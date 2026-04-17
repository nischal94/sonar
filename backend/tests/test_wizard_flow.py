import pytest
import json
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.signal import Signal
from app.models.signal_proposal_event import SignalProposalEvent


class FakeLLM:
    async def complete(self, prompt: str, model: str, **kwargs) -> str:
        return json.dumps(
            {
                "signals": [
                    {
                        "phrase": f"signal {i}",
                        "example_post": f"post body {i} here text",
                        "intent_strength": 0.5 + i * 0.01,
                    }
                    for i in range(9)
                ]
            }
        )


class FakeEmbed:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_happy_path_register_propose_confirm(client, db_session):
    """End-to-end: a new user registers, logs in, calls propose, confirms all
    9 proposed signals verbatim, and ends up with 9 Signal rows + 1 completed
    SignalProposalEvent."""
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "Happy Path Agency",
            "email": "happy@path.com",
            "password": "pass123",
        },
    )
    tok = (
        await client.post(
            "/auth/token", data={"username": "happy@path.com", "password": "pass123"}
        )
    ).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    propose = (
        await client.post(
            "/workspace/signals/propose",
            json={
                "what_you_sell": "Fractional CTO services for Series A-B SaaS startups",
                "icp": "CEOs and VPs Eng at 20-50 person startups",
            },
            headers=hdrs,
        )
    ).json()
    assert len(propose["signals"]) == 9

    confirm = (
        await client.post(
            "/workspace/signals/confirm",
            json={
                "proposal_event_id": propose["proposal_event_id"],
                "accepted": list(range(9)),
            },
            headers=hdrs,
        )
    ).json()
    assert len(confirm["signal_ids"]) == 9
    assert confirm["profile_active"] is True

    sigs = (await db_session.execute(select(Signal))).scalars().all()
    assert len(sigs) == 9
    assert all(s.enabled for s in sigs)
    assert all(s.embedding is not None for s in sigs)

    ev_result = await db_session.execute(select(SignalProposalEvent))
    ev = ev_result.scalar_one()
    assert ev.completed_at is not None
    assert ev.prompt_version == "v1"

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
