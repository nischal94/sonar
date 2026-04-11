from sqlalchemy import Column, Integer, Text, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models._types import TIMESTAMPTZ
import uuid
from app.database import Base


class Trend(Base):
    __tablename__ = "trends"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    ring = Column(Integer, nullable=False)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
    cluster_label = Column(Text)
    cluster_sample_posts = Column(JSONB)
    this_week_count = Column(Integer, nullable=False, default=0)
    last_week_count = Column(Integer, nullable=False, default=0)
    velocity_delta = Column(Integer, nullable=False, default=0)
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
