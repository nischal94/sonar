import pytest


@pytest.mark.asyncio
async def test_alerts_endpoint_returns_empty_list(client):
    await client.post("/workspace/register", json={
        "workspace_name": "Alerts Test", "email": "test@alerts.com", "password": "pass123"
    })
    login = await client.post("/auth/token", data={"username": "test@alerts.com", "password": "pass123"})
    token = login.json()["access_token"]

    resp = await client.get("/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []
