import pytest
import jwt
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import get_settings

ALGORITHM = "HS256"


@pytest.mark.asyncio
async def test_register_and_login(client):
    resp = await client.post("/workspace/register", json={
        "workspace_name": "Test Agency",
        "email": "owner@test.com",
        "password": "testpassword123"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "workspace_id" in data

    resp = await client.post("/auth/token", data={
        "username": "owner@test.com",
        "password": "testpassword123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_get_current_user_rejects_token_missing_sub(client):
    """Regression test for issue #7: JWT decode must explicitly require
    `sub` via options={"require": [...]} so missing claims fail loudly
    with a PyJWTError instead of sneaking through as a silent KeyError."""
    secret = get_settings().secret_key
    token_without_sub = jwt.encode(
        {
            # No "sub" claim on purpose
            "workspace_id": str(uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        secret,
        algorithm=ALGORITHM,
    )
    resp = await client.patch(
        "/workspace/channels",
        headers={"Authorization": f"Bearer {token_without_sub}"},
        json={"delivery_channels": {}},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_token_missing_exp(client):
    """Regression test for issue #7: JWT decode must explicitly require
    `exp` so tokens without an expiry are rejected at decode time."""
    secret = get_settings().secret_key
    token_without_exp = jwt.encode(
        {
            "sub": str(uuid4()),
            "workspace_id": str(uuid4()),
            # No "exp" claim on purpose
        },
        secret,
        algorithm=ALGORITHM,
    )
    resp = await client.patch(
        "/workspace/channels",
        headers={"Authorization": f"Bearer {token_without_exp}"},
        json={"delivery_channels": {}},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"
