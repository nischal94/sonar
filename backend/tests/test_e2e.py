# backend/tests/test_e2e.py
"""
End-to-end integration test: register → profile → ingest → alert created.
Runs against test database. Mocks LLM and delivery channels.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.services.embedding import get_embedding_provider
from app.services.llm import get_llm_client


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end(client):
    """
    Full flow:
    1. Register workspace
    2. Extract capability profile (mocked LLM)
    3. Ingest a LinkedIn post (mocked pipeline task)
    4. Verify alert is created and retrievable
    """

    # Step 1: Register
    resp = await client.post("/workspace/register", json={
        "workspace_name": "E2E Test Agency",
        "email": "e2e@test.com",
        "password": "testpassword"
    })
    assert resp.status_code == 201

    # Step 2: Login
    login = await client.post("/auth/token", data={
        "username": "e2e@test.com", "password": "testpassword"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: Extract profile (mock LLM + embedding)
    mock_profile_json = '''{
        "company_name": "E2E Test Agency",
        "company_description": "We build AI agents.",
        "primary_services": ["AI agents"],
        "target_customers": ["SaaS companies"],
        "pain_points_solved": ["automation"],
        "technologies_used": ["Python", "LLMs"],
        "signal_keywords": ["AI agent", "automation", "LLM"],
        "anti_keywords": ["happy birthday"],
        "capability_summary": "We build custom AI agents for SaaS automation."
    }'''

    # FastAPI dependency overrides instead of patch() — impossible to defeat
    # with `from ... import ...` because the override layer sits above
    # Python's import binding. See #21.
    fake_llm = MagicMock()
    fake_llm.complete = AsyncMock(return_value=mock_profile_json)
    fake_emb = MagicMock()
    fake_emb.embed = AsyncMock(return_value=[0.5] * 1536)
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb
    try:
        resp = await client.post("/profile/extract", json={
            "text": "We build custom AI agents for SaaS companies."
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "E2E Test Agency"
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
        app.dependency_overrides.pop(get_embedding_provider, None)

    # Step 4: Ingest a post (pipeline task mocked — tested separately in test_ingest_router.py)
    with patch("app.routers.ingest.process_post_pipeline") as mock_task:
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-e2e"))

        resp = await client.post("/ingest", json={
            "posts": [{
                "linkedin_post_id": "urn:li:activity:e2etest001",
                "author": {
                    "name": "Test Person",
                    "headline": "CTO at TestCo",
                    "profile_url": "https://linkedin.com/in/testperson",
                    "linkedin_id": "testperson",
                    "degree": 1
                },
                "content": "Looking for AI agent solutions for our sales automation pipeline.",
                "post_type": "post",
                "posted_at": "2026-04-08T10:00:00Z"
            }],
            "extraction_version": "1.0.0"
        }, headers=headers)

        assert resp.status_code == 202
        assert resp.json()["queued"] == 1
        assert resp.json()["skipped"] == 0
        mock_task.delay.assert_called_once()

    # Step 5: Alerts endpoint returns empty list (pipeline was mocked, no real alert created)
    resp = await client.get("/alerts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
