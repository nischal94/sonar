"""Incremental aggregation task for the dashboard Ranked People List.

Chains to the end of pipeline.py (see Task 2). For every scored post, updates
the person_signal_summary row for the post's author so the dashboard list
reflects the new signal within ~100 ms of scoring. Target runtime per call:
<100 ms (design.md §5.2).

Call shape is a pure function that takes a db_session so tests can assert
against the same transaction; the Celery wrapper is a thin delegate.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.person_signal_summary import PersonSignalSummary
from app.models.post import Post


async def update_person_aggregation(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    connection_id: UUID,
    post_id: UUID,
    signal_id: UUID | None,
    combined_score: float,
) -> None:
    """Upsert the PersonSignalSummary for this connection + recompute trend.

    NO-OP if signal_id is None — aggregation tracks matched signals only.
    """
    if signal_id is None:
        return

    result = await db.execute(
        select(PersonSignalSummary).where(
            and_(
                PersonSignalSummary.workspace_id == workspace_id,
                PersonSignalSummary.connection_id == connection_id,
            )
        )
    )
    summary = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if summary is None:
        summary = PersonSignalSummary(
            workspace_id=workspace_id,
            connection_id=connection_id,
            aggregate_score=combined_score,
            trend_direction=await _trend_direction(
                db, workspace_id, connection_id, now
            ),
            last_signal_at=now,
            recent_post_id=post_id,
            recent_signal_id=signal_id,
        )
        db.add(summary)
    else:
        # MVP: replace score with latest. Rolling-avg is follow-up polish.
        summary.aggregate_score = combined_score
        summary.last_signal_at = now
        summary.recent_post_id = post_id
        summary.recent_signal_id = signal_id
        summary.trend_direction = await _trend_direction(
            db, workspace_id, connection_id, now
        )
        summary.updated_at = now


async def _trend_direction(
    db: AsyncSession,
    workspace_id: UUID,
    connection_id: UUID,
    now: datetime,
) -> str:
    """Compare matched-post counts for this week vs last week → up / flat / down.

    Uses COALESCE(posted_at, ingested_at) for the window filter — Apify-backfilled
    posts sometimes have null posted_at. Without the coalesce, such posts would
    be silently excluded from trend counts and prolific-but-backfilled people
    would read as `flat` forever.
    """
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    # Coalesce ensures posts with null posted_at still contribute to the window.
    post_ts = func.coalesce(Post.posted_at, Post.ingested_at)

    this_week = await db.execute(
        select(func.count())
        .select_from(Post)
        .where(
            and_(
                Post.workspace_id == workspace_id,
                Post.connection_id == connection_id,
                Post.matched.is_(True),
                post_ts >= this_week_start,
            )
        )
    )
    last_week = await db.execute(
        select(func.count())
        .select_from(Post)
        .where(
            and_(
                Post.workspace_id == workspace_id,
                Post.connection_id == connection_id,
                Post.matched.is_(True),
                post_ts >= last_week_start,
                post_ts < this_week_start,
            )
        )
    )
    this_week_count = this_week.scalar_one()
    last_week_count = last_week.scalar_one()

    if this_week_count > last_week_count:
        return "up"
    if this_week_count < last_week_count:
        return "down"
    return "flat"
