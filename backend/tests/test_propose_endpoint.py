import pytest
import json
from uuid import UUID
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.models.signal_proposal_event import SignalProposalEvent


class FakeLLM:
    """Test double. Returns a fixed 8-signal JSON payload."""

    def __init__(self, payload: str | None = None):
        self.payload = payload or json.dumps(
            {
                "signals": [
                    {
                        "phrase": f"phrase {i}",
                        "example_post": f"example post {i} body",
                        "intent_strength": 0.5,
                    }
                    for i in range(8)
                ]
            }
        )
        self.calls = 0

    async def complete(self, prompt: str, model: str) -> str:
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_propose_returns_8_signals_and_logs_partial_telemetry(client, db_session):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake

    # Register a workspace + login to get a JWT
    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "WS",
            "email": "a@a.com",
            "password": "pass123",
        },
    )
    tok = (
        await client.post(
            "/auth/token", data={"username": "a@a.com", "password": "pass123"}
        )
    ).json()["access_token"]

    resp = await client.post(
        "/workspace/signals/propose",
        json={
            "what_you_sell": "Fractional CTO services",
            "icp": "CEOs at small startups",
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["signals"]) == 8
    assert body["prompt_version"] == "v1"
    proposal_event_id = UUID(body["proposal_event_id"])

    # Telemetry row is written with completed_at still NULL
    result = await db_session.execute(
        select(SignalProposalEvent).where(SignalProposalEvent.id == proposal_event_id)
    )
    row = result.scalar_one()
    assert row.prompt_version == "v1"
    assert row.what_you_sell.startswith("Fractional CTO")
    assert row.icp == "CEOs at small startups"
    assert len(row.proposed) == 8
    assert row.completed_at is None
    assert fake.calls == 1

    app.dependency_overrides.pop(get_llm_client, None)


@pytest.mark.asyncio
async def test_propose_rejects_unauthenticated(client):
    resp = await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "x"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_propose_validates_minimum_input_length(client, db_session):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    await client.post(
        "/workspace/register",
        json={"workspace_name": "W", "email": "b@b.com", "password": "pass123"},
    )
    tok = (
        await client.post(
            "/auth/token", data={"username": "b@b.com", "password": "pass123"}
        )
    ).json()["access_token"]
    # 'hi' is 2 chars, below min_length=5
    resp = await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "hi"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 422
    app.dependency_overrides.pop(get_llm_client, None)
