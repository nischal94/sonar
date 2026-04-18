"""Apify service wrapper for the Day-One Backfill slice.

First external HTTP integration since SendGrid/Groq. Follows the Depends()-
injectable pattern (per sonar/CLAUDE.md Python test mocking rules) so tests
never touch real Apify.

Actor selection + pricing documented in docs/phase-2/backfill-apify-research.md.
"""

from __future__ import annotations
from datetime import datetime
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.config import get_settings


class ApifyProfilePost(BaseModel):
    """Normalized representation of one post returned by Apify."""

    profile_url: str
    linkedin_post_id: str
    content: str
    posted_at: datetime
    reaction_count: int = 0
    comment_count: int = 0
    share_count: int = 0


class ApifyService(Protocol):
    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]: ...


class RealApifyService:
    """Production implementation. Calls the configured Apify actor via HTTPS.

    The specific actor id and input-schema mapping live in
    docs/phase-2/backfill-apify-research.md. Update this class when the
    MVP pick changes.
    """

    _ACTOR_ID = "apify/linkedin-profile-scraper"  # verify in research spike
    _RUN_TIMEOUT_SEC = 600

    def __init__(self) -> None:
        token = get_settings().apify_api_token
        if token.startswith("placeholder"):
            raise RuntimeError(
                "APIFY_API_TOKEN is the placeholder value; real token required "
                "to call the live Apify API."
            )
        self._token = token
        self._base = "https://api.apify.com/v2"

    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]:
        run_url = (
            f"{self._base}/acts/{self._ACTOR_ID}/run-sync-get-dataset-items"
            f"?token={self._token}"
        )
        payload = {
            "profileUrls": profile_urls,
            "maxPostsPerProfile": 30,
            "daysBack": days,
        }
        async with httpx.AsyncClient(timeout=self._RUN_TIMEOUT_SEC) as client:
            resp = await client.post(run_url, json=payload)
            resp.raise_for_status()
            raw = resp.json()

        # Actor-specific field mapping. Adjust when swapping actors.
        posts: list[ApifyProfilePost] = []
        for item in raw:
            try:
                posts.append(
                    ApifyProfilePost(
                        profile_url=item["profileUrl"],
                        linkedin_post_id=item["postId"],
                        content=item.get("text", ""),
                        posted_at=datetime.fromisoformat(item["postedAt"]),
                        reaction_count=item.get("reactions", 0),
                        comment_count=item.get("comments", 0),
                        share_count=item.get("shares", 0),
                    )
                )
            except (KeyError, ValueError):
                # Malformed row from Apify — skip, keep the batch useful.
                continue
        return posts


_singleton: RealApifyService | None = None


def get_apify_service() -> ApifyService:
    """FastAPI Depends() factory. Tests override with a FakeApifyService."""
    global _singleton
    if _singleton is None:
        _singleton = RealApifyService()
    return _singleton
