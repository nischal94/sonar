from twilio.rest import Client
from app.config import get_settings


class WhatsAppSender:
    def __init__(self):
        self._client = Client(get_settings().twilio_account_sid, get_settings().twilio_auth_token)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("whatsapp", {})
        to_phone = config.get("phone")
        if not to_phone:
            return

        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")
        short_id = str(alert.id)[:8]

        body = (
            f"{emoji} *Sonar Signal* [{alert.priority.upper()}]\n\n"
            f"Why it matches: {alert.match_reason}\n\n"
            f"Draft: {alert.outreach_draft_a}\n\n"
            f"Ref: {short_id}"
        )

        self._client.messages.create(
            from_=get_settings().twilio_whatsapp_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
