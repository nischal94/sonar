from sqlalchemy import Column, String, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models._types import TIMESTAMPTZ
import uuid
from app.database import Base


class CompanySignalSummary(Base):
    __tablename__ = "company_signal_summary"
    __table_args__ = (UniqueConstraint("workspace_id", "company_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    company_name = Column(String, nullable=False)
    aggregate_score = Column(Float, nullable=False, default=0.0)
    active_signal_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
