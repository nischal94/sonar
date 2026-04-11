from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

DEFAULT_WEIGHTS = {
    "relevance": 0.50,
    "relationship": 0.30,
    "timing": 0.20,
}

DEGREE_BASE_SCORE = {1: 0.90, 2: 0.60, 3: 0.30}
INTERACTION_BOOST = 0.15


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScoringResult:
    relevance_score: float
    relationship_score: float
    timing_score: float
    combined_score: float
    priority: Priority


def compute_combined_score(
    relevance_score: float,
    connection,
    posted_at: datetime,
    weights: dict | None = None,
    keyword_match_strength: float = 0.0,
) -> ScoringResult:
    """
    Compute 3-dimension combined score for a post+connection pair.

    Dimensions:
      - relevance: semantic match quality (0-1), provided by caller.
        When keyword_match_strength > 0, relevance is boosted by a fraction
        of the keyword match strength to reflect the Ring 1 hit. Capped at 1.0.
      - relationship: warmth of connection (degree + interaction history)
      - timing: urgency decay (linear over 24 hours)

    Args:
      keyword_match_strength: 0.0 (no keyword match) to 1.0 (full match).
        This replaces the old keyword_prefilter hard gate: instead of
        dropping posts that fail the keyword filter, we score all posts
        and let the keyword filter add a boost.
    """
    w = weights or DEFAULT_WEIGHTS

    # Relevance boost from keyword match — up to +0.15
    boosted_relevance = min(1.0, relevance_score + 0.15 * keyword_match_strength)

    # Relationship score
    if connection.relationship_score is not None:
        relationship_score = float(connection.relationship_score)
    else:
        relationship_score = DEGREE_BASE_SCORE.get(connection.degree, 0.15)

    if getattr(connection, "has_interacted", False):
        relationship_score = min(1.0, relationship_score + INTERACTION_BOOST)

    # Timing score — linear decay over 24 hours
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    hours_old = (now - posted_at).total_seconds() / 3600
    timing_score = max(0.0, 1.0 - (hours_old / 24))

    # Combined weighted score
    combined = (
        boosted_relevance   * w["relevance"] +
        relationship_score  * w["relationship"] +
        timing_score        * w["timing"]
    )
    combined = min(1.0, max(0.0, combined))

    if combined >= 0.80:
        priority = Priority.HIGH
    elif combined >= 0.55:
        priority = Priority.MEDIUM
    else:
        priority = Priority.LOW

    return ScoringResult(
        relevance_score=boosted_relevance,
        relationship_score=relationship_score,
        timing_score=timing_score,
        combined_score=combined,
        priority=priority,
    )
