"""
FunctionExecutor for executing real banking operations by calling internal micro-services.
This sits in the service layer so it can be reused by LLMService and other APIs.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, Callable, Awaitable, Optional
from datetime import datetime, timedelta

import httpx

from app.config.settings import get_settings
from app.utils.logging import get_logger
from app.utils.singleton import singleton_factory

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helper – HTTP call into finance-service (internal Docker network)
# ---------------------------------------------------------------------------

async def _call_finance_service(
    path: str,
    *,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
) -> Any:
    """Thin async wrapper around httpx for calling the finance-service.

    Args:
        path: Endpoint path starting with a slash (e.g. "/accounts").
        method: HTTP verb.
        params: Querystring parameters (for GET).
        payload: JSON body (for POST, PUT).
        timeout: Seconds before aborting – project rule caps this at 5s.
    """
    settings = get_settings()
    base_url: str = os.getenv("FINANCE_SERVICE_URL", getattr(settings, "finance_service_url", "http://finance-service:4002"))
    url = f"{base_url}{path}"

    logger.debug(f"Calling finance-service {method} {url}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method.upper() == "GET":
            response = await client.get(url, params=params)
        else:
            response = await client.request(method.upper(), url, json=payload)

    if response.status_code >= 400:
        # Bubble up error details for visibility in the agent
        raise RuntimeError(f"Finance-service {method} {path} failed: {response.status_code} – {response.text}")

    try:
        return response.json()
    except ValueError:
        return response.text  # not JSON – return raw text

# ---------------------------------------------------------------------------
# Concrete banking function implementations
# ---------------------------------------------------------------------------

async def _transfer_funds(args: Dict[str, Any], user_context) -> Dict[str, Any]:
    """Transfer funds between two accounts. Requires destination account ID provided by list_recipients."""
    required = {"from_account", "to_account_id", "amount"}
    if not required.issubset(args):
        raise ValueError(f"transfer_funds requires {required}")

    user_id = getattr(user_context, "user_id", None)
    if not user_id:
        raise ValueError("User context not available for transfer_funds")

    # Resolve sender's source account ID from account type (checking / savings)
    from_account_id = await _resolve_user_account(args["from_account"], user_id)

    # Destination must already be an account UUID provided by list_recipients
    to_account_id = args["to_account_id"]

    payload = {
        "fromAccountId": from_account_id,
        "toAccountId": to_account_id,
        "amount": args["amount"],
        "description": args.get("description", "LLM initiated transfer"),
    }
    result = await _call_finance_service("/transfers", method="POST", payload=payload)
    return result


async def _list_recipients(args: Dict[str, Any], user_context) -> Dict[str, Any]:
    """Search for users by (partial) name and return recipient(s) with an account ID.

    Behavior:
    - If account_type is provided (e.g., "checking" or "savings"), returns recipients whose account of that type exists,
      selecting that account's ID.
    - If account_type is not provided, returns the first account ID (existing behavior), but includes the account_type
      in the response object for transparency.
    """
    search_term = args.get("name")
    requested_type = (args.get("account_type") or "").strip().lower() if args else ""

    logger.info(f"[FUNCTION_DEBUG] list_recipients called with search_term: '{search_term}', account_type: '{requested_type or 'N/A'}'")
    
    if not search_term or len(search_term.strip()) < 3:
        raise ValueError("name parameter (min 3 chars) is required")

    try:
        logger.info(f"[FUNCTION_DEBUG] Calling user-service with search_term: '{search_term}'")
        users_resp = await _call_user_service("/users", params={"name": search_term})
        logger.info(f"[FUNCTION_DEBUG] User-service response: {users_resp}")
        
        users = users_resp.get("users", [])
        logger.info(f"[FUNCTION_DEBUG] Found {len(users)} users: {users}")
        
        recipients = []
        for u in users:
            logger.info(f"[FUNCTION_DEBUG] Getting accounts for user {u['id']} ({u['name']})")
            accounts = await _call_finance_service("/accounts", params={"userId": u["id"]})
            logger.info(f"[FUNCTION_DEBUG] User {u['name']} has {len(accounts) if accounts else 0} accounts: {accounts}")
            
            if not accounts:
                continue

            chosen_account = None
            if requested_type:
                for a in accounts:
                    if str(a.get("type", "")).strip().lower() == requested_type:
                        chosen_account = a
                        break
                if not chosen_account:
                    # Skip this user if they don't have the requested account type
                    logger.info(f"[FUNCTION_DEBUG] User {u['name']} lacks requested account_type '{requested_type}', skipping")
                    continue
            else:
                chosen_account = accounts[0]

            recipients.append({
                "user_id": u["id"],
                "name": u["name"],
                "account_id": chosen_account["id"],
                "account_type": chosen_account.get("type")
            })
        
        logger.info(f"[FUNCTION_DEBUG] Final recipients list: {recipients}")
        return {"recipients": recipients}
    except Exception as e:
        logger.error(f"[FUNCTION_DEBUG] Failed to list recipients for term '{search_term}': {e}")
        logger.error(f"[FUNCTION_DEBUG] Exception type: {type(e).__name__}")
        logger.error(f"[FUNCTION_DEBUG] Exception details: {str(e)}")
        raise RuntimeError("Recipient lookup failed")


async def _resolve_user_account(account_identifier: str, user_id: str) -> str:
    """Resolve user's account identifier to account ID."""
    # If it looks like a UUID, assume it's already an account ID
    if len(account_identifier) == 36 and account_identifier.count('-') == 4:
        return account_identifier
    
    # Otherwise, treat as account type (checking, savings)
    accounts = await _call_finance_service("/accounts", params={"userId": user_id})
    for account in accounts:
        if account.get("type", "").lower() == account_identifier.lower():
            return account["id"]
    
    raise ValueError(f"No {account_identifier} account found for user")


async def _resolve_recipient_account(recipient_identifier: str, sender_user_id: str) -> str:
    """Resolve recipient identifier to account ID."""
    # If it looks like a UUID, assume it's already an account ID
    if len(recipient_identifier) == 36 and recipient_identifier.count('-') == 4:
        return recipient_identifier
    
    # If it looks like a name (contains space or is longer than typical account type)
    if ' ' in recipient_identifier or len(recipient_identifier) > 10:
        # Search for user by name
        try:
            # Call user-service to search by name
            users_response = await _call_user_service("/users", params={"name": recipient_identifier})
            users = users_response.get("users", [])
            
            if not users:
                raise ValueError(f"No user found with name: {recipient_identifier}")
            
            # Use the first matching user
            recipient_user = users[0]
            recipient_user_id = recipient_user["id"]
            
            # Get recipient's accounts
            accounts = await _call_finance_service("/accounts", params={"userId": recipient_user_id})
            if not accounts:
                raise ValueError(f"Recipient {recipient_identifier} has no accounts")
            
            # Use their first account (typically checking)
            return accounts[0]["id"]
            
        except Exception as e:
            logger.error(f"Failed to resolve recipient name {recipient_identifier}: {e}")
            raise ValueError(f"Could not find recipient: {recipient_identifier}")
    
    # Otherwise, treat as sender's own account type for internal transfers
    return await _resolve_user_account(recipient_identifier, sender_user_id)


def _extract_finance_user_id(user_context) -> str:
    """Prefer finance_user_id from user context attributes; fallback to user_id.
    If neither present, returns None and upstream callers should handle.
    """
    if not user_context:
        return None
    try:
        attributes = getattr(user_context, "attributes", {}) or {}
        finance_id = attributes.get("finance_user_id")
        if isinstance(finance_id, str) and finance_id.strip():
            return finance_id.strip()
    except Exception:
        pass
    return getattr(user_context, "user_id", None)


async def _call_user_service(endpoint: str, method: str = "GET", payload: Dict = None, params: Dict = None) -> Dict[str, Any]:
    """Call user-service API."""
    user_service_port = os.getenv("USER_SERVICE_INTERNAL_PORT", "8081")
    url = f"http://user-service:{user_service_port}{endpoint}"
    
    logger.info(f"[HTTP_DEBUG] Calling user-service: {method} {url} with params={params}, payload={payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, params=params, timeout=10.0)
            elif method == "POST":
                response = await client.post(url, json=payload, timeout=10.0)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            logger.info(f"[HTTP_DEBUG] User-service response: status={response.status_code}, body={response.text[:500]}")
            response.raise_for_status()
            result = response.json()
            logger.info(f"[HTTP_DEBUG] User-service parsed JSON: {result}")
            return result
    except httpx.HTTPError as e:
        logger.error(f"[HTTP_DEBUG] HTTP error calling user-service {url}: {e}")
        logger.error(f"[HTTP_DEBUG] Response status: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
        logger.error(f"[HTTP_DEBUG] Response body: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        raise RuntimeError(f"User service error: {e}")
    except Exception as e:
        logger.error(f"[HTTP_DEBUG] Error calling user-service {url}: {e}")
        raise RuntimeError(f"User service error: {e}")


async def _get_account_balance(args: Dict[str, Any], user_context) -> Dict[str, Any]:
    """Return aggregated balance for the requested account type."""
    acct_type = args.get("account_type")
    if not acct_type:
        raise ValueError("account_type parameter required")

    # Assuming finance-service returns list of accounts with fields [type, balance]
    params = {"userId": _extract_finance_user_id(user_context)} if user_context else None
    accounts = await _call_finance_service("/accounts", params=params)
    balance = sum(float(a.get("balance", 0)) for a in accounts if a.get("type", "").lower() == acct_type.lower())
    return {"account_type": acct_type, "balance": balance}


async def _get_transaction_history(args: Dict[str, Any], user_context) -> Dict[str, Any]:
    """Fetch recent transactions for a user (basic filtering client-side)."""
    days = int(args.get("days", 30))
    params = {"userId": _extract_finance_user_id(user_context)} if user_context else None
    txns = await _call_finance_service("/transactions", params=params)

    # Rough filter by days using createdAt timestamp if present
    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered = [t for t in txns if _txn_within_cutoff(t, cutoff)]

    # Apply item cap if the model did not specify a limit
    limit_arg = None
    try:
        if isinstance(args, dict) and args.get("limit") is not None:
            limit_arg = int(args.get("limit"))
    except Exception:
        limit_arg = None

    # Default to 5 if no explicit limit provided; do not override if the AI capped it
    effective_limit = limit_arg if (isinstance(limit_arg, int) and limit_arg > 0) else 5
    txns_capped = filtered[:effective_limit] if isinstance(effective_limit, int) and effective_limit > 0 else filtered

    try:
        logger.info(f"[FUNCTION_DEBUG] get_transaction_history returning {len(txns_capped)} of {len(filtered)} (limit={effective_limit}, days={days})")
    except Exception:
        pass

    return {"days": days, "transactions": txns_capped}


async def _get_rag_context(args: Dict[str, Any], user_context) -> Dict[str, Any]:
    """Query rag-service for a concise knowledge-base context.

    Expected args: { "query": string }
    Returns: { "context": string }
    """
    from app.config.settings import get_settings
    settings = get_settings()

    query_text = (args or {}).get("query")
    if not query_text:
        # Try to recover from user_context if available
        last_user_msg = getattr(user_context, "last_user_message", None)
        if isinstance(last_user_msg, str) and last_user_msg.strip():
            query_text = last_user_msg.strip()
        else:
            raise ValueError("get_rag_context requires 'query' string")

    # Determine per-model defaults for RAG limits (k, context truncation)
    rag_k = None
    rag_max_chars = None
    try:
        from app.services.model_registry import ModelRegistry
        provider = getattr(settings, "llm_provider", "")
        model_api = getattr(settings, "llm_model", "")
        friendly = ModelRegistry.get_friendly_name(provider, model_api) or model_api
        defaults = ModelRegistry.get_default_params(provider, friendly)
        rag_k = int(defaults.get("rag_k")) if isinstance(defaults, dict) and defaults.get("rag_k") else None
        rag_max_chars = int(defaults.get("rag_max_context_chars")) if isinstance(defaults, dict) and defaults.get("rag_max_context_chars") else None
    except Exception:
        pass

    url = f"{settings.rag_service_url}/query"
    payload = {"query": query_text}
    if rag_k and rag_k > 0:
        payload["k"] = rag_k

    logger.info(f"[RAG_TOOL] Calling rag-service with query len={len(query_text)}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code >= 400:
        raise RuntimeError(f"rag-service failed: {resp.status_code} – {resp.text}")

    try:
        data = resp.json()
    except ValueError:
        data = {"context": resp.text}

    context_text = data.get("context") if isinstance(data, dict) else None
    if not context_text:
        context_text = ""
    # Truncate context if configured
    try:
        if isinstance(rag_max_chars, int) and rag_max_chars > 0 and len(context_text) > rag_max_chars:
            context_text = context_text[:rag_max_chars]
    except Exception:
        pass
    logger.info(f"[RAG_TOOL] rag-service returned context len={len(context_text)}")
    return {"context": context_text}


async def _get_user_profile(args: Dict[str, Any], user_context):
    """Return basic profile info for the current user (admin call)."""
    if not user_context or not user_context.user_id:
        raise ValueError("User context required")
    user_id = _extract_finance_user_id(user_context)
    result = await _call_finance_service("/accounts", params={"userId": user_id})
    profile = {
        "user_id": user_id,
        "name": user_context.attributes.get("user_name") if user_context else None,
        "membership_tier": user_context.attributes.get("membership_tier"),
        "region": user_context.attributes.get("region"),
        "accounts": result,
    }
    return profile


def _txn_within_cutoff(txn: Dict[str, Any], cutoff) -> bool:
    ts = txn.get("createdAt") or txn.get("created_at")
    if not ts:
        return True  # keep if timestamp missing
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt >= cutoff
    except Exception:
        return True

# ---------------------------------------------------------------------------
# Registry + Executor
# ---------------------------------------------------------------------------

FUNCTION_MAP: Dict[str, Callable[[Dict[str, Any], Any], Awaitable[Any]]] = {
    "list_recipients": _list_recipients,
    "transfer_funds": _transfer_funds,
    "get_account_balance": _get_account_balance,
    "get_transaction_history": _get_transaction_history,
    "get_user_profile": _get_user_profile,
    # RAG as a tool
    "get_rag_context": _get_rag_context,
}


class FunctionExecutor:
    """Executes permitted banking functions asynchronously."""

    async def execute(self, function_name: str, arguments: Dict[str, Any], user_context=None) -> Any:
        if function_name not in FUNCTION_MAP:
            raise ValueError(f"Unknown function: {function_name}")
        func = FUNCTION_MAP[function_name]
        logger.info(f"Executing function {function_name}")
        result = await func(arguments, user_context)
        logger.debug(f"Function executed: {function_name}")
        return result


@singleton_factory
def get_function_executor() -> FunctionExecutor:  # pragma: no cover – singleton
    return FunctionExecutor()
