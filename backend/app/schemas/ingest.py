from pydantic import BaseModel
from datetime import datetime

class PostAuthor(BaseModel):
    name: str
    headline: str | None = None
    profile_url: str | None = None
    linkedin_id: str
    degree: int  # 1, 2, or 3

class PostEngagement(BaseModel):
    likes: int = 0
    comments: int = 0

class IngestPost(BaseModel):
    linkedin_post_id: str
    author: PostAuthor
    content: str
    post_type: str = "post"
    posted_at: datetime | None = None
    engagement: PostEngagement = PostEngagement()

class PostIngestPayload(BaseModel):
    posts: list[IngestPost]
    extraction_version: str = "unknown"

class IngestResponse(BaseModel):
    queued: int
    skipped: int  # duplicates
