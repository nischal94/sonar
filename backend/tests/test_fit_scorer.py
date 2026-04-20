"""Unit tests for fit_scorer — pure math, no DB, no LLM."""

from datetime import datetime, timedelta, timezone
import math

import pytest

from app.services.fit_scorer import (
    cosine_similarity,
    compute_fit_score,
    compute_intent_score,
    compute_hybrid_score,
)


# ---------- cosine_similarity ----------


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert math.isclose(cosine_similarity(v, v), 1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_cosine_similarity_opposite_vectors():
    assert math.isclose(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)


def test_cosine_similarity_zero_vector_returns_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# ---------- compute_fit_score ----------


def test_fit_score_pure_icp_match_no_seller_signal():
    # ICP matches perfectly; seller signal absent
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [1.0, 0.0, 0.0]  # perfect ICP, zero seller
    fit = compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.3)
    assert math.isclose(fit, 1.0, abs_tol=1e-6)


def test_fit_score_pure_seller_match_floored_at_zero():
    # Connection is a perfect seller mirror, nothing like ICP
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.0, 1.0, 0.0]  # perfect mirror → raw = 0 - 0.3*1 = -0.3
    fit = compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.3)
    assert fit == 0.0, "negative raw fit must floor at 0"


def test_fit_score_lambda_zero_equals_raw_icp_cosine():
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.8, 0.6, 0.0]
    expected = cosine_similarity(icp_emb, conn_emb)  # 0.8
    assert math.isclose(
        compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.0),
        expected,
        abs_tol=1e-6,
    )


def test_fit_score_lambda_one_subtracts_full_mirror_term():
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.8, 0.6, 0.0]
    # raw = 0.8 - 1.0*0.6 = 0.2
    assert math.isclose(
        compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=1.0),
        0.2,
        abs_tol=1e-6,
    )


def test_fit_score_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        compute_fit_score([1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0], lambda_=0.3)


def test_fit_score_negative_lambda_raises():
    with pytest.raises(ValueError):
        compute_fit_score([1.0], [0.5], [1.0], lambda_=-0.1)


# ---------- compute_intent_score ----------


def test_intent_score_fresh_post_full_relevance():
    now = datetime.now(timezone.utc)
    score = compute_intent_score(relevance_score=1.0, posted_at=now)
    assert math.isclose(score, 1.0, abs_tol=1e-3)  # 0.7*1 + 0.3*1 = 1


def test_intent_score_stale_post_timing_decayed_to_zero():
    then = datetime.now(timezone.utc) - timedelta(hours=48)
    score = compute_intent_score(relevance_score=1.0, posted_at=then)
    # relevance 1 * 0.7 + timing 0 * 0.3 = 0.7
    assert math.isclose(score, 0.7, abs_tol=1e-3)


def test_intent_score_mid_decay():
    then = datetime.now(timezone.utc) - timedelta(hours=12)
    score = compute_intent_score(relevance_score=0.5, posted_at=then)
    # relevance 0.5 * 0.7 + timing 0.5 * 0.3 = 0.35 + 0.15 = 0.5
    assert math.isclose(score, 0.5, abs_tol=1e-2)


def test_intent_score_clamped_to_unit_interval():
    now = datetime.now(timezone.utc)
    assert 0.0 <= compute_intent_score(relevance_score=0.0, posted_at=now) <= 1.0
    assert 0.0 <= compute_intent_score(relevance_score=1.5, posted_at=now) <= 1.0


# ---------- compute_hybrid_score ----------


def test_hybrid_score_multiplies_fit_and_intent():
    assert math.isclose(compute_hybrid_score(fit_score=0.4, intent_score=0.9), 0.36)


def test_hybrid_score_zero_fit_suppresses():
    """The Lipi Mittal fix: low fit zeros out regardless of intent."""
    assert compute_hybrid_score(fit_score=0.0, intent_score=0.95) == 0.0


def test_hybrid_score_zero_intent_suppresses():
    assert compute_hybrid_score(fit_score=0.8, intent_score=0.0) == 0.0


def test_hybrid_score_clamps_to_unit_interval():
    assert compute_hybrid_score(fit_score=1.0, intent_score=1.0) == 1.0
