import logging
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
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

    # Constructor-inject a fake sender registry — no module-level patching needed.
    router = DeliveryRouter(senders={"slack": mock_class})
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

    router = DeliveryRouter(senders={"slack": mock_class})
    await router.deliver(alert=alert, workspace=workspace)

    mock_instance.send.assert_not_called()


@pytest.mark.asyncio
async def test_router_logs_channel_failure_and_continues_siblings(caplog):
    """A failing sender must not cancel sibling channels, and its exception
    must be logged with channel + alert_id + workspace_id context instead of
    being silently swallowed by asyncio.gather(return_exceptions=True)."""
    alert = make_alert(priority="high")
    workspace = SimpleNamespace(
        id=uuid4(),
        delivery_channels={
            "slack": {"webhook_url": "https://hooks.slack.com/test", "min_priority": "low"},
            "email": {"to": "ops@example.com", "min_priority": "low"},
        },
    )

    # Slack raises; email succeeds. Both must be invoked (siblings preserved).
    slack_class, slack_instance = _mock_sender_class()
    slack_instance.send = AsyncMock(side_effect=RuntimeError("slack webhook 500"))
    email_class, email_instance = _mock_sender_class()

    router = DeliveryRouter(senders={"slack": slack_class, "email": email_class})

    with caplog.at_level(logging.ERROR, logger="app.delivery.router"):
        await router.deliver(alert=alert, workspace=workspace)

    slack_instance.send.assert_called_once()
    email_instance.send.assert_called_once()

    failure_records = [r for r in caplog.records if r.name == "app.delivery.router"]
    assert len(failure_records) == 1, "expected exactly one error log for the failing channel"
    msg = failure_records[0].getMessage()
    assert "slack" in msg
    assert "slack webhook 500" in msg
    assert str(alert.id) in msg
    assert str(workspace.id) in msg
    # Pin the `exc_info=result` kwarg so a regression that drops it (silently
    # losing the stack trace in logs) fails loudly instead of sneaking through.
    assert failure_records[0].exc_info is not None
    assert failure_records[0].exc_info[1] is slack_instance.send.side_effect
