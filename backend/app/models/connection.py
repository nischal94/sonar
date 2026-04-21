from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Integer,
    ARRAY,
    Text,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models._types import TIMESTAMPTZ
import uuid
from app.database import Base


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    linkedin_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    headline = Column(Text)
    profile_url = Column(String)
    company = Column(String)
    seniority = Column(String)
    degree = Column(Integer, nullable=False)
    mutual_count = Column(Integer, nullable=False, default=0, server_default="0")
    relationship_score = Column(Float, nullable=True)
    fit_score = Column(Float, nullable=True)
    has_interacted = Column(Boolean, nullable=False, default=False)
    first_seen_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    last_active_at = Column(TIMESTAMPTZ)
    enriched_at = Column(TIMESTAMPTZ)
    enrichment_data = Column(JSONB, default=dict)
    topic_interests = Column(ARRAY(Text))
