from datetime import datetime
from typing import List, Dict, Any, Optional

import motor.motor_asyncio

from app.config.settings import get_settings
from app.utils.singleton import singleton_factory


class MemoryManager:
    """Persist chat threads in MongoDB.
    Two collections:
      • chat_threads_active – full documents per thread (for prompt building)
      • chat_threads_audit  – one document per message for immutable audit
    """

    def __init__(self):
        settings = get_settings()
        self._client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongo_uri)
        self._db = self._client.get_default_database()
        self._active = self._db["chat_threads_active"]
        self._audit = self._db["chat_threads_audit"]
        # TTL index on active collection (24h) if not present
        self._ensure_indexes()

    async def _ensure_indexes(self):
        await self._active.create_index("last_activity", expireAfterSeconds=60*60*24)
        await self._audit.create_index([("thread_id", 1), ("message_index", 1)], unique=True)

    async def load_history(self, thread_id: str) -> List[Dict[str, Any]]:
        doc = await self._active.find_one({"thread_id": thread_id})
        return doc.get("messages", []) if doc else []

    async def append_messages(self, thread_id: str, user_id: str, messages: List[Dict[str, Any]]):
        now = datetime.utcnow()
        # Update active thread
        await self._active.update_one(
            {"thread_id": thread_id},
            {
                "$setOnInsert": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "created_at": now,
                },
                "$set": {"last_activity": now},
                "$push": {"messages": {"$each": messages}},
            },
            upsert=True,
        )
        # Insert audit rows
        for idx, msg in enumerate(messages):
            audit_doc = {
                "thread_id": thread_id,
                "user_id": user_id,
                "message_index": int(now.timestamp()*1000)+idx,
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": now,
                "function_call": msg.get("function_call"),
            }
            try:
                await self._audit.insert_one(audit_doc)
            except Exception:
                # ignore dup errors
                pass

    async def close_thread(self, thread_id: str):
        now = datetime.utcnow()
        await self._active.delete_one({"thread_id": thread_id})
        await self._audit.update_many({"thread_id": thread_id}, {"$set": {"closed_at": now}})


@singleton_factory
def get_memory_manager() -> MemoryManager:
    return MemoryManager() 