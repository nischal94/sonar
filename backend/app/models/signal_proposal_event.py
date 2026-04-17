from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class SignalProposalEvent(Base):
    """Telemetry row written once per wizard run. See `docs/phase-2/wizard-decisions.md` §3a
    for the schema rationale. `/propose` inserts with most fields populated + `completed_at=NULL`;
    `/confirm` updates the same row with the acceptance breakdown and sets `completed_at`."""

    __tablename__ = "signal_proposal_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    what_you_sell: Mapped[str] = mapped_column(Text, nullable=False)
    icp: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed: Mapped[list] = mapped_column(JSONB, nullable=False)
    accepted_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    edited_pairs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rejected_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    user_added: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
