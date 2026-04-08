from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base

class OutreachHistory(Base):
    __tablename__ = "outreach_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True), nullable=False)
    message_sent = Column(Text)
    outcome = Column(String)
    notes = Column(Text)
    contacted_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
