"""Unit tests for canonicalize_profile_url.

This helper is the join key between connections captured by the extension
(stored in Connection.profile_url) and posts returned by Apify (mapped into
ApifyProfilePost.profile_url). If the two sides of the join disagree on
canonical form — case, trailing slash, query params — the worker's
conn_by_url.get(post.profile_url) silently misses and no posts land against
that connection.

Cover every normalization axis: scheme/netloc lowercasing, trailing-slash
stripping, query/params/fragment dropping, and falsy-input pass-through.
"""

from __future__ import annotations
import pytest

from app.services.apify import canonicalize_profile_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Canonical form round-trips to itself.
        (
            "https://www.linkedin.com/in/alice",
            "https://www.linkedin.com/in/alice",
        ),
        # Trailing slash stripped.
        (
            "https://www.linkedin.com/in/alice/",
            "https://www.linkedin.com/in/alice",
        ),
        # Tracking query param dropped (Apify's actual output shape).
        (
            "https://www.linkedin.com/in/alice?miniProfileUrn=urn%3Ali%3Afsd_profile%3AAB123",
            "https://www.linkedin.com/in/alice",
        ),
        # Fragment dropped.
        (
            "https://www.linkedin.com/in/alice#section",
            "https://www.linkedin.com/in/alice",
        ),
        # Uppercase host lowercased — this is the latent bug the reviewer
        # caught. JS's u.origin lowercases on the extension side; without
        # lowercasing here, the join would silently miss.
        (
            "https://www.LinkedIn.com/in/alice",
            "https://www.linkedin.com/in/alice",
        ),
        # Uppercase scheme lowercased (same reason).
        (
            "HTTPS://www.linkedin.com/in/alice",
            "https://www.linkedin.com/in/alice",
        ),
        # Path case preserved — LinkedIn slugs are usually lowercased, but
        # we don't touch the path beyond trailing-slash stripping.
        (
            "https://www.linkedin.com/in/AliceSlug",
            "https://www.linkedin.com/in/AliceSlug",
        ),
        # Multi-axis combination stress test.
        (
            "HTTPS://WWW.LINKEDIN.COM/in/alice/?miniProfileUrn=urn%3Ali%3A123#about",
            "https://www.linkedin.com/in/alice",
        ),
    ],
)
def test_canonicalize_profile_url_normalizes_all_axes(raw, expected):
    assert canonicalize_profile_url(raw) == expected


@pytest.mark.parametrize("falsy", [None, ""])
def test_canonicalize_profile_url_returns_none_for_falsy(falsy):
    """_map_row passes Apify's linkedinUrl straight through, which may be
    missing. Returning None lets callers skip the row cleanly."""
    assert canonicalize_profile_url(falsy) is None
