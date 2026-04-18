"""Day-One Backfill Celery task.

Called once per workspace after the wizard completes + the extension
captures the user's connection list. Runs an Apify 1st-degree scrape,
ingests the resulting posts through the existing pipeline.

Caps: 200 connections × 60 days per workspace (see
docs/phase-2/backfill-decisions.md §4).
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection import Connection
from app.models.post import Post
from app.models.workspace import Workspace
from app.services.apify import ApifyService

logger = logging.getLogger(__name__)

# Dogfood-scale cap (2026-04-18). Production target is 200 — see
# docs/phase-2/backfill-decisions.md §4. Lowered to keep Apify spend
# inside the free-tier credit during dogfood. Revert to 200 before
# first customer backfill (tracked in issue #81).
MAX_CONNECTIONS = 20
DAYS_BACK = 60


async def run_day_one_backfill(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    apify: ApifyService,
    email=None,  # Optional — inject FakeEmailSender in tests
) -> int:
    """Run backfill for one workspace. Returns the number of profiles scraped.

    Raises ValueError if the workspace has already been backfilled to completion.
    Idempotency is keyed on `backfill_completed_at IS NOT NULL` (not
    `backfill_used`) because the trigger endpoint sets `backfill_used=True`
    before enqueueing — the worker would otherwise refuse the very job that
    endpoint just scheduled. Failed runs leave `backfill_failed_at` set; a new
    attempt requires an admin clear of both `backfill_used` and
    `backfill_failed_at`.
    """
    ws = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if ws is None:
        raise ValueError(f"workspace {workspace_id} not found")
    if ws.backfill_completed_at is not None:
        raise ValueError(f"workspace {workspace_id} already backfilled")

    # Safe to touch `ws` attributes across commits: the session factory uses
    # expire_on_commit=False (see app/database.py), so the instance does not
    # expire after commit and no lazy reload is triggered inside the
    # exception handler below.
    ws.backfill_started_at = datetime.now(timezone.utc)
    ws.backfill_failed_at = None
    await db.commit()

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

    try:
        posts = await apify.scrape_profile_posts(
            profile_urls=profile_urls, days=DAYS_BACK
        )
    except Exception as apify_exc:
        # Persist the failure marker so the status endpoint can surface it.
        # Guard against a commit failure here masking the original Apify
        # exception — we always re-raise the Apify error, not the DB error.
        try:
            ws.backfill_failed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as commit_exc:
            logger.error(
                "[backfill] failed to persist backfill_failed_at for workspace %s: %s",
                workspace_id,
                commit_exc,
                exc_info=True,
            )
        logger.error(
            "[backfill] apify scrape failed for workspace %s",
            workspace_id,
            exc_info=apify_exc,
        )
        raise

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
    await db.commit()

    # Fire-and-forget completion email. Email failures do NOT fail the task.
    if email is not None:
        try:
            await email.send_backfill_complete(ws, len(profile_urls))
        except Exception as exc:
            logger.warning("[backfill] completion email failed, continuing: %s", exc)

    return len(profile_urls)
