from sqlalchemy import Column, String, Float, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base

class FeedbackAdjustment(Base):
    __tablename__ = "feedback_adjustments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    old_threshold = Column(Float, nullable=False)
    new_threshold = Column(Float, nullable=False)
    positive_rate = Column(Float, nullable=False)
    adjustment_reason = Column(String)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")


class SignalEffectiveness(Base):
    __tablename__ = "signal_effectiveness"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    predicted_score = Column(Float, nullable=False)
    user_rated = Column(String)
    outreach_sent = Column(Boolean, nullable=False, default=False)
    outreach_outcome = Column(String)
    revenue_attributed = Column(Numeric(10, 2))
    effectiveness_score = Column(Float)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
