"""Celery task wrapper around run_day_one_backfill.

The pure async worker lives in app.workers.day_one_backfill. This module
adapts it for Celery: a sync entry point that stands up its own engine +
async session (Celery can't await), resolves the real Apify service, and
runs the coroutine.

Pattern matches app/jobs/public_poller.py — kept in app/jobs/ (not
app/workers/) so Celery-scheduled wrappers and the pure pipeline code
stay separated.
"""

from __future__ import annotations
import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.services.apify import get_apify_service
from app.workers.celery_app import celery_app
from app.workers.day_one_backfill import run_day_one_backfill

# Eager imports so SQLAlchemy's configure_mappers() can resolve string-name
# relationships (e.g. Workspace.users → "User") at first query. The Celery
# worker process hasn't loaded these via any other import path — without
# them the first query raises "expression 'User' failed to locate a name".
# Match the full model set registered against Base to cover any relationship.
from app.models import (  # noqa: F401
    alert,
    company_signal_summary,
    connection,
    feedback,
    outreach,
    person_signal_summary,
    post,
    signal,
    signal_proposal_event,
    trend,
    user,
    workspace,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.jobs.day_one_backfill_task.run_day_one_backfill_task")
def run_day_one_backfill_task(workspace_id: str) -> int:
    """Sync Celery entry point. Returns profile count for result backend."""
    return asyncio.run(_run(workspace_id))


async def _run(workspace_id: str) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as db:
            return await run_day_one_backfill(
                db,
                workspace_id=UUID(workspace_id),
                apify=get_apify_service(),
            )
    finally:
        await engine.dispose()
