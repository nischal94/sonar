from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


class ProposeSignalsRequest(BaseModel):
    what_you_sell: str = Field(min_length=5, max_length=2000)
    icp: str | None = Field(default=None, max_length=1000)


class ProposedSignal(BaseModel):
    phrase: str = Field(min_length=3, max_length=120)
    example_post: str = Field(min_length=10, max_length=500)
    intent_strength: float = Field(ge=0, le=1)


class ProposeSignalsResponse(BaseModel):
    proposal_event_id: UUID
    prompt_version: str
    signals: list[ProposedSignal]


class EditedPair(BaseModel):
    proposed_idx: int = Field(ge=0)
    final_phrase: str = Field(min_length=3, max_length=120)
    final_example_post: str = Field(min_length=10, max_length=500)
    final_intent_strength: float = Field(ge=0, le=1)


class ConfirmedSignal(BaseModel):
    """Final shape sent by the frontend — post-edit or user-added."""

    phrase: str = Field(min_length=3, max_length=120)
    example_post: str = Field(min_length=10, max_length=500)
    intent_strength: float = Field(ge=0, le=1)


class ConfirmSignalsRequest(BaseModel):
    proposal_event_id: UUID
    accepted: list[int] = Field(
        default_factory=list
    )  # indices into proposal's signals array
    edited: list[EditedPair] = Field(default_factory=list)
    rejected: list[int] = Field(default_factory=list)
    user_added: list[ConfirmedSignal] = Field(default_factory=list)


class ConfirmSignalsResponse(BaseModel):
    signal_ids: list[UUID]
    profile_active: bool
