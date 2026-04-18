import pytest
from datetime import datetime, timezone
from app.config import get_settings
from app.services.apify import (
    ApifyService,
    ApifyProfilePost,
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
