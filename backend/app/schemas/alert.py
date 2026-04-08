from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class AlertResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    connection_id: UUID
    priority: str
    combined_score: float
    relevance_score: float
    relationship_score: float
    timing_score: float
    match_reason: str | None
    outreach_draft_a: str | None
    outreach_draft_b: str | None
    opportunity_type: str | None
    urgency_reason: str | None
    status: str
    feedback: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

class FeedbackRequest(BaseModel):
    feedback: str  # 'positive' | 'negative'
    outcome: str | None = None
    message_sent: str | None = None
