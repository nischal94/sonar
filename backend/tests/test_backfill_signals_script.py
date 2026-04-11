import pytest
import uuid
from sqlalchemy import select
from unittest.mock import AsyncMock
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.signal import Signal


@pytest.mark.asyncio
async def test_backfill_creates_signals_from_capability_profile_keywords(
    db_session, monkeypatch
):
    """Smoke test: given an active capability profile with signal_keywords,
    the backfill function creates one Signal row per keyword with a stored
    embedding."""
    ws = Workspace(id=uuid.uuid4(), name="WS Backfill", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=["data pipeline", "ETL migration", "ingest bottleneck"],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.commit()

    # Mock the embedding provider so the smoke test doesn't call OpenAI
    fake_embedding = [0.42] * 1536
    from app.services import embedding as emb_module
    monkeypatch.setattr(
        emb_module.embedding_provider,
        "embed",
        AsyncMock(return_value=fake_embedding),
    )

    # Drive the backfill directly against the test session. The script exposes
    # an `async def run(db)` helper precisely so tests don't need to stub out
    # engine creation/disposal.
    from scripts.backfill_signals_from_keywords import run as backfill_run

    result = await backfill_run(db_session)

    # Re-query on the same session — signals should now exist for this workspace
    signals_result = await db_session.execute(
        select(Signal).where(Signal.workspace_id == ws.id)
    )
    signals = signals_result.scalars().all()
    phrases = sorted(s.phrase for s in signals)
    assert phrases == ["ETL migration", "data pipeline", "ingest bottleneck"]
    assert result == {"created": 3, "skipped_profiles": 0}
