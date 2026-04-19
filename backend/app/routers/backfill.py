from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import Connection
from app.models.user import User
from app.models.workspace import Workspace
from app.rate_limit import limiter
from app.routers.auth import get_current_user
from app.schemas.backfill import (
    BackfillStatusResponse,
    BackfillTriggerResponse,
    BulkConnection,
    ConnectionsBulkRequest,
    ConnectionsBulkResponse,
)

router = APIRouter(tags=["backfill"])


@router.post("/extension/connections/bulk", response_model=ConnectionsBulkResponse)
@limiter.limit("5/hour")
async def connections_bulk(
    request: Request,
    body: ConnectionsBulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    received = len(body.connections)
    if not body.connections:
        return ConnectionsBulkResponse(upserted=0, received=0, deduped=0)

    # Dedupe by linkedin_id within the request body — LinkedIn's virtualized
    # list can emit duplicates when the extension scrolls re-renders over the
    # same row. Last occurrence wins so the freshest scrape payload sticks.
    deduped_map: dict[str, BulkConnection] = {}
    for row in body.connections:
        deduped_map[row.linkedin_id] = row
    rows = list(deduped_map.values())

    linkedin_ids = list(deduped_map.keys())
    existing = (
        (
            await db.execute(
                select(Connection).where(
                    Connection.workspace_id == current_user.workspace_id,
                    Connection.linkedin_id.in_(linkedin_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    existing_by_lid = {c.linkedin_id: c for c in existing}

    for row in rows:
        e = existing_by_lid.get(row.linkedin_id)
        if e is not None:
            e.name = row.name
            e.headline = row.headline
            e.company = row.company
            e.profile_url = row.profile_url
        else:
            db.add(
                Connection(
                    workspace_id=current_user.workspace_id,
                    user_id=current_user.id,
                    linkedin_id=row.linkedin_id,
                    name=row.name,
                    headline=row.headline,
                    company=row.company,
                    profile_url=row.profile_url,
                    degree=1,
                )
            )

    await db.commit()
    return ConnectionsBulkResponse(
        upserted=len(rows),
        received=received,
        deduped=received - len(rows),
    )


@router.post("/workspace/backfill/trigger", response_model=BackfillTriggerResponse)
@limiter.limit("2/day")
async def backfill_trigger(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = (
        await db.execute(
            select(Workspace).where(Workspace.id == current_user.workspace_id)
        )
    ).scalar_one()
    if ws.backfill_used:
        raise HTTPException(
            status_code=409,
            detail=(
                "Backfill already used for this workspace (started at "
                f"{ws.backfill_started_at.isoformat() if ws.backfill_started_at else 'unknown'})"
            ),
        )

    # Mark started now to prevent race with a second trigger before the
    # Celery task picks up. run_day_one_backfill keys idempotency on
    # backfill_completed_at (not backfill_used), so the worker will still
    # run this job even though backfill_used is already True here.
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    await db.commit()

    from app.jobs.day_one_backfill_task import run_day_one_backfill_task

    async_result = run_day_one_backfill_task.delay(str(current_user.workspace_id))
    return BackfillTriggerResponse(task_id=async_result.id, backfill_started_at=now)


@router.get("/workspace/backfill/status", response_model=BackfillStatusResponse)
async def backfill_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = (
        await db.execute(
            select(Workspace).where(Workspace.id == current_user.workspace_id)
        )
    ).scalar_one()

    if not ws.backfill_used:
        state = "idle"
    elif ws.backfill_completed_at is not None:
        state = "done"
    elif ws.backfill_failed_at is not None:
        state = "failed"
    else:
        state = "running"

    return BackfillStatusResponse(
        state=state,
        profile_count=ws.backfill_profile_count,
        backfill_started_at=ws.backfill_started_at,
        backfill_completed_at=ws.backfill_completed_at,
    )
