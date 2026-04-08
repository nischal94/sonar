from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models.workspace import Workspace
from app.models.feedback import FeedbackAdjustment
import uuid

MINIMUM_FEEDBACK_COUNT = 10
RAISE_THRESHOLD_STEP = 0.02
LOWER_THRESHOLD_STEP = 0.01
MAX_THRESHOLD = 0.92
MIN_THRESHOLD = 0.55


async def process_feedback_adjustment(
    workspace,
    recent_feedback: list[str],
    db: AsyncSession,
) -> float:
    """
    Adjust workspace matching threshold based on accumulated feedback.
    Returns the new threshold (unchanged if no adjustment made).
    """
    if len(recent_feedback) < MINIMUM_FEEDBACK_COUNT:
        return workspace.matching_threshold

    positive_count = sum(1 for f in recent_feedback if f == "positive")
    positive_rate = positive_count / len(recent_feedback)
    old_threshold = workspace.matching_threshold

    if positive_rate < 0.40:
        # Too many irrelevant alerts — be more selective
        new_threshold = min(MAX_THRESHOLD, old_threshold + RAISE_THRESHOLD_STEP)
    elif positive_rate > 0.75:
        # High satisfaction — catch more signals
        new_threshold = max(MIN_THRESHOLD, old_threshold - LOWER_THRESHOLD_STEP)
    else:
        return old_threshold  # No change needed

    if new_threshold == old_threshold:
        return old_threshold

    await db.execute(
        update(Workspace)
        .where(Workspace.id == workspace.id)
        .values(matching_threshold=new_threshold)
    )

    adjustment = FeedbackAdjustment(
        workspace_id=workspace.id,
        alert_id=uuid.uuid4(),  # placeholder — no single alert triggered this
        old_threshold=old_threshold,
        new_threshold=new_threshold,
        positive_rate=positive_rate,
        adjustment_reason=f"positive_rate={positive_rate:.2f}, n={len(recent_feedback)}",
    )
    db.add(adjustment)

    return new_threshold
