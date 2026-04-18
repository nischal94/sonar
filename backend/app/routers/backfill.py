from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import Connection
from app.models.user import User
from app.rate_limit import limiter
from app.routers.auth import get_current_user
from app.schemas.backfill import (
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
    if not body.connections:
        return ConnectionsBulkResponse(upserted=0)

    linkedin_ids = [c.linkedin_id for c in body.connections]
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

    for row in body.connections:
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
    return ConnectionsBulkResponse(upserted=len(body.connections))
