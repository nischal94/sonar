from sqlalchemy import Column, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models._types import TIMESTAMPTZ
import uuid
from app.database import Base


class PersonSignalSummary(Base):
    __tablename__ = "person_signal_summary"
    __table_args__ = (UniqueConstraint("workspace_id", "connection_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("connections.id"), nullable=False)
    aggregate_score = Column(Float, nullable=False, default=0.0)
    trend_direction = Column(String, nullable=False, default="flat")
    last_signal_at = Column(TIMESTAMPTZ)
    recent_post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"))
    recent_signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
