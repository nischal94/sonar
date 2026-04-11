import asyncio
import logging
from app.delivery.slack import SlackSender
from app.delivery.email import EmailSender
from app.delivery.telegram import TelegramSender
from app.delivery.whatsapp import WhatsAppSender

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

CHANNEL_SENDERS = {
    "slack": SlackSender,
    "email": EmailSender,
    "telegram": TelegramSender,
    "whatsapp": WhatsAppSender,
}


class DeliveryRouter:
    def __init__(self, senders: dict[str, type] | None = None):
        # Constructor-injected sender registry. Defaults to the module-level
        # CHANNEL_SENDERS so production call sites stay unchanged. Tests pass
        # a fake registry directly instead of monkey-patching globals.
        self._senders = senders if senders is not None else CHANNEL_SENDERS

    async def deliver(self, alert, workspace=None, db=None) -> None:
        """
        Fan-out alert to all configured channels that meet the priority threshold.
        Fetches workspace from db if not provided.
        """
        if workspace is None and db is not None:
            from app.models.workspace import Workspace
            workspace = await db.get(Workspace, alert.workspace_id)

        if not workspace:
            return

        channels = workspace.delivery_channels or {}
        alert_priority_value = PRIORITY_ORDER.get(alert.priority, 1)

        # Track channel names alongside tasks so gather results can be
        # correlated back to their channel when logging failures.
        invoked_channels: list[str] = []
        tasks = []
        for channel_name, config in channels.items():
            min_priority = config.get("min_priority", "low")
            min_value = PRIORITY_ORDER.get(min_priority, 1)

            if alert_priority_value >= min_value:
                sender_class = self._senders.get(channel_name)
                if sender_class:
                    sender = sender_class()
                    tasks.append(sender.send(alert=alert, workspace=workspace))
                    invoked_channels.append(channel_name)

        if not tasks:
            return

        # return_exceptions=True so one failing channel never cancels siblings.
        # Each result is inspected below and logged if it's an exception, so
        # failures surface in logs instead of being silently swallowed.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for channel_name, result in zip(invoked_channels, results):
            if isinstance(result, Exception):
                logger.error(
                    "[DeliveryRouter] Channel send failed: %s. "
                    "channel=%s alert_id=%s workspace_id=%s",
                    result,
                    channel_name,
                    getattr(alert, "id", None),
                    getattr(workspace, "id", None),
                    exc_info=result,
                )
