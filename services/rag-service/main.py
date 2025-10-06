from __future__ import annotations

"""
RAG Service – *Intentionally* vulnerable, no-auth, Retrieval-Augmented-Generation
search endpoint.

Design goals
------------
1. Expose `/search?q=...` that streams raw vector-DB hits (incl. full text,
   source path, scores, metadata) to anyone – deliberately leaking everything
   in the index (OWASP-LLM-06).
2. **No authentication / rate-limiting / schema-validation**.
3. **No query-length cap or pagination** → token / CPU DoS potential (LLM-04).
4. Minimal dependencies so the container can run standalone under
   `docker-compose up` even when external Pinecone is unavailable.  If a
   PINECONE_API_KEY is present the service will prefer Pinecone, otherwise it
   falls back to a local FAISS index that is (re)built on first run from the
   Markdown files checked-in under `docs/rag_corpus/`.

Nothing in this file provides exploit code or security "hints" – only the bare
vulnerable surfaces requested in the blueprint.
"""

import asyncio
import json
import os
import pathlib
import pickle
import time
import typing as t
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

# --------------------------------------------------------------------------- #
# Optional / "soft" imports.  The service tries to stay alive even if some
# libraries are missing – this avoids container crash-loops during workshops.
# --------------------------------------------------------------------------- #
try:
    from langchain.embeddings import HuggingFaceEmbeddings
    from langchain.vectorstores.faiss import FAISS
except Exception:  # pragma: no cover
    FAISS = None  # type: ignore
    HuggingFaceEmbeddings = None  # type: ignore

try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:  # pragma: no cover
    Pinecone = None  # type: ignore
    ServerlessSpec = None  # type: ignore


HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CORPUS_DIR = (
    HERE.parent.parent.parent / "docs" / "rag_corpus"
)  # points three levels up


# --------------------------------------------------------------------------- #
# FastAPI set-up
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: D401
    """App lifespan: initialise vector store once, then keep in memory."""
    global VECTOR_STORE  # noqa: PLW0603
    VECTOR_STORE = await init_vector_store()
    yield
    # Nothing to clean up – FAISS lives in process; Pinecone handled by SDK.


app = FastAPI(
    title="Fake-Fintech • RAG Service (insecure)",
    description=(
        "Unauthenticated vector search endpoint purposely leaking raw docs "
        "so researchers can exercise OWASP-LLM-06 + others."
    ),
    version="0.1.0-vuln",
    lifespan=lifespan,
)

# Placeholder set in lifespan()
VECTOR_STORE: "VectorStoreProtocol" | None = None


# --------------------------------------------------------------------------- #
# Protocol (duck-type) to avoid importing heavy LangChain base classes at
# import-time.
# --------------------------------------------------------------------------- #
class VectorStoreProtocol(t.Protocol):
    async def async_similarity_search_with_score(  # type: ignore[override]
        self, query: str, k: int
    ) -> list[tuple[t.Any, float]]: ...


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
async def init_vector_store() -> VectorStoreProtocol:
    """Create / connect to a vector store (Pinecone or local FAISS)."""
    
    # Check VECTOR_DB_TYPE to determine which vector store to use
    vector_db_type = os.getenv("VECTOR_DB_TYPE", "faiss").lower()
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    
    print(f"🔍 Debug: vector_db_type={vector_db_type}")
    print(f"🔍 Debug: pinecone_api_key exists={bool(pinecone_api_key)}")
    print(f"🔍 Debug: Pinecone module available={Pinecone is not None}")
    
    # 1️⃣ Pinecone path (if explicitly configured) -------------------- #
    if vector_db_type == "pinecone" and pinecone_api_key and Pinecone is not None:
        api_key = pinecone_api_key
        if not api_key or api_key == "changeme":
            print("⚠️  PINECONE_API_KEY not properly configured, falling back to FAISS")
        else:
            index_name = os.getenv("PINECONE_INDEX", "fake-fintech-rag-corpus")
            
            print(f"🌲 Initializing Pinecone 3.x with index: {index_name}")
            
            # Initialize Pinecone with the new 3.x API
            pc = Pinecone(api_key=api_key)
            
            # Connect to existing index (create if doesn't exist)
            existing_indexes = {i["name"] for i in pc.list_indexes()}
            if index_name not in existing_indexes:
                print(f"🔧 Creating Pinecone index: {index_name}")
                pc.create_index(
                    index_name,
                    dimension=768,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
            index = pc.Index(index_name)

            if HuggingFaceEmbeddings is None:
                raise RuntimeError("Missing langchain embeddings back-end.")

            embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
            from langchain.vectorstores import Pinecone as LC_Pinecone  # lazy

            print(f"✅ Pinecone vector store initialized successfully")
            return LC_Pinecone(index, embedder, text_key="text")
    
    # 2️⃣ Local FAISS fallback -------------------------------------------- #
    print(f"💾 Using local FAISS vector store (VECTOR_DB_TYPE={vector_db_type})")
    if FAISS is None or HuggingFaceEmbeddings is None:
        raise RuntimeError(
            "FAISS / HuggingFace libs not available and Pinecone not configured."
        )

    faiss_idx_path = HERE / "index.faiss"
    metadata_path = HERE / "index.pkl"

    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

    if faiss_idx_path.exists() and metadata_path.exists():
        with open(metadata_path, "rb") as fh:
            stored = pickle.load(fh)
        index = FAISS.load_local(str(faiss_idx_path), embeddings=embedder)
        print("✅ Loaded existing FAISS index")
        return index

    # Build from scratch on first run
    print("🔧 Building FAISS index from documents...")
    docs = load_docs(DEFAULT_CORPUS_DIR)
    index = FAISS.from_texts(texts=[d["text"] for d in docs], embedding=embedder, metadatas=docs)
    index.save_local(str(faiss_idx_path))
    with open(metadata_path, "wb") as fh:
        pickle.dump(docs, fh)
    print(f"✅ FAISS index built successfully with {len(docs)} documents")
    return index


def load_docs(root: pathlib.Path) -> list[dict[str, t.Any]]:
    """Load every file under `root` into memory as plain text chunks.

    The simplest thing possible: each file becomes one "document".  No chunking,
    no cleaning, no redaction → intentional ☠️.
    """
    docs: list[dict[str, t.Any]] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md", ".txt"}:
            docs.append(
                {
                    "id": str(uuid.uuid4()),
                    "source": str(p.relative_to(root)),
                    "text": p.read_text(encoding="utf-8", errors="ignore"),
                }
            )
    if not docs:
        # Put at least one placeholder doc so FAISS dimension known
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "source": "placeholder.txt",
                "text": "No documents loaded. This is an empty placeholder.",
            }
        )
    return docs


async def stream_hits(
    results: list[tuple[t.Any, float]],
) -> t.AsyncGenerator[bytes, None]:
    """Yield search hits as NDJSON over an HTTP streaming response."""
    # Simulate latency so clients see progressive streaming (and so that –
    # intentionally – attackers can exploit timing / DoS angles).
    for doc, score in results:
        payload = {
            "source": getattr(doc, "metadata", {}).get("source", "N/A"),
            "score": score,
            "text": getattr(doc, "page_content", str(doc)),
            # leak everything, no redaction
        }
        yield (json.dumps(payload) + "\n").encode("utf-8")
        await asyncio.sleep(0.05)  # small delay to mimic streaming
    # Stream terminator
    yield b""


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "ts": str(int(time.time()))}


# Alias route so container health-checks on /health succeed as well
@app.get("/health")
async def health_alias() -> dict[str, str]:
    """Simple alias to `/healthz` for external probes."""
    return {"status": "ok", "ts": str(int(time.time()))}


@app.get("/search")
async def search_endpoint(
    request: Request,
    q: str = Query(..., description="Free-form search string"),
    k: int = Query(10, gt=0, lt=50, description="Number of neighbours to return"),
):
    if VECTOR_STORE is None:  # pragma: no cover
        raise HTTPException(503, "Vector store not ready")

    # Basic empty check – we DELIBERATELY **don't** validate size / charset
    if not q.strip():
        raise HTTPException(400, "Query must not be empty")

    # Offload similarity search to thread-pool to avoid blocking event-loop
    loop = asyncio.get_event_loop()

    results: list[tuple[t.Any, float]] = await loop.run_in_executor(
        None, lambda: VECTOR_STORE.similarity_search_with_score(q, k)  # type: ignore[attr-defined]
    )

    # Return as chunked NDJSON (no auth, no filtering)
    return StreamingResponse(
        stream_hits(results),
        media_type="application/x-ndjson",
    )


@app.post("/query")
async def query_endpoint(request: dict):
    """JSON endpoint for llm-service integration."""
    if VECTOR_STORE is None:  # pragma: no cover
        raise HTTPException(503, "Vector store not ready")
    
    query = request.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query must not be empty")
    
    k = request.get("k", 5)  # Default to 5 results
    
    # Offload similarity search to thread-pool
    loop = asyncio.get_event_loop()
    results: list[tuple[t.Any, float]] = await loop.run_in_executor(
        None, lambda: VECTOR_STORE.similarity_search_with_score(query, k)  # type: ignore[attr-defined]
    )
    
    # Extract the best context text
    if results:
        # Combine all result texts
        context_texts = []
        for doc, score in results:
            text = getattr(doc, "page_content", str(doc))
            context_texts.append(text)
        
        context = "\n\n".join(context_texts)
        return {"context": context, "results_count": len(results)}
    else:
        return {"context": "", "results_count": 0}


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    uvicorn.run(
        "services.rag_service.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8005)),
        reload=bool(os.getenv("DEV", "")),
    )