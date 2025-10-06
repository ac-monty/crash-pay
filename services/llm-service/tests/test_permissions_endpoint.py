import jwt
import pytest
from httpx import AsyncClient
from app.main import app
from app.auth.models import JWTPayload
from datetime import datetime, timedelta

JWT_SECRET = "super-secret-not-safe"

@pytest.mark.asyncio
async def test_permissions_resolution_endpoint():
    """Call /api/v1/permissions/resolve with a fake JWT and ensure list is returned."""
    # Build token without fxn claim so service calculates permissions
    exp = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())
    payload = {
        "sub": "test-user",
        "scope": "banking:read banking:write transfers:create",
        "roles": ["customer"],
        "exp": exp,
        "iat": int(datetime.utcnow().timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/permissions/resolve",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "test-user"
    # Should include at least one permitted function
    assert len(data["permitted_functions"]) > 0 