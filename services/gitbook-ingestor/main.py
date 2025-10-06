"""
GitBook Ingestion Service for Crash-Pay
--------------------------------------
Fetches Markdown content from GitBook spaces and upserts embeddings to Pinecone
indices. Supports:
• Full back-fill at startup
• Incremental updates via GitBook webhooks (page.published / page.updated /
  page.deleted)

This service is intentionally light on security ‑ it runs on an internal
network and trusts the environment.
"""

from __future__ import annotations

import asyncio
import logging
import os
import typing as t

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Pinecone as LCPinecone
from pinecone import Pinecone, ServerlessSpec
from pydantic import BaseModel

# ────────────────────────────────
# Logging
# ────────────────────────────────
logger = logging.getLogger("gitbook_ingestor")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ────────────────────────────────
# Environment / Configuration
# ────────────────────────────────
GITBOOK_TOKEN = os.getenv("GITBOOK_TOKEN") or os.getenv("GITBOOK_API")
if not GITBOOK_TOKEN:
    raise RuntimeError("GITBOOK_TOKEN environment variable is required")

# Remove quotes if present in token
GITBOOK_TOKEN = GITBOOK_TOKEN.strip('"\'')

HEADERS = {"Authorization": f"Bearer {GITBOOK_TOKEN}"}
logger.info(f"GitBook token configured (length: {len(GITBOOK_TOKEN)}, prefix: {GITBOOK_TOKEN[:10]}...)")

# Single space with collections/groups
SPACE_ID = os.getenv("GITBOOK_SPACE_ID")
if not SPACE_ID:
    raise RuntimeError("GITBOOK_SPACE_ID environment variable is required")
# Collection paths within the space
COLLECTION_PATHS: dict[str, str] = {
    "rag": "",  # Root level pages (main space content)
    "nonrag": "non-rag-corpus",  # Collection path
}

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise RuntimeError("PINECONE_API_KEY environment variable is required")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
INDEX_NAMES: dict[str, str] = {
    "rag": os.getenv("PINECONE_INDEX_RAG", "fake-fintech-rag-corpus"),
    "nonrag": os.getenv("PINECONE_INDEX_NONRAG", "fake-fintech-nonrag-corpus"),
}

# ────────────────────────────────
# Pinecone initialisation (lazy per index)
# ────────────────────────────────
pc = Pinecone(api_key=PINECONE_API_KEY)
embedder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2"
)
_indexes: dict[str, LCPinecone] = {}

def get_index(group: str) -> LCPinecone:
    """Return (and create if needed) the Pinecone index for the corpus group."""
    if group in _indexes:
        return _indexes[group]

    index_name = INDEX_NAMES[group]
    existing = {i["name"] for i in pc.list_indexes()}
    if index_name not in existing:
        logger.info("Creating Pinecone index %s", index_name)
        pc.create_index(
            index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV),
        )
    pinecone_idx = pc.Index(index_name)
    lc_index = LCPinecone(pinecone_idx, embedder, text_key="text")
    _indexes[group] = lc_index
    return lc_index

# ────────────────────────────────
# GitBook helper functions
# ────────────────────────────────
async def fetch_page(client: httpx.AsyncClient, space_id: str, page_id: str) -> dict:
    """Fetch a specific page with full document content by ID."""
    try:
        # Use the correct GitBook API endpoint for full page content
        logger.debug("🔍 Fetching full page content for %s", page_id)
        url = f"https://api.gitbook.com/v1/spaces/{space_id}/content/page/{page_id}"
        resp = await client.get(url, headers=HEADERS, timeout=10.0)
        
        if resp.status_code == 200:
            logger.debug("✅ Successfully fetched full page content")
            return resp.json()
        else:
            logger.error("❌ Failed to fetch page content: %s %s", resp.status_code, resp.text)
            return {}
            
    except Exception as e:
        logger.error("❌ Error fetching page content: %s", str(e))
        return {}


def find_page_by_id(pages: list[dict], target_id: str) -> dict | None:
    """Recursively find a page by ID in the GitBook page structure."""
    for page in pages:
        if page.get("id") == target_id:
            return page
        # Check nested pages
        if page.get("pages"):
            result = find_page_by_id(page["pages"], target_id)
            if result:
                return result
    return None


def extract_document_pages(pages: list[dict], target_group_path: str = "") -> list[dict]:
    """Recursively extract document pages from GitBook page structure."""
    documents = []
    
    for page in pages:
        if page.get("type") == "document":
            # This is a document page
            page_path = page.get("path", "")
            if not target_group_path or page_path.startswith(target_group_path):
                documents.append(page)
        elif page.get("type") == "group":
            # This is a group, check if it matches our target or recurse into it
            group_path = page.get("path", "")
            if not target_group_path:
                # For root collection (rag), we want groups that are NOT non-rag-corpus
                if group_path != "non-rag-corpus":
                    documents.extend(extract_document_pages(page.get("pages", []), ""))
            elif group_path == target_group_path:
                # This is the target group, extract all documents inside
                documents.extend(extract_document_pages(page.get("pages", []), ""))
    
    return documents


async def list_pages(client: httpx.AsyncClient, space_id: str, collection_path: str = "") -> list[dict]:
    """List pages in a space, optionally filtered by collection path."""
    url = f"https://api.gitbook.com/v1/spaces/{space_id}/content"
    logger.info(f"Requesting GitBook API: {url}")
    resp = await client.get(url, headers=HEADERS, timeout=10.0)
    
    if resp.status_code != 200:
        logger.error(f"GitBook API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    
    content_data = resp.json()
    all_pages = content_data.get("pages", [])
    
    # Extract document pages based on collection path
    if collection_path == "":
        # For rag collection: get all documents NOT in non-rag-corpus
        return extract_document_pages(all_pages, target_group_path="")
    else:
        # For specific collection: get documents in that group path
        return extract_document_pages(all_pages, target_group_path=collection_path)


def extract_text_content(document: dict) -> str:
    """Extract text content from GitBook document structure."""
    if not document:
        return ""
    
    text_parts = []
    
    # GitBook documents have a 'nodes' structure containing the actual content blocks
    if document.get("nodes"):
        for node in document["nodes"]:
            node_text = extract_text_from_node(node)
            if node_text.strip():
                text_parts.append(node_text.strip())
    
    return "\n\n".join(text_parts) if text_parts else ""


def extract_text_from_node(node: dict) -> str:
    """Recursively extract text from a GitBook document node."""
    if not isinstance(node, dict):
        return ""
    
    text_parts = []
    
    # Handle text nodes with leaves (contains the actual text content)
    if node.get("object") == "text" and node.get("leaves"):
        for leaf in node["leaves"]:
            if isinstance(leaf, dict) and leaf.get("text"):
                text_parts.append(leaf["text"])
    
    # Handle block nodes that contain nested content
    elif node.get("object") == "block" and node.get("nodes"):
        for child_node in node["nodes"]:
            child_text = extract_text_from_node(child_node)
            if child_text.strip():
                text_parts.append(child_text.strip())
    
    # Handle nodes that have direct text content
    elif node.get("text"):
        text_parts.append(node["text"])
    
    # Join text appropriately
    if text_parts:
        # For block-level content, join with newlines
        if node.get("type") in ["heading-1", "heading-2", "heading-3", "paragraph", "list-item"]:
            return "\n".join(text_parts)
        else:
            # For inline content, join with spaces
            return " ".join(text_parts)
    
    return ""


async def upsert_page(group: str, page: dict) -> None:
    """Upsert a page to the vector database."""
    index = get_index(group)
    
    # Extract text content from the page
    text_content = ""
    
    # Try different text fields that might contain content
    if page.get("document"):
        text_content = extract_text_content(page["document"])
    elif page.get("description"):
        text_content = page["description"]
    elif page.get("title"):
        text_content = page["title"]  # At minimum, use the title
    
    # For GitBook pages, we also have title and description available
    title = page.get("title", "")
    description = page.get("description", "")
    
    # Combine all available text
    all_text_parts = [title, description, text_content]
    combined_text = "\n".join([part for part in all_text_parts if part.strip()])
    
    if not combined_text.strip():
        logger.warning("No text content found for page %s", page.get("title", "unknown"))
        return
    
    metadata = {
        "title": page.get("title", ""),
        "path": page.get("path", ""),
        "updated": page.get("updatedAt", ""),
        "description": page.get("description", ""),
        "document_id": page.get("documentId", ""),
        "source": f"{group}:{page.get('id')}",
    }
    
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: index.add_texts([combined_text], metadatas=[metadata], ids=[page["id"]]),
    )
    logger.info("Upserted page '%s' to %s index (content length: %d)", 
                page.get("title", "unknown"), group, len(combined_text))


async def delete_page(group: str, page_id: str) -> None:
    index = get_index(group)
    index.delete(page_id)
    logger.info("Deleted page %s from %s", page_id, group)


async def full_sync() -> None:
    """Perform a full back-fill of all collections in the space."""
    async with httpx.AsyncClient() as client:
        for group, collection_path in COLLECTION_PATHS.items():
            logger.info("Starting full sync for %s (collection: %s)", group, collection_path or "root")
            pages = await list_pages(client, SPACE_ID, collection_path)
            tasks: list[asyncio.Task] = []
            for p in pages:
                tasks.append(asyncio.create_task(fetch_page(client, SPACE_ID, p["id"])))
            for task in asyncio.as_completed(tasks):
                page = await task
                await upsert_page(group, page)
    logger.info("Full sync finished.")


# ────────────────────────────────
# FastAPI application
# ────────────────────────────────
app = FastAPI(title="GitBook Ingestor", version="0.1.0")


class WebhookPayload(BaseModel):
    event: str
    spaceId: str
    pageId: str | None = None
    page: dict | None = None  # GitBook sometimes includes page data


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(full_sync())


def determine_group_from_page_path(page_path: str) -> str:
    """Determine which group (rag/nonrag) a page belongs to based on its path."""
    if page_path.startswith("non-rag-corpus/"):
        return "nonrag"
    else:
        return "rag"  # Default to rag for root-level pages


async def _handle_upsert(space_id: str, page_id: str):
    async with httpx.AsyncClient() as client:
        page = await fetch_page(client, space_id, page_id)
        page_path = page.get("path", "")
        group = determine_group_from_page_path(page_path)
        await upsert_page(group, page)


@app.post("/webhook")
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    if payload.spaceId != SPACE_ID:
        raise HTTPException(400, f"Unknown spaceId: {payload.spaceId}")
    
    if payload.event in {"page.updated", "page.published"} and payload.pageId:
        background_tasks.add_task(_handle_upsert, payload.spaceId, payload.pageId)
    elif payload.event == "page.deleted" and payload.pageId:
        # For deletions, we need to determine the group somehow
        # Since we don't have the page anymore, we'll try both indices
        for group in ["rag", "nonrag"]:
            background_tasks.add_task(delete_page, group, payload.pageId)
    else:
        logger.warning("Unhandled event %s", payload.event)
    return {"status": "accepted"}


@app.post("/sync")
async def manual_sync(request: Request):
    """Manually trigger a full sync of GitBook content."""
    try:
        # Optional: Check for authorization header
        auth_header = request.headers.get("authorization")
        expected_token = os.getenv("RAG_SYNC_TOKEN")
        
        if expected_token and auth_header:
            if not auth_header.startswith("Bearer ") or auth_header[7:] != expected_token:
                raise HTTPException(status_code=401, detail="Invalid authorization token")
        elif expected_token:
            raise HTTPException(status_code=401, detail="Authorization token required")
        
        logger.info("🔄 Manual sync triggered")
        await full_sync()
        return {"status": "success", "message": "Full sync completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Manual sync failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/debug/gitbook")
async def debug_gitbook():
    """Debug endpoint to test GitBook connection and see what content is available."""
    debug_info = {
        "space_id": SPACE_ID,
        "collections": {},
        "errors": []
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Test both collections
            for group, collection_path in COLLECTION_PATHS.items():
                logger.info(f"🔍 Testing {group} collection (path: '{collection_path}')")
                debug_info["collections"][group] = {
                    "collection_path": collection_path,
                    "pages": [],
                    "total_pages": 0,
                    "pages_with_content": 0,
                    "error": None
                }
                
                try:
                    pages = await list_pages(client, SPACE_ID, collection_path)
                    debug_info["collections"][group]["total_pages"] = len(pages)
                    
                    # Get details for first few pages
                    for i, page in enumerate(pages[:3]):  # Limit to first 3 pages for debug
                        try:
                            full_page = await fetch_page(client, SPACE_ID, page["id"])
                            content = extract_text_content(full_page.get("document", {}))
                            
                            page_info = {
                                "id": page["id"],
                                "title": page.get("title", "No title"),
                                "path": page.get("path", ""),
                                "type": page.get("type", ""),
                                "content_length": len(content),
                                "content_preview": content[:200] + "..." if len(content) > 200 else content
                            }
                            debug_info["collections"][group]["pages"].append(page_info)
                            
                            if content.strip():
                                debug_info["collections"][group]["pages_with_content"] += 1
                                
                        except Exception as e:
                            logger.error(f"Error fetching page {page['id']}: {e}")
                            debug_info["collections"][group]["pages"].append({
                                "id": page["id"],
                                "title": page.get("title", "No title"),
                                "error": str(e)
                            })
                
                except Exception as e:
                    logger.error(f"Error listing pages for {group}: {e}")
                    debug_info["collections"][group]["error"] = str(e)
                    debug_info["errors"].append(f"{group}: {str(e)}")
        
        except Exception as e:
            logger.error(f"General GitBook API error: {e}")
            debug_info["errors"].append(f"General API error: {str(e)}")
    
    return debug_info


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.gitbook-ingestor.main:app", host="0.0.0.0", port=8020)
