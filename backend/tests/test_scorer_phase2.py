import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.services.scorer import compute_combined_score, Priority


def _fresh_post_time():
    return datetime.now(timezone.utc) - timedelta(hours=1)


def test_scorer_should_accept_keyword_match_strength_input():
    connection = SimpleNamespace(
        degree=1, relationship_score=0.9, has_interacted=True
    )
    result = compute_combined_score(
        relevance_score=0.75,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=1.0,
    )
    assert isinstance(result.combined_score, float)
    assert 0.0 <= result.combined_score <= 1.0


def test_scorer_boosts_relevance_when_keyword_match_strong():
    connection = SimpleNamespace(
        degree=1, relationship_score=0.9, has_interacted=False
    )
    weak = compute_combined_score(
        relevance_score=0.60,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=0.0,
    )
    strong = compute_combined_score(
        relevance_score=0.60,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=1.0,
    )
    assert strong.combined_score > weak.combined_score


def test_scorer_keyword_strength_defaults_to_zero_when_not_provided():
    connection = SimpleNamespace(
        degree=2, relationship_score=None, has_interacted=False
    )
    result = compute_combined_score(
        relevance_score=0.50,
        connection=connection,
        posted_at=_fresh_post_time(),
    )
    assert result.combined_score >= 0.0
