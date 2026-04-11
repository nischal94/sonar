import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.delivery.router import DeliveryRouter


def make_alert(priority: str = "high"):
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        connection_id=uuid4(),
        priority=priority,
        combined_score=0.85,
        relevance_score=0.88,
        relationship_score=0.90,
        timing_score=0.82,
        match_reason="This is why it matches.",
        outreach_draft_a="Draft A message.",
        outreach_draft_b="Draft B message.",
        opportunity_type="service_need",
        urgency_reason="Post is fresh.",
    )


def make_workspace_with_slack(min_priority: str = "low"):
    return SimpleNamespace(
        id=uuid4(),
        delivery_channels={
            "slack": {
                "webhook_url": "https://hooks.slack.com/test",
                "min_priority": min_priority,
            }
        },
    )


def _mock_sender_class():
    """Build a sender-class mock that returns a mock instance whose .send is an AsyncMock."""
    mock_instance = MagicMock()
    mock_instance.send = AsyncMock()
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class, mock_instance


@pytest.mark.asyncio
async def test_router_calls_slack_for_configured_workspace():
    alert = make_alert(priority="high")
    workspace = make_workspace_with_slack()

    mock_class, mock_instance = _mock_sender_class()

    # Patch the CHANNEL_SENDERS dict directly. Patching `app.delivery.router.SlackSender`
    # does NOT work because CHANNEL_SENDERS was populated at import time with a direct
    # reference to the original SlackSender class — the dict entry doesn't follow
    # subsequent rebinding of the module-level name.
    with patch.dict("app.delivery.router.CHANNEL_SENDERS", {"slack": mock_class}):
        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace)

    mock_instance.send.assert_called_once()
    # Verify the sender was called with both alert and workspace
    _, kwargs = mock_instance.send.call_args
    assert kwargs["alert"] is alert
    assert kwargs["workspace"] is workspace


@pytest.mark.asyncio
async def test_router_skips_channel_below_min_priority():
    alert = make_alert(priority="low")
    workspace = make_workspace_with_slack(min_priority="high")

    mock_class, mock_instance = _mock_sender_class()

    with patch.dict("app.delivery.router.CHANNEL_SENDERS", {"slack": mock_class}):
        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace)

    mock_instance.send.assert_not_called()
