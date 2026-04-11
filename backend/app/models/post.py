from sqlalchemy import Column, String, Float, Boolean, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models._types import TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
import uuid
from app.database import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_post_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("connections.id"))
    linkedin_post_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    post_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    posted_at = Column(TIMESTAMPTZ)
    ingested_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    relevance_score = Column(Float)
    relationship_score = Column(Float)
    timing_score = Column(Float)
    combined_score = Column(Float)
    matched = Column(Boolean, nullable=False, default=False)
    processed_at = Column(TIMESTAMPTZ)
    extraction_version = Column(String)
    embedding = Column(Vector(1536))  # added in Task 1
    # Phase 2 JSONB additions (Task 6)
    ring1_matches = Column(JSONB, default=list)
    ring2_matches = Column(JSONB, default=list)
    themes = Column(JSONB, default=list)
    engagement_counts = Column(JSONB, default=dict)
