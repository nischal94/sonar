from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class BulkConnection(BaseModel):
    linkedin_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    headline: str | None = Field(default=None, max_length=500)
    company: str | None = Field(default=None, max_length=200)
    profile_url: str = Field(min_length=1, max_length=500)


class ConnectionsBulkRequest(BaseModel):
    connections: list[BulkConnection] = Field(min_length=0, max_length=500)


class ConnectionsBulkResponse(BaseModel):
    upserted: int


class BackfillTriggerResponse(BaseModel):
    task_id: str
    backfill_started_at: datetime


BackfillState = Literal["idle", "running", "done", "failed"]


class BackfillStatusResponse(BaseModel):
    state: BackfillState
    profile_count: int
    backfill_started_at: datetime | None
    backfill_completed_at: datetime | None
