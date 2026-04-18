import pytest
from datetime import datetime, timezone
from app.config import get_settings
from app.services.apify import (
    ApifyService,
    ApifyProfilePost,
    RealApifyService,
    get_apify_service,
)


class FakeApify(ApifyService):
    """In-memory double for tests. Returns fixed posts regardless of input."""

    def __init__(self, posts_per_profile: int = 3):
        self.calls: list[dict] = []
        self._posts_per_profile = posts_per_profile

    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]:
        self.calls.append({"profile_urls": profile_urls, "days": days})
        out: list[ApifyProfilePost] = []
        for url in profile_urls:
            for i in range(self._posts_per_profile):
                out.append(
                    ApifyProfilePost(
                        profile_url=url,
                        linkedin_post_id=f"{url}-post-{i}",
                        content=f"post body {i} about hiring challenges",
                        posted_at=datetime.now(timezone.utc),
                        reaction_count=i * 3,
                        comment_count=i,
                        share_count=0,
                    )
                )
        return out


@pytest.mark.asyncio
async def test_fake_apify_returns_expected_shape():
    fake = FakeApify(posts_per_profile=2)
    result = await fake.scrape_profile_posts(
        ["https://linkedin.com/in/alice", "https://linkedin.com/in/bob"], days=60
    )
    assert len(result) == 4
    assert all(isinstance(p, ApifyProfilePost) for p in result)
    assert fake.calls == [
        {
            "profile_urls": [
                "https://linkedin.com/in/alice",
                "https://linkedin.com/in/bob",
            ],
            "days": 60,
        }
    ]


@pytest.mark.skipif(
    get_settings().apify_api_token.startswith("placeholder"),
    reason="requires real APIFY_API_TOKEN",
)
def test_get_apify_service_is_callable():
    svc = get_apify_service()
    assert isinstance(svc, ApifyService)


# --- RealApifyService._map_row: harvestapi output → ApifyProfilePost ---


def _ok_row(**overrides):
    row = {
        "id": "urn:li:activity:7000000000000000001",
        "content": "Hiring two senior engineers, DMs open.",
        "postedAt": {"timestamp": 1713440000000},  # ms since epoch
        "author": {
            "linkedinUrl": "https://www.linkedin.com/in/alice",
        },
        "engagement": {"likes": 42, "comments": 3, "shares": 1},
    }
    row.update(overrides)
    return row


def test_map_row_happy_path():
    post = RealApifyService._map_row(_ok_row())
    assert post is not None
    assert post.profile_url == "https://www.linkedin.com/in/alice"
    assert post.linkedin_post_id == "urn:li:activity:7000000000000000001"
    assert post.content.startswith("Hiring")
    assert post.posted_at.tzinfo is not None  # timezone-aware
    assert (post.reaction_count, post.comment_count, post.share_count) == (42, 3, 1)


def test_map_row_accepts_iso_timestamp_string():
    # Some actor versions return an ISO string rather than a ms-epoch int.
    post = RealApifyService._map_row(_ok_row(postedAt="2026-04-10T14:22:00+00:00"))
    assert post is not None
    assert post.posted_at == datetime(2026, 4, 10, 14, 22, tzinfo=timezone.utc)


def test_map_row_falls_back_to_profileurl_field_name():
    # Older harvestapi schema used `profileUrl` instead of `linkedinUrl`.
    row = _ok_row()
    row["author"] = {"profileUrl": "https://www.linkedin.com/in/bob"}
    post = RealApifyService._map_row(row)
    assert post is not None
    assert post.profile_url == "https://www.linkedin.com/in/bob"


def test_map_row_returns_none_on_missing_required_field():
    # No id → skip row, don't crash the batch.
    assert RealApifyService._map_row(_ok_row(id=None)) is None
    # No profile url → skip.
    row = _ok_row()
    row["author"] = {}
    assert RealApifyService._map_row(row) is None
    # No posted_at → skip.
    assert RealApifyService._map_row(_ok_row(postedAt=None)) is None


def test_map_row_defaults_missing_engagement_to_zero():
    row = _ok_row()
    row.pop("engagement")
    post = RealApifyService._map_row(row)
    assert post is not None
    assert (post.reaction_count, post.comment_count, post.share_count) == (0, 0, 0)
