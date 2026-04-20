"""Unit tests for the metrics helpers used by analyze-hybrid."""

from scripts.calibrate_matching import (
    precision_at_k,
    recall_at_k,
    competitor_count_in_top_k,
)


def test_precision_at_5_mixed_ranking():
    # 3 of top-5 are true matches → 0.6
    # Each item is (score, is_match, is_competitor).
    ranked = [
        (0.9, True, False),
        (0.8, False, False),
        (0.7, True, False),
        (0.6, True, False),
        (0.5, False, False),
        (0.4, True, False),
    ]
    assert precision_at_k(ranked, k=5) == 0.6


def test_precision_at_5_fewer_than_k():
    ranked = [(0.9, True, False), (0.8, True, False)]
    assert precision_at_k(ranked, k=5) == 1.0  # 2/2


def test_recall_half_caught():
    ranked = [
        (0.9, True, False),
        (0.8, False, False),
        (0.7, True, False),
        (0.6, False, False),
        (0.5, True, False),
        (0.4, True, False),
    ]
    # top-5 has 3 true matches; total true matches = 4 → 3/4 = 0.75
    assert recall_at_k(ranked, k=5) == 0.75


def test_competitor_count_in_top_5():
    ranked = [
        (0.9, True, False),
        (0.85, False, True),
        (0.8, False, True),
        (0.7, True, False),
        (0.6, False, False),
    ]
    assert competitor_count_in_top_k(ranked, k=5) == 2


def test_competitor_count_zero_when_none_flagged():
    ranked = [(0.9, True, False)] * 5
    assert competitor_count_in_top_k(ranked, k=5) == 0
