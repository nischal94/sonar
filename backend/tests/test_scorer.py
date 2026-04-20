from datetime import datetime, timezone, timedelta
from app.services.scorer import compute_combined_score, Priority, ScoringResult


def make_connection(
    degree: int = 1,
    relationship_score: float | None = None,
    has_interacted: bool = False,
):
    from types import SimpleNamespace

    return SimpleNamespace(
        degree=degree,
        relationship_score=relationship_score,
        has_interacted=has_interacted,
    )


def test_high_priority_for_fresh_first_degree_relevant_post():
    connection = make_connection(degree=1, relationship_score=0.9)
    result = compute_combined_score(
        relevance_score=0.88,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    assert result.priority == Priority.HIGH
    assert result.combined_score >= 0.80


def test_low_priority_for_old_third_degree_weak_post():
    connection = make_connection(degree=3, relationship_score=0.3)
    result = compute_combined_score(
        relevance_score=0.55,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=23),
    )
    assert result.priority == Priority.LOW
    assert result.combined_score < 0.55


def test_relationship_score_falls_back_to_degree_base_when_null():
    # Regression for issue #105: when connection.relationship_score is None,
    # the scorer must fall back to DEGREE_BASE_SCORE, not silently pass through
    # a stale default. A 1st-degree connection must score at least 0.9.
    connection = make_connection(degree=1, relationship_score=None)
    result = compute_combined_score(
        relevance_score=0.5,
        connection=connection,
        posted_at=datetime.now(timezone.utc),
    )
    assert result.relationship_score == 0.9


def test_relationship_score_boost_for_interaction():
    connection = make_connection(degree=2, relationship_score=None, has_interacted=True)
    result = compute_combined_score(
        relevance_score=0.80,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    # has_interacted should boost relationship score above base 0.60 for degree=2
    assert result.relationship_score > 0.60


def test_timing_score_decays_over_24_hours():
    connection = make_connection(degree=1)
    fresh_result = compute_combined_score(
        relevance_score=0.80,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    old_result = compute_combined_score(
        relevance_score=0.80,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=22),
    )
    assert fresh_result.timing_score > old_result.timing_score
    assert fresh_result.combined_score > old_result.combined_score


def test_scoring_result_fields_present():
    connection = make_connection(degree=1)
    result = compute_combined_score(
        relevance_score=0.75,
        connection=connection,
        posted_at=datetime.now(timezone.utc),
    )
    assert isinstance(result, ScoringResult)
    assert 0.0 <= result.relevance_score <= 1.0
    assert 0.0 <= result.relationship_score <= 1.0
    assert 0.0 <= result.timing_score <= 1.0
    assert 0.0 <= result.combined_score <= 1.0
    assert result.priority in (Priority.HIGH, Priority.MEDIUM, Priority.LOW)
