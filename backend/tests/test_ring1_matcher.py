import pytest
from dataclasses import dataclass
from app.services.ring1_matcher import match_post_to_ring1_signals


@dataclass
class FakeSignal:
    id: str
    phrase: str
    enabled: bool = True


def test_should_match_exact_phrase():
    signals = [FakeSignal(id="s1", phrase="struggling to hire senior engineers")]
    post = "We are struggling to hire senior engineers this quarter."
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s1"]


def test_should_match_case_insensitive():
    signals = [FakeSignal(id="s1", phrase="Series A")]
    post = "Just closed our series a round!"
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s1"]


def test_should_return_multiple_matches():
    signals = [
        FakeSignal(id="s1", phrase="hiring"),
        FakeSignal(id="s2", phrase="engineering"),
    ]
    post = "Hiring across engineering teams."
    result = match_post_to_ring1_signals(post, signals)
    assert set(result) == {"s1", "s2"}


def test_should_skip_disabled_signals():
    signals = [
        FakeSignal(id="s1", phrase="hiring", enabled=False),
        FakeSignal(id="s2", phrase="engineering", enabled=True),
    ]
    post = "Hiring across engineering teams."
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s2"]


def test_should_return_empty_list_when_no_matches():
    signals = [FakeSignal(id="s1", phrase="quantum computing")]
    post = "We just launched our new coffee blend."
    result = match_post_to_ring1_signals(post, signals)
    assert result == []


def test_should_handle_empty_signal_list():
    result = match_post_to_ring1_signals("any content", [])
    assert result == []
