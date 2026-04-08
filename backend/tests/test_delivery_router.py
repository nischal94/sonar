import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from app.delivery.router import DeliveryRouter


def make_alert(priority: str = "high"):
    from types import SimpleNamespace
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


def make_workspace_with_slack():
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid4(),
        delivery_channels={"slack": {"webhook_url": "https://hooks.slack.com/test", "min_priority": "low"}},
    )


@pytest.mark.asyncio
async def test_router_calls_slack_for_configured_workspace():
    alert = make_alert(priority="high")
    workspace = make_workspace_with_slack()

    with patch("app.delivery.router.SlackSender") as MockSlack:
        mock_instance = MagicMock()
        mock_instance.send = AsyncMock()
        MockSlack.return_value = mock_instance

        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace)

        mock_instance.send.assert_called_once()


@pytest.mark.asyncio
async def test_router_skips_channel_below_min_priority():
    alert = make_alert(priority="low")
    workspace_with_high_threshold = __import__("types").SimpleNamespace(
        id=uuid4(),
        delivery_channels={
            "slack": {"webhook_url": "https://hooks.slack.com/test", "min_priority": "high"}
        },
    )

    with patch("app.delivery.router.SlackSender") as MockSlack:
        mock_instance = MagicMock()
        mock_instance.send = AsyncMock()
        MockSlack.return_value = mock_instance

        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace_with_high_threshold)

        mock_instance.send.assert_not_called()
