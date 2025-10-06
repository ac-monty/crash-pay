from fastapi import APIRouter, Depends, HTTPException
from app.auth.middleware import get_current_user
from app.auth.models import UserPermissions
from app.services.memory import get_memory_manager

router = APIRouter()

@router.post("/threads/{thread_id}/close", summary="Close chat thread")
async def close_thread(thread_id: str, user: UserPermissions = Depends(get_current_user)):
    memory = get_memory_manager()
    await memory.close_thread(thread_id)
    return {"thread_id": thread_id, "closed": True} 