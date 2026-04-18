import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.dashboard import DashboardPerson, DashboardPeopleResponse


def test_dashboard_person_accepts_minimum_fields():
    p = DashboardPerson(
        connection_id=uuid4(),
        name="Jane Doe",
        title=None,
        company=None,
        relationship_degree=1,
        mutual_count=None,
        aggregate_score=0.82,
        trend_direction="up",
        last_signal_at=datetime.now(timezone.utc),
        recent_post_snippet=None,
        matching_signal_phrase=None,
        recent_post_url=None,
    )
    assert p.relationship_degree == 1


def test_relationship_degree_must_be_1_or_2():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=3,
            mutual_count=None,
            aggregate_score=0.5,
            trend_direction="flat",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_trend_direction_enum():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=1,
            mutual_count=None,
            aggregate_score=0.5,
            trend_direction="sideways",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_aggregate_score_bounds():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=1,
            mutual_count=None,
            aggregate_score=1.5,
            trend_direction="flat",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_response_shape():
    r = DashboardPeopleResponse(people=[], threshold_used=0.65, total=0)
    assert r.total == 0
