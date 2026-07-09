from sqlalchemy import Column, String, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from app.models._types import TIMESTAMPTZ
import uuid
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    post_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True), nullable=False)
    relevance_score = Column(Float, nullable=False)
    relationship_score = Column(Float, nullable=True)
    timing_score = Column(Float, nullable=False)
    combined_score = Column(Float, nullable=False)
    priority = Column(String, nullable=False)
    match_reason = Column(Text)
    outreach_draft_a = Column(Text)
    outreach_draft_b = Column(Text)
    opportunity_type = Column(String)
    urgency_reason = Column(Text)
    status = Column(String, nullable=False, default="pending")
    delivered_at = Column(TIMESTAMPTZ)
    seen_at = Column(TIMESTAMPTZ)
    feedback = Column(String)
    feedback_at = Column(TIMESTAMPTZ)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
