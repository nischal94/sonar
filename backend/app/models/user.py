from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    linkedin_profile_url = Column(String)
    delivery_channels = Column(JSONB, default=dict)
    alert_rate_limits = Column(JSONB, default=lambda: {"high": 10, "medium": 5, "low": 2})
    quiet_hours = Column(JSONB, default=dict)
    extension_installed = Column(Boolean, nullable=False, default=False)
    extension_last_sync = Column(TIMESTAMPTZ)
    timezone = Column(String, nullable=False, default="UTC")
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    workspace = relationship("Workspace", back_populates="users")
