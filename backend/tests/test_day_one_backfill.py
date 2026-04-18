import pytest
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.post import Post
from app.workers.day_one_backfill import run_day_one_backfill
from tests.test_apify_service import FakeApify


async def _seed_workspace_with_connections(db_session, n_connections: int = 3):
    ws = Workspace(name="Backfill WS")
    db_session.add(ws)
    await db_session.flush()
    user = User(workspace_id=ws.id, email="x@x.com", hashed_password="x", role="owner")
    db_session.add(user)
    await db_session.flush()
    for i in range(n_connections):
        db_session.add(
            Connection(
                workspace_id=ws.id,
                user_id=user.id,
                linkedin_id=f"li-{i}",
                name=f"Conn {i}",
                profile_url=f"https://linkedin.com/in/conn-{i}",
                degree=1,
            )
        )
    await db_session.commit()
    return ws


@pytest.mark.asyncio
async def test_run_day_one_backfill_ingests_posts_and_marks_complete(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=3)
    fake_apify = FakeApify(posts_per_profile=2)

    await run_day_one_backfill(db_session, workspace_id=ws.id, apify=fake_apify)
    await db_session.commit()

    # Apify called once with all 3 profile URLs + 60-day window
    assert len(fake_apify.calls) == 1
    assert len(fake_apify.calls[0]["profile_urls"]) == 3
    assert fake_apify.calls[0]["days"] == 60

    # 3 connections × 2 posts = 6 Post rows
    posts = (await db_session.execute(select(Post))).scalars().all()
    assert len(posts) == 6

    # Workspace bookkeeping updated
    reloaded = (
        await db_session.execute(select(Workspace).where(Workspace.id == ws.id))
    ).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None
    assert reloaded.backfill_completed_at is not None
    assert reloaded.backfill_profile_count == 3


@pytest.mark.asyncio
async def test_run_day_one_backfill_caps_at_200_profiles(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=250)
    fake_apify = FakeApify(posts_per_profile=1)

    await run_day_one_backfill(db_session, workspace_id=ws.id, apify=fake_apify)
    await db_session.commit()

    # Only 200 profile URLs forwarded
    assert len(fake_apify.calls[0]["profile_urls"]) == 200

    reloaded = (
        await db_session.execute(select(Workspace).where(Workspace.id == ws.id))
    ).scalar_one()
    assert reloaded.backfill_profile_count == 200


@pytest.mark.asyncio
async def test_run_day_one_backfill_is_idempotent(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=2)
    ws.backfill_used = True  # already backfilled
    await db_session.commit()

    fake_apify = FakeApify(posts_per_profile=2)
    with pytest.raises(ValueError, match="already backfilled"):
        await run_day_one_backfill(db_session, workspace_id=ws.id, apify=fake_apify)
    # Apify was NOT called
    assert fake_apify.calls == []
