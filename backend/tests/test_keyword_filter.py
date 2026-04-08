import pytest
from app.services.keyword_filter import keyword_prefilter

def test_blocks_birthday_post():
    result = keyword_prefilter(
        content="Happy birthday to my amazing colleague Sarah!",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=["happy birthday"]
    )
    assert result is False

def test_blocks_post_with_no_signal_words():
    result = keyword_prefilter(
        content="Just had an amazing lunch at this new Italian place downtown.",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=[]
    )
    assert result is False

def test_passes_relevant_post():
    result = keyword_prefilter(
        content="We're evaluating AI automation tools for our data pipeline. Any recommendations?",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=[]
    )
    assert result is True

def test_blocks_open_to_work():
    result = keyword_prefilter(
        content="Excited to share that I'm open to work! Looking for a senior data role.",
        signal_keywords=["data", "pipeline"],
        anti_keywords=["open to work", "looking for"]
    )
    assert result is False
