import pytest
from sqlalchemy import select
from app.models.connection import Connection
from app.models.post import Post
from app.models.signal import Signal
from app.models.person_signal_summary import PersonSignalSummary
from app.models.workspace import Workspace
from app.models.user import User
from app.workers.incremental_trending import update_person_aggregation


async def _seed(db_session):
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
    return workspace, conn, signal


@pytest.mark.asyncio
async def test_update_creates_summary_if_missing(db_session):
    workspace, conn, signal = await _seed(db_session)
    post = Post(
        workspace_id=workspace.id,
        connection_id=conn.id,
        linkedin_post_id="p-1",
        content="we've been interviewing",
        post_type="text",
        source="feed",
        combined_score=0.82,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id,
        connection_id=conn.id,
        post_id=post.id,
        signal_id=signal.id,
        combined_score=0.82,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    assert summary.aggregate_score == pytest.approx(0.82)
    assert summary.recent_post_id == post.id
    assert summary.recent_signal_id == signal.id
    assert summary.trend_direction in {"up", "flat", "down"}


@pytest.mark.asyncio
async def test_update_bumps_existing_summary(db_session):
    workspace, conn, signal = await _seed(db_session)
    existing = PersonSignalSummary(
        workspace_id=workspace.id,
        connection_id=conn.id,
        aggregate_score=0.5,
        trend_direction="flat",
    )
    db_session.add(existing)

    post = Post(
        workspace_id=workspace.id,
        connection_id=conn.id,
        linkedin_post_id="p-2",
        content="hiring struggles",
        post_type="text",
        source="feed",
        combined_score=0.9,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id,
        connection_id=conn.id,
        post_id=post.id,
        signal_id=signal.id,
        combined_score=0.9,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    # New score replaces old (simple replacement strategy for MVP; rolling
    # average is follow-up polish).
    assert summary.aggregate_score == pytest.approx(0.9)
    assert summary.recent_post_id == post.id


@pytest.mark.asyncio
async def test_update_with_no_signal_match_is_noop(db_session):
    workspace, conn, _ = await _seed(db_session)
    post = Post(
        workspace_id=workspace.id,
        connection_id=conn.id,
        linkedin_post_id="p-3",
        content="random post",
        post_type="text",
        source="feed",
        combined_score=0.1,
        matched=False,
    )
    db_session.add(post)
    await db_session.commit()

    # signal_id=None means no signal matched; aggregation should NOT create a row
    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id,
        connection_id=conn.id,
        post_id=post.id,
        signal_id=None,
        combined_score=0.1,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    assert result.scalar_one_or_none() is None
