"""Apify service wrapper for the Day-One Backfill slice.

External HTTP integration alongside Resend (email) and Groq (LLM). Follows
the Depends()-injectable pattern (per sonar/CLAUDE.md Python test mocking
rules) so tests never touch real Apify.

Actor selection, pricing, and schema mapping documented in
docs/phase-2/backfill-apify-research.md. MVP pick: harvestapi/linkedin-
profile-posts (no cookies, $1.50/1k posts, clean postedLimitDate filter).
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse, urlunparse

import httpx
from pydantic import BaseModel

from app.config import get_settings

# Dogfood-scale cap (2026-04-18). Production target is 10 — see
# docs/phase-2/backfill-apify-research.md §2 for the production cost
# math. Lowered to 3 to keep Apify spend inside the free-tier credit
# during dogfood. Revert to 10 before first customer backfill
# (tracked in issue #81).
MAX_POSTS_PER_PROFILE = 3


def canonicalize_profile_url(url: str | None) -> str | None:
    """Canonical form used as the join key between the extension-captured
    Connection.profile_url and posts returned by Apify.

    Normalizes three axes:
    - scheme + netloc lowercased (e.g. https://LinkedIn.com → https://linkedin.com).
      urllib.parse does NOT do this automatically; JS's `new URL(...).origin`
      does. Without this symmetry the join silently drops posts when Apify
      returns a redirect-normalized host with different case.
    - trailing slash stripped from the path.
    - query, params, fragment dropped (Apify returns `?miniProfileUrn=urn%3A...`
      tracking params; the extension stores clean `/in/<slug>`).

    Returns None for falsy input so callers can pass Apify fields straight
    through without a second None check.
    """
    if not url:
        return None
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


class ApifyProfilePost(BaseModel):
    """Normalized representation of one post returned by Apify.

    Keep this shape stable across actor swaps — the worker and tests depend
    on it. The raw-field mapping in RealApifyService.scrape_profile_posts
    is what changes when we pick a new actor.
    """

    profile_url: str
    linkedin_post_id: str
    content: str
    posted_at: datetime
    reaction_count: int = 0
    comment_count: int = 0
    share_count: int = 0


@runtime_checkable
class ApifyService(Protocol):
    """@runtime_checkable so tests can isinstance-check RealApifyService against
    the Protocol when a real APIFY_API_TOKEN is configured. Protocol conformance
    is structural — the decorator just enables the isinstance() check."""

    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]: ...


class RealApifyService:
    """Production implementation. Calls the configured Apify actor via HTTPS.

    See docs/phase-2/backfill-apify-research.md for actor selection rationale
    and the raw-field mapping table. Swap actors by updating _ACTOR_ID + the
    field-access lines in scrape_profile_posts; do NOT change ApifyProfilePost.
    """

    _ACTOR_ID = "harvestapi~linkedin-profile-posts"
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
        # harvestapi uses `postedLimitDate` (ISO string), not `daysBack`.
        posted_limit = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        run_url = (
            f"{self._base}/acts/{self._ACTOR_ID}/run-sync-get-dataset-items"
            f"?token={self._token}"
        )
        payload = {
            "targetUrls": profile_urls,
            "maxPosts": MAX_POSTS_PER_PROFILE,
            "postedLimitDate": posted_limit,
            "scrapeReactions": False,
            "scrapeComments": False,
            "includeQuotePosts": True,
            "includeReposts": False,
        }
        async with httpx.AsyncClient(timeout=self._RUN_TIMEOUT_SEC) as client:
            resp = await client.post(run_url, json=payload)
            resp.raise_for_status()
            raw = resp.json()

        return [post for post in map(self._map_row, raw) if post is not None]

    @staticmethod
    def _map_row(item: dict) -> ApifyProfilePost | None:
        """Map one harvestapi output row to our normalized shape.

        Skip rows with missing required fields rather than raise — one
        malformed row shouldn't kill the batch. See research doc §3 for the
        mapping table.
        """
        try:
            author = item.get("author") or {}
            raw_profile_url = author.get("linkedinUrl") or author.get("profileUrl")
            profile_url = canonicalize_profile_url(raw_profile_url)
            post_id = item.get("id")

            # postedAt may be a dict ({timestamp, date, relative}) OR a bare
            # ISO string, depending on the actor's schema rev. Handle both.
            posted_at_field = item.get("postedAt")
            if isinstance(posted_at_field, dict):
                posted_at_raw = posted_at_field.get("timestamp") or posted_at_field.get(
                    "date"
                )
            else:
                posted_at_raw = posted_at_field

            if not profile_url or not post_id or not posted_at_raw:
                return None

            if isinstance(posted_at_raw, (int, float)):
                posted_at = datetime.fromtimestamp(
                    posted_at_raw / 1000 if posted_at_raw > 1e12 else posted_at_raw,
                    tz=timezone.utc,
                )
            else:
                posted_at = datetime.fromisoformat(str(posted_at_raw))

            engagement = item.get("engagement") or {}
            return ApifyProfilePost(
                profile_url=profile_url,
                linkedin_post_id=str(post_id),
                content=item.get("content") or "",
                posted_at=posted_at,
                reaction_count=engagement.get("likes")
                or engagement.get("totalReactions")
                or 0,
                comment_count=engagement.get("comments") or 0,
                share_count=engagement.get("shares") or 0,
            )
        except (KeyError, ValueError, TypeError):
            return None


_singleton: RealApifyService | None = None


def get_apify_service() -> ApifyService:
    """FastAPI Depends() factory. Tests override with a FakeApifyService."""
    global _singleton
    if _singleton is None:
        _singleton = RealApifyService()
    return _singleton
