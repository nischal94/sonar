import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.feedback_trainer import process_feedback_adjustment


@pytest.mark.asyncio
async def test_raises_threshold_when_positive_rate_low():
    workspace = MagicMock()
    workspace.id = __import__("uuid").uuid4()
    workspace.matching_threshold = 0.72

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.add = MagicMock()

    recent_feedback = ["positive"] * 3 + ["negative"] * 17

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == pytest.approx(0.74, abs=1e-9)


@pytest.mark.asyncio
async def test_lowers_threshold_when_positive_rate_high():
    workspace = MagicMock()
    workspace.id = __import__("uuid").uuid4()
    workspace.matching_threshold = 0.72

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    recent_feedback = ["positive"] * 40 + ["negative"] * 10

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == pytest.approx(0.71, abs=1e-9)


@pytest.mark.asyncio
async def test_no_change_when_rate_in_acceptable_range():
    workspace = MagicMock()
    workspace.matching_threshold = 0.72
    mock_db = AsyncMock()

    recent_feedback = ["positive"] * 30 + ["negative"] * 20

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == pytest.approx(0.72)


@pytest.mark.asyncio
async def test_returns_unchanged_when_insufficient_feedback():
    workspace = MagicMock()
    workspace.matching_threshold = 0.72
    mock_db = AsyncMock()

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=["positive"] * 5,
        db=mock_db,
    )

    assert new_threshold == pytest.approx(0.72)
