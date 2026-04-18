import pytest
import json
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.connection import Connection
from app.models.user import User
from app.models.signal import Signal
from app.models.post import Post
from app.workers.incremental_trending import update_person_aggregation


class FakeLLM:
    async def complete(self, prompt, model, **kwargs):
        return json.dumps(
            {
                "signals": [
                    {
                        "phrase": "hiring struggles",
                        "example_post": "still interviewing body",
                        "intent_strength": 0.8,
                    },
                    {
                        "phrase": "fundraising mode",
                        "example_post": "raising a Series A body",
                        "intent_strength": 0.7,
                    },
                    {
                        "phrase": "infra pain",
                        "example_post": "legacy ETL bottlenecks body",
                        "intent_strength": 0.7,
                    },
                    {
                        "phrase": "team scaling",
                        "example_post": "hiring plan this quarter body",
                        "intent_strength": 0.6,
                    },
                    {
                        "phrase": "tech debt",
                        "example_post": "refactoring payments body",
                        "intent_strength": 0.6,
                    },
                    {
                        "phrase": "migration pain",
                        "example_post": "moving off legacy stack body",
                        "intent_strength": 0.6,
                    },
                    {
                        "phrase": "compliance ask",
                        "example_post": "SOC2 prep this year body",
                        "intent_strength": 0.5,
                    },
                    {
                        "phrase": "tooling chaos",
                        "example_post": "too many SaaS tools body",
                        "intent_strength": 0.5,
                    },
                ]
            }
        )


class FakeEmbed:
    async def embed(self, text):
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_full_flow_register_wizard_pipeline_dashboard(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "End-to-End Agency",
            "email": "e2e@dash.com",
            "password": "pass123",
        },
    )
    tok = (
        await client.post(
            "/auth/token",
            data={"username": "e2e@dash.com", "password": "pass123"},
        )
    ).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    # Complete the wizard
    propose = (
        await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "CTO services"},
            headers=hdrs,
        )
    ).json()
    confirm = (
        await client.post(
            "/workspace/signals/confirm",
            json={
                "proposal_event_id": propose["proposal_event_id"],
                "accepted": [0, 1, 2],
            },
            headers=hdrs,
        )
    ).json()
    assert len(confirm["signal_ids"]) == 3

    # Now seed a connection + scored post, and invoke the aggregation
    # directly (Celery chain would do this in prod — simulating here).
    user = (
        await db_session.execute(select(User).where(User.email == "e2e@dash.com"))
    ).scalar_one()
    first_signal = (
        await db_session.execute(
            select(Signal).where(Signal.workspace_id == user.workspace_id).limit(1)
        )
    ).scalar_one()
    conn = Connection(
        workspace_id=user.workspace_id,
        user_id=user.id,
        linkedin_id="li-e2e",
        name="Dashboard Test Person",
        headline="CTO",
        company="TestCo",
        degree=1,
    )
    db_session.add(conn)
    await db_session.flush()
    post = Post(
        workspace_id=user.workspace_id,
        connection_id=conn.id,
        linkedin_post_id="e2e-post-1",
        content="We've been interviewing senior engineers for 4 months.",
        post_type="text",
        source="feed",
        combined_score=0.88,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=user.workspace_id,
        connection_id=conn.id,
        post_id=post.id,
        signal_id=first_signal.id,
        combined_score=0.88,
    )
    await db_session.commit()

    resp = await client.get("/workspace/dashboard/people", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    row = body["people"][0]
    assert row["name"] == "Dashboard Test Person"
    assert row["aggregate_score"] == pytest.approx(0.88)
    assert row["recent_post_snippet"].startswith("We've been interviewing")

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
