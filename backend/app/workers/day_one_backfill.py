"""Day-One Backfill Celery task.

Called once per workspace after the wizard completes + the extension
captures the user's connection list. Runs an Apify 1st-degree scrape,
ingests the resulting posts through the existing pipeline.

Caps: 200 connections × 60 days per workspace (see
docs/phase-2/backfill-decisions.md §4).
"""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection import Connection
from app.models.post import Post
from app.models.workspace import Workspace
from app.services.apify import ApifyService

MAX_CONNECTIONS = 200
DAYS_BACK = 60


async def run_day_one_backfill(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    apify: ApifyService,
) -> int:
    """Run backfill for one workspace. Returns the number of profiles scraped.

    Raises ValueError if the workspace has already been backfilled.
    """
    ws = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if ws is None:
        raise ValueError(f"workspace {workspace_id} not found")
    if ws.backfill_used:
        raise ValueError(f"workspace {workspace_id} already backfilled")

    # Mark started + consumed FIRST — prevents double-enqueue on retry.
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db.flush()

    # Pick up to 200 connections, ordered by first_seen_at DESC.
    conns = (
        (
            await db.execute(
                select(Connection)
                .where(Connection.workspace_id == workspace_id)
                .where(Connection.degree == 1)
                .order_by(Connection.first_seen_at.desc())
                .limit(MAX_CONNECTIONS)
            )
        )
        .scalars()
        .all()
    )
    profile_urls = [c.profile_url for c in conns if c.profile_url]
    conn_by_url = {c.profile_url: c for c in conns if c.profile_url}

    # Scrape via Apify
    posts = await apify.scrape_profile_posts(profile_urls=profile_urls, days=DAYS_BACK)

    # Ingest each post (simplified — in prod this would dispatch to the
    # pipeline Celery task; for MVP we insert Post rows directly so the
    # existing pipeline picks them up on its next sweep).
    for p in posts:
        conn = conn_by_url.get(p.profile_url)
        if conn is None:
            continue
        db.add(
            Post(
                workspace_id=workspace_id,
                connection_id=conn.id,
                linkedin_post_id=p.linkedin_post_id,
                content=p.content,
                post_type="text",
                source="backfill",
                posted_at=p.posted_at,
                engagement_counts={
                    "reactions": p.reaction_count,
                    "comments": p.comment_count,
                    "shares": p.share_count,
                },
            )
        )

    ws.backfill_completed_at = datetime.now(timezone.utc)
    ws.backfill_profile_count = len(profile_urls)
    await db.flush()
    return len(profile_urls)
