import pytest
import uuid
from datetime import date
from sqlalchemy import select
from app.models.trend import Trend
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_ring1_trend(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    trend = Trend(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        ring=1,
        signal_id=None,
        this_week_count=12,
        last_week_count=3,
        velocity_delta=9,
        snapshot_date=date.today(),
    )
    db_session.add(trend)
    await db_session.commit()

    result = await db_session.execute(
        select(Trend).where(Trend.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.ring == 1
    assert loaded.velocity_delta == 9


@pytest.mark.asyncio
async def test_should_persist_ring3_trend_with_cluster_label(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS 2", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    trend = Trend(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        ring=3,
        cluster_label="migration pain",
        cluster_sample_posts=[{"id": "p1", "text": "our ETL broke"}],
        this_week_count=7,
        last_week_count=1,
        velocity_delta=6,
        snapshot_date=date.today(),
    )
    db_session.add(trend)
    await db_session.commit()

    result = await db_session.execute(
        select(Trend).where(Trend.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.ring == 3
    assert loaded.cluster_label == "migration pain"
    assert loaded.cluster_sample_posts[0]["text"] == "our ETL broke"
