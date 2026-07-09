"""Integration test: backfill script populates fit_score for every connection."""

import pytest
from sqlalchemy import select

from app.models.connection import Connection


@pytest.mark.asyncio
async def test_backfill_populates_fit_score_for_all_connections(
    db_session,
    workspace_with_icp,
    seeded_connections,
):
    from scripts.backfill_fit_scores import run

    # Override the embedding provider to avoid real OpenAI calls.
    from app.services import embedding as emb_mod

    class _FakeProvider:
        async def embed(self, text: str) -> list[float]:
            return [0.2] * 1536

    emb_mod._provider = _FakeProvider()

    summary = await run(db_session, workspace_id=workspace_with_icp.id)

    assert summary["updated"] == 3
    conns = (
        (
            await db_session.execute(
                select(Connection).where(
                    Connection.workspace_id == workspace_with_icp.id
                )
            )
        )
        .scalars()
        .all()
    )
    for c in conns:
        assert c.fit_score is not None
        assert 0.0 <= c.fit_score <= 1.0


@pytest.mark.asyncio
async def test_backfill_skips_connections_with_existing_fit_score(
    db_session,
    workspace_with_icp,
    seeded_connections_mixed,
):
    """Default mode skips connections that already have a fit_score."""
    from scripts.backfill_fit_scores import run
    from app.services import embedding as emb_mod

    class _FakeProvider:
        async def embed(self, text: str) -> list[float]:
            return [0.2] * 1536

    emb_mod._provider = _FakeProvider()

    summary = await run(
        db_session, workspace_id=workspace_with_icp.id, recompute_all=False
    )
    assert summary["updated"] == 2  # the two with fit_score=None
