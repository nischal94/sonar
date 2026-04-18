from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


TrendDirection = Literal["up", "flat", "down"]


class DashboardPerson(BaseModel):
    connection_id: UUID
    name: str
    title: str | None
    company: str | None
    relationship_degree: int = Field(ge=1, le=2)
    mutual_count: int | None
    aggregate_score: float = Field(ge=0, le=1)
    trend_direction: TrendDirection
    last_signal_at: datetime
    recent_post_snippet: str | None
    matching_signal_phrase: str | None
    recent_post_url: str | None


class DashboardPeopleResponse(BaseModel):
    people: list[DashboardPerson]
    threshold_used: float = Field(ge=0, le=1)
    total: int = Field(ge=0)
