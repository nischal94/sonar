import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

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
