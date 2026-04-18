import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_workspace_has_backfill_bookkeeping_columns(db_session):
    ws = Workspace(name="Backfill Test")
    db_session.add(ws)
    await db_session.commit()

    # Defaults
    assert ws.backfill_used is False
    assert ws.backfill_started_at is None
    assert ws.backfill_completed_at is None
    assert ws.backfill_profile_count == 0

    # Set them
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    ws.backfill_completed_at = now
    ws.backfill_profile_count = 127
    await db_session.commit()

    reloaded = (
        await db_session.execute(select(Workspace).where(Workspace.id == ws.id))
    ).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None
    assert reloaded.backfill_profile_count == 127
