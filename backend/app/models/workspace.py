from sqlalchemy import Column, String, Float, Boolean, Integer, ARRAY, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models._types import TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    plan_tier = Column(String, nullable=False, default="starter")
    capability_profile = Column(Text)
    matching_threshold = Column(Float, nullable=False, default=0.72)
    scoring_weights = Column(
        JSONB, default=lambda: {"relevance": 0.50, "relationship": 0.30, "timing": 0.20}
    )
    delivery_channels = Column(JSONB, default=dict)
    onboarding_url = Column(String)
    onboarding_doc_path = Column(String)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    backfill_used = Column(Boolean, nullable=False, default=False)
    backfill_started_at = Column(TIMESTAMPTZ)
    backfill_completed_at = Column(TIMESTAMPTZ)
    backfill_failed_at = Column(TIMESTAMPTZ)
    backfill_profile_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )

    users = relationship("User", back_populates="workspace")
    capability_versions = relationship(
        "CapabilityProfileVersion", back_populates="workspace"
    )


class CapabilityProfileVersion(Base):
    __tablename__ = "capability_profile_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    version = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    signal_keywords = Column(ARRAY(Text))
    anti_keywords = Column(ARRAY(Text))
    is_active = Column(Boolean, nullable=False, default=True)
    performance_score = Column(Float)
    embedding = Column(Vector(1536))
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    workspace = relationship("Workspace", back_populates="capability_versions")
