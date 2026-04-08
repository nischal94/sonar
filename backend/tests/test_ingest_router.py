import pytest
from unittest.mock import patch, MagicMock
from app.schemas.ingest import PostIngestPayload, PostAuthor

@pytest.mark.asyncio
async def test_ingest_endpoint_accepts_valid_payload(client):
    await client.post("/workspace/register", json={
        "workspace_name": "Test Agency", "email": "test@ingest.com", "password": "pass123"
    })
    login = await client.post("/auth/token", data={"username": "test@ingest.com", "password": "pass123"})
    token = login.json()["access_token"]

    payload = {
        "posts": [{
            "linkedin_post_id": "urn:li:activity:111222333",
            "author": {
                "name": "Jane Doe",
                "headline": "CTO at StartupX",
                "profile_url": "https://linkedin.com/in/janedoe",
                "linkedin_id": "janedoe123",
                "degree": 1
            },
            "content": "We are evaluating AI agent frameworks for our product team.",
            "post_type": "post",
            "posted_at": "2026-04-08T09:00:00Z",
            "engagement": {"likes": 12, "comments": 3}
        }],
        "extraction_version": "1.0.0"
    }

    with patch("app.routers.ingest.process_post_pipeline") as mock_task:
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-123"))
        resp = await client.post(
            "/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )

    assert resp.status_code == 202
    assert resp.json()["queued"] == 1
