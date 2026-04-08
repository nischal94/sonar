from sqlalchemy import Column, String, Float, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base

class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_post_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True))
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
