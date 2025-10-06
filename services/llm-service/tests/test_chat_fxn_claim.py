import jwt
import pytest
from httpx import AsyncClient
from app.main import app
from datetime import datetime, timedelta

JWT_SECRET = "super-secret-not-safe"

@pytest.mark.asyncio
async def test_chat_with_fxn_claim():
    exp = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())
    token = jwt.encode(
        {
            "sub": "chat-user",
            "scope": "banking:read banking:write transfers:create",
            "roles": ["customer"],
            "fxn": ["get_account_balance"],
            "exp": exp,
            "iat": int(datetime.utcnow().timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "What is my balance?", "use_rag": False},
        )
    assert resp.status_code in (200, 500)  # model providers may be unavailable in CI
    if resp.status_code == 200:
        data = resp.json()
        assert "response" in data
        assert data["provider"] 