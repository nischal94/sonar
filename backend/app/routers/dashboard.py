from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import Connection
from app.models.person_signal_summary import PersonSignalSummary
from app.models.post import Post
from app.models.signal import Signal
from app.models.user import User
from app.models.workspace import Workspace
from app.rate_limit import limiter
from app.routers.auth import get_current_user
from app.schemas.dashboard import DashboardPeopleResponse, DashboardPerson

router = APIRouter(prefix="/workspace/dashboard", tags=["dashboard"])


def _snippet(content: str, max_chars: int = 200) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rsplit(" ", 1)[0] + "…"


def _post_url(linkedin_post_id: str | None) -> str | None:
    if not linkedin_post_id:
        return None
    if linkedin_post_id.startswith("http"):
        return linkedin_post_id
    if linkedin_post_id.startswith("urn:"):
        return f"https://www.linkedin.com/feed/update/{linkedin_post_id}/"
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{linkedin_post_id}/"


@router.get("/people", response_model=DashboardPeopleResponse)
@limiter.limit("30/minute")
async def get_dashboard_people(
    request: Request,  # required by @limiter.limit
    threshold: float | None = Query(None, ge=0.0, le=1.0),
    relationship: str = Query("1,2"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Resolve threshold: explicit param > workspace default > 0.65 fallback
    if threshold is None:
        ws_result = await db.execute(
            select(Workspace.matching_threshold).where(
                Workspace.id == current_user.workspace_id
            )
        )
        threshold = ws_result.scalar_one_or_none() or 0.65

    # Parse relationship filter — "1,2" → [1, 2]
    try:
        degrees = sorted({int(x) for x in relationship.split(",") if x.strip()})
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid relationship param; expected comma-separated ints",
        )
    if not all(d in (1, 2) for d in degrees):
        raise HTTPException(
            status_code=422, detail="relationship degree must be 1 or 2"
        )

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stmt = (
        select(
            PersonSignalSummary,
            Connection,
            Post,
            Signal,
        )
        .join(Connection, Connection.id == PersonSignalSummary.connection_id)
        .outerjoin(Post, Post.id == PersonSignalSummary.recent_post_id)
        .outerjoin(Signal, Signal.id == PersonSignalSummary.recent_signal_id)
        .where(
            and_(
                PersonSignalSummary.workspace_id == current_user.workspace_id,
                PersonSignalSummary.aggregate_score >= threshold,
                PersonSignalSummary.last_signal_at >= seven_days_ago,
                Connection.degree.in_(degrees),
            )
        )
        .order_by(PersonSignalSummary.aggregate_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    people = [
        DashboardPerson(
            connection_id=conn.id,
            name=conn.name,
            title=conn.headline,
            company=conn.company,
            relationship_degree=conn.degree,
            mutual_count=None,
            aggregate_score=summary.aggregate_score,
            trend_direction=summary.trend_direction,
            last_signal_at=summary.last_signal_at,
            recent_post_snippet=_snippet(post.content) if post else None,
            matching_signal_phrase=sig.phrase if sig else None,
            recent_post_url=_post_url(post.linkedin_post_id) if post else None,
        )
        for summary, conn, post, sig in rows
    ]

    return DashboardPeopleResponse(
        people=people, threshold_used=threshold, total=len(people)
    )
