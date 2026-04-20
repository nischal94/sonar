"""Pipeline branches on workspace.use_hybrid_scoring.

Case A: flag=False → existing compute_combined_score path; post stored with
relationship/timing/combined scores, no fit_score on the connection.

Case B: flag=True → hybrid path; post's combined_score = fit_score * intent_score
(where fit_score comes from connection.fit_score and intent_score from
relevance + timing), connection.fit_score is populated if null.
"""

import pytest
from sqlalchemy import select

from app.models.connection import Connection
from app.models.post import Post


@pytest.mark.asyncio
async def test_pipeline_legacy_path_when_flag_false(
    db_session, pipeline_setup, monkeypatch
):
    """flag=False: uses compute_combined_score (existing behavior)."""
    workspace_id, post_id, connection_id = await pipeline_setup(use_hybrid=False)

    # Redirect the pipeline's engine to sonar_test (same DB the fixture used).
    from app.config import get_settings
    from app.services import embedding as emb_module

    settings = get_settings()
    base_url = settings.database_url
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    monkeypatch.setattr(settings, "database_url", test_db_url)

    dummy_emb = [0.1] * 1536

    async def fake_embed(text_in):
        return dummy_emb

    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

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

    from app.delivery import router as router_mod

    class NoopRouter:
        async def deliver(self, **kwargs):
            pass

    monkeypatch.setattr(router_mod, "DeliveryRouter", lambda: NoopRouter())

    from app.workers.pipeline import _run_pipeline

    await _run_pipeline(post_id, workspace_id)

    post = (
        await db_session.execute(select(Post).where(Post.id == post_id))
    ).scalar_one()
    await db_session.refresh(post)

    conn = (
        await db_session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
    ).scalar_one()
    await db_session.refresh(conn)

    assert post.combined_score is not None
    assert post.relationship_score is not None
    # Legacy path does not populate fit_score on the connection
    assert conn.fit_score is None


@pytest.mark.asyncio
async def test_pipeline_hybrid_path_when_flag_true(
    db_session, pipeline_setup, monkeypatch
):
    """flag=True: uses compute_hybrid_score. Stores fit_score on the connection."""
    workspace_id, post_id, connection_id = await pipeline_setup(use_hybrid=True)

    # Redirect the pipeline's engine to sonar_test (same DB the fixture used).
    from app.config import get_settings
    from app.services import embedding as emb_module

    settings = get_settings()
    base_url = settings.database_url
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    monkeypatch.setattr(settings, "database_url", test_db_url)

    dummy_emb = [0.1] * 1536

    async def fake_embed(text_in):
        return dummy_emb

    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

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

    from app.delivery import router as router_mod

    class NoopRouter:
        async def deliver(self, **kwargs):
            pass

    monkeypatch.setattr(router_mod, "DeliveryRouter", lambda: NoopRouter())

    from app.workers.pipeline import _run_pipeline

    await _run_pipeline(post_id, workspace_id)

    post = (
        await db_session.execute(select(Post).where(Post.id == post_id))
    ).scalar_one()
    await db_session.refresh(post)

    conn = (
        await db_session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
    ).scalar_one()
    await db_session.refresh(conn)

    # Hybrid path: combined_score = fit * intent
    assert post.combined_score is not None
    assert 0.0 <= post.combined_score <= 1.0
    assert conn.fit_score is not None
    assert 0.0 <= conn.fit_score <= 1.0
