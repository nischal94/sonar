from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import get_settings


class EmailSender:
    def __init__(self):
        self._client = SendGridAPIClient(get_settings().sendgrid_api_key)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("email", {})
        to_email = config.get("address")
        if not to_email:
            return

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")
        subject = f"{priority_emoji} Sonar Signal — {alert.opportunity_type.replace('_', ' ').title()}"

        html = f"""
        <h2>{priority_emoji} {alert.priority.upper()} SIGNAL</h2>
        <p><strong>Why it matches:</strong><br>{alert.match_reason}</p>
        <p><strong>Urgency:</strong> {alert.urgency_reason}</p>
        <hr>
        <p><strong>Draft A (Direct):</strong><br><em>{alert.outreach_draft_a}</em></p>
        <p><strong>Draft B (Question):</strong><br><em>{alert.outreach_draft_b}</em></p>
        <hr>
        <p>
            Scores — Relevance: {alert.relevance_score:.0%} |
            Relationship: {alert.relationship_score:.0%} |
            Timing: {alert.timing_score:.0%} |
            Combined: {alert.combined_score:.0%}
        </p>
        """

        message = Mail(
            from_email=get_settings().sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        self._client.send(message)
