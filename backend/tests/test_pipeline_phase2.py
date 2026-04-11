import pytest
import uuid
from sqlalchemy import text, select
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.user import User
from app.models.connection import Connection
from app.models.post import Post
from app.models.signal import Signal


@pytest.mark.asyncio
async def test_pipeline_persists_embedding_and_ring_matches(db_session, monkeypatch):
    """Integration test: a post with a Ring 1 keyword match flows through
    the refactored pipeline and persists embedding + ring1_matches without
    being dropped by a keyword-filter gate."""
    from app.workers import pipeline as pipeline_module
    from app.services import embedding as emb_module
    from app.config import get_settings

    # The pipeline creates its own engine from settings.database_url (points at
    # the `sonar` DB). The test fixture writes to the `sonar_test` DB. Redirect
    # the cached Settings instance so the pipeline uses the same DB the test
    # has been writing to.
    settings = get_settings()
    base_url = settings.database_url
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    monkeypatch.setattr(settings, "database_url", test_db_url)

    # Seed workspace + active profile
    ws = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter", matching_threshold=0.1)
    db_session.add(ws)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(), workspace_id=ws.id, email="u@t.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=["data pipeline"],
        anti_keywords=[],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    # Raw SQL to set capability_profile_versions.embedding (pgvector)
    dummy_emb = [0.5] * 1536
    emb_str = "[" + ",".join(str(x) for x in dummy_emb) + "]"
    await db_session.execute(
        text("UPDATE capability_profile_versions SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(profile.id)},
    )

    # Signal for Ring 1 match
    signal = Signal(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        profile_version_id=profile.id,
        phrase="data pipeline",
        intent_strength=0.8,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(signal.id)},
    )

    conn = Connection(
        id=uuid.uuid4(), workspace_id=ws.id, user_id=user.id,
        linkedin_id="ln-1", name="Alice", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        connection_id=conn.id,
        linkedin_post_id="ln-p-1",
        content="Our data pipeline broke again and it cost us a day.",
        post_type="post",
        source="extension",
    )
    db_session.add(post)
    await db_session.commit()

    # Monkey-patch the embedding provider to return a deterministic vector
    async def fake_embed(text_in):
        return dummy_emb
    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

    # Monkey-patch context_generator to avoid real LLM calls
    from app.services import context_generator as ctx_mod
    async def fake_ctx(**kwargs):
        return ctx_mod.AlertContext(
            match_reason="test match",
            outreach_draft_a="test a",
            outreach_draft_b="test b",
            opportunity_type="product_pain",
            urgency_reason="test urgency",
            themes=["data tooling"],
        )
    monkeypatch.setattr(ctx_mod, "generate_alert_context", fake_ctx)

    # Monkey-patch DeliveryRouter to be a no-op
    from app.delivery import router as router_mod
    class NoopRouter:
        async def deliver(self, **kwargs): pass
    monkeypatch.setattr(router_mod, "DeliveryRouter", lambda: NoopRouter())

    # Run the pipeline directly (not as celery task)
    await pipeline_module._run_pipeline(post.id, ws.id)

    # Re-fetch post and verify
    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    await db_session.refresh(loaded)
    assert loaded.processed_at is not None
    assert loaded.matched is True
    assert loaded.ring1_matches == [str(signal.id)]
    assert len(loaded.ring2_matches) >= 1
    assert "data tooling" in (loaded.themes or [])
