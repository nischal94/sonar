from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.alert import Alert
from app.models.outreach import OutreachHistory
from app.models.feedback import SignalEffectiveness
from app.routers.auth import get_current_user
from app.schemas.alert import AlertResponse, FeedbackRequest
from app.services.feedback_trainer import process_feedback_adjustment

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    priority: str | None = None,
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert).where(Alert.workspace_id == current_user.workspace_id)
    if priority:
        query = query.where(Alert.priority == priority)
    if status:
        query = query.where(Alert.status == status)
    query = query.order_by(Alert.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{alert_id}/feedback", status_code=200)
async def submit_feedback(
    alert_id: UUID,
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.feedback not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="feedback must be 'positive' or 'negative'")

    alert = await db.get(Alert, alert_id)
    if not alert or alert.workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc)

    await db.execute(
        update(Alert).where(Alert.id == alert_id)
        .values(
            feedback=body.feedback,
            feedback_at=now,
            status="acted" if body.feedback == "positive" else "dismissed",
        )
    )

    user_rated = "relevant" if body.feedback == "positive" else "not_relevant"
    await db.execute(
        update(SignalEffectiveness).where(SignalEffectiveness.alert_id == alert_id)
        .values(user_rated=user_rated, outreach_sent=body.message_sent is not None)
    )

    if body.message_sent:
        outreach = OutreachHistory(
            workspace_id=current_user.workspace_id,
            alert_id=alert_id,
            connection_id=alert.connection_id,
            message_sent=body.message_sent,
            outcome=body.outcome,
        )
        db.add(outreach)

    await db.flush()

    recent_result = await db.execute(
        select(Alert.feedback).where(
            Alert.workspace_id == current_user.workspace_id,
            Alert.feedback.is_not(None),
        ).order_by(Alert.feedback_at.desc()).limit(50)
    )
    recent_feedback = [row[0] for row in recent_result.fetchall()]

    from app.models.workspace import Workspace
    workspace = await db.get(Workspace, current_user.workspace_id)
    await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=db,
    )

    await db.commit()
    return {"message": "Sonar is learning your preferences."}
