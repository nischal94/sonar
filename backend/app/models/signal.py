from sqlalchemy import Column, Float, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models._types import TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
import uuid
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    profile_version_id = Column(UUID(as_uuid=True), ForeignKey("capability_profile_versions.id"))
    phrase = Column(Text, nullable=False)
    example_post = Column(Text)
    intent_strength = Column(Float, nullable=False, default=0.7)
    enabled = Column(Boolean, nullable=False, default=True)
    embedding = Column(Vector(1536))
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
