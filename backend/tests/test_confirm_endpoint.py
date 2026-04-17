import pytest
import json
from uuid import UUID
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.signal import Signal


class FakeLLM:
    async def complete(self, prompt: str, model: str) -> str:
        return json.dumps(
            {
                "signals": [
                    {
                        "phrase": f"phrase {i}",
                        "example_post": f"ex {i} body here",
                        "intent_strength": 0.5,
                    }
                    for i in range(8)
                ]
            }
        )


class FakeEmbed:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_confirm_persists_accepted_and_user_added_signals(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post(
        "/workspace/register",
        json={"workspace_name": "W", "email": "c@c.com", "password": "pass123"},
    )
    tok = (
        await client.post(
            "/auth/token", data={"username": "c@c.com", "password": "pass123"}
        )
    ).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    propose = (
        await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "X services"},
            headers=hdrs,
        )
    ).json()
    event_id = propose["proposal_event_id"]

    resp = await client.post(
        "/workspace/signals/confirm",
        json={
            "proposal_event_id": event_id,
            "accepted": [0, 1, 2],
            "edited": [
                {
                    "proposed_idx": 3,
                    "final_phrase": "my edit",
                    "final_example_post": "post body text",
                    "final_intent_strength": 0.7,
                }
            ],
            "rejected": [4, 5, 6, 7],
            "user_added": [
                {
                    "phrase": "custom one",
                    "example_post": "body body text",
                    "intent_strength": 0.8,
                }
            ],
        },
        headers=hdrs,
    )
    assert resp.status_code == 200
    body = resp.json()
    # 3 accepted + 1 edited + 1 user_added = 5 signals persisted
    assert len(body["signal_ids"]) == 5
    assert body["profile_active"] is True

    # Telemetry event is marked completed
    result = await db_session.execute(
        select(SignalProposalEvent).where(SignalProposalEvent.id == UUID(event_id))
    )
    row = result.scalar_one()
    assert row.completed_at is not None
    assert row.accepted_ids == ["0", "1", "2"]
    assert row.rejected_ids == ["4", "5", "6", "7"]
    assert len(row.edited_pairs) == 1
    assert len(row.user_added) == 1

    # Signal rows exist with embeddings populated
    sig_result = await db_session.execute(select(Signal))
    sigs = sig_result.scalars().all()
    assert len(sigs) == 5
    assert all(s.embedding is not None and len(list(s.embedding)) == 1536 for s in sigs)

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.mark.asyncio
async def test_confirm_rejects_mismatched_workspace(client, db_session):
    """A user in one workspace cannot confirm another workspace's proposal."""
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post(
        "/workspace/register",
        json={"workspace_name": "A", "email": "d@d.com", "password": "pass123"},
    )
    tokA = (
        await client.post(
            "/auth/token", data={"username": "d@d.com", "password": "pass123"}
        )
    ).json()["access_token"]
    proposeA = (
        await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "X services"},
            headers={"Authorization": f"Bearer {tokA}"},
        )
    ).json()

    await client.post(
        "/workspace/register",
        json={"workspace_name": "B", "email": "e@e.com", "password": "pass123"},
    )
    tokB = (
        await client.post(
            "/auth/token", data={"username": "e@e.com", "password": "pass123"}
        )
    ).json()["access_token"]

    resp = await client.post(
        "/workspace/signals/confirm",
        json={"proposal_event_id": proposeA["proposal_event_id"], "accepted": [0]},
        headers={"Authorization": f"Bearer {tokB}"},
    )
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
