import pytest
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.signal import Signal
from app.models.post import Post
from app.models.person_signal_summary import PersonSignalSummary
from app.workers import pipeline as pipeline_module


@pytest.mark.asyncio
async def test_pipeline_populates_person_signal_summary(db_session):
    """After scoring, pipeline must call update_person_aggregation so the
    dashboard's PersonSignalSummary stays fresh within ~100 ms (design §5.2)."""
    workspace = Workspace(name="WS")
    db_session.add(workspace)
    await db_session.flush()
    user = User(
        workspace_id=workspace.id,
        email="x@x.com",
        hashed_password="x",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    conn = Connection(
        workspace_id=workspace.id,
        user_id=user.id,
        linkedin_id="li-1",
        name="Jane",
        degree=1,
    )
    db_session.add(conn)
    await db_session.flush()
    signal = Signal(
        workspace_id=workspace.id,
        phrase="struggling to hire",
        example_post="example body text",
        intent_strength=0.7,
        embedding=[0.0] * 1536,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    post = Post(
        workspace_id=workspace.id,
        connection_id=conn.id,
        linkedin_post_id="p-1",
        content="we've been interviewing",
        post_type="text",
        source="feed",
        combined_score=0.85,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await pipeline_module.run_dashboard_aggregation_hook(
        db_session,
        post_id=post.id,
        signal_id=signal.id,
        combined_score=0.85,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    assert summary.aggregate_score == pytest.approx(0.85)
    assert summary.recent_post_id == post.id
    assert summary.recent_signal_id == signal.id
