from sqlalchemy import Column, String, Float, Boolean, Integer, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
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
    scoring_weights = Column(JSONB, default=lambda: {"relevance": 0.50, "relationship": 0.30, "timing": 0.20})
    onboarding_url = Column(String)
    onboarding_doc_path = Column(String)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    users = relationship("User", back_populates="workspace")
    capability_versions = relationship("CapabilityProfileVersion", back_populates="workspace")


class CapabilityProfileVersion(Base):
    __tablename__ = "capability_profile_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    version = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    # embedding stored via pgvector — added in migration using Vector type
    source = Column(String, nullable=False)
    signal_keywords = Column(ARRAY(Text))
    anti_keywords = Column(ARRAY(Text))
    is_active = Column(Boolean, nullable=False, default=True)
    performance_score = Column(Float)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    workspace = relationship("Workspace", back_populates="capability_versions")
