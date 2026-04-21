"""Fit × Intent hybrid scoring — Phase 2.6.

Pure functions. No DB, no LLM, no async. Import-safe from workers and scripts.

Design reference: docs/phase-2-6/design.md §3.2, §3.5.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero.

    Pure-Python implementation — acceptable for the scoring layer where
    this runs once per post-connection pair at pipeline time. If a future
    caller batches thousands of pairs (e.g. a bulk re-embedding job),
    migrate to numpy or defer to pgvector's `<=>` operator at the DB layer.
    """
    if len(a) != len(b):
        raise ValueError(f"[fit_scorer] dimension mismatch: a={len(a)}, b={len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def compute_fit_score(
    icp_embedding: Sequence[float],
    seller_mirror_embedding: Sequence[float],
    connection_embedding: Sequence[float],
    lambda_: float,
) -> float:
    """fit_score = max(0, cos(ICP, conn) - λ·cos(seller_mirror, conn)).

    Floored at 0: anti-ICP connections (raw < 0) get suppressed to 0, not
    ranked negatively. Multiplying a negative fit by a positive intent
    would invert ordering — not the intended behavior.

    Raises ValueError on negative lambda_ or mismatched dimensions.
    """
    if lambda_ < 0:
        raise ValueError(f"lambda_ must be non-negative, got {lambda_}")
    if not (
        len(icp_embedding) == len(seller_mirror_embedding) == len(connection_embedding)
    ):
        raise ValueError(
            f"[fit_scorer] embedding dimensions must match: "
            f"icp={len(icp_embedding)}, "
            f"mirror={len(seller_mirror_embedding)}, "
            f"conn={len(connection_embedding)}"
        )

    icp_cos = cosine_similarity(icp_embedding, connection_embedding)
    mirror_cos = cosine_similarity(seller_mirror_embedding, connection_embedding)
    raw = icp_cos - lambda_ * mirror_cos
    return max(0.0, raw)


def compute_intent_score(
    relevance_score: float,
    posted_at: datetime,
    *,
    now: datetime | None = None,
) -> float:
    """intent_score = 0.7·relevance + 0.3·timing. No relationship axis.

    Relationship moves to the dashboard degree filter per design §3.5.
    Timing decays linearly to 0 over 24 hours.
    """
    now = now or datetime.now(timezone.utc)
    # Ensure posted_at is timezone-aware
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    hours_old = max(0.0, (now - posted_at).total_seconds() / 3600.0)
    timing = max(0.0, 1.0 - hours_old / 24.0)
    relevance = max(0.0, min(1.0, relevance_score))
    return max(0.0, min(1.0, 0.7 * relevance + 0.3 * timing))


def compute_hybrid_score(fit_score: float, intent_score: float) -> float:
    """final_score = fit_score × intent_score, clamped to [0, 1]."""
    return max(0.0, min(1.0, fit_score * intent_score))
