import asyncio
import resend
from app.config import get_settings


class EmailSender:
    def __init__(self):
        settings = get_settings()
        resend.api_key = settings.resend_api_key
        self._from_email = settings.resend_from_email

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("email", {})
        to_email = config.get("address")
        if not to_email:
            return

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            alert.priority, "⚪"
        )
        subject = f"{priority_emoji} Sonar Signal — {alert.opportunity_type.replace('_', ' ').title()}"

        relationship_segment = (
            f"Relationship: {alert.relationship_score:.0%} | "
            if alert.relationship_score is not None
            else ""
        )
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
            {relationship_segment}Timing: {alert.timing_score:.0%} |
            Combined: {alert.combined_score:.0%}
        </p>
        """

        # resend.Emails.send is a blocking HTTP call; run it in a thread so
        # we don't block the event loop.
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": self._from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            },
        )

    async def send_backfill_complete(self, workspace, profile_count: int) -> None:
        """One-time onboarding email sent when Day-One Backfill finishes."""
        config = (
            workspace.delivery_channels.get("email", {})
            if workspace.delivery_channels
            else {}
        )
        to_email = config.get("address")
        if not to_email:
            return

        subject = "Your Sonar dashboard is ready"
        html = f"""
        <h2>Your Sonar dashboard is ready</h2>
        <p>We've finished scanning <strong>{profile_count}</strong> people in your network for buying-intent signals over the past 60 days.</p>
        <p>Open your dashboard to see who's showing intent right now:</p>
        <p><a href="http://localhost:5173/dashboard">Open Sonar Dashboard</a></p>
        <p>Going forward, new signals flow into your dashboard automatically as the extension observes your LinkedIn feed.</p>
        """

        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": self._from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            },
        )
