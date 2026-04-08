import httpx

PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


class SlackSender:
    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("slack", {})
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            return

        emoji = PRIORITY_EMOJI.get(alert.priority, "⚪")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {alert.priority.upper()} SIGNAL"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Why it matches:*\n{alert.match_reason}"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Relevance: `{_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}\n"
                        f"Relationship: `{_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}\n"
                        f"Timing: `{_score_bar(alert.timing_score)}` {alert.timing_score:.0%}"
                    )
                }
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Draft A (Direct):*\n_{alert.outreach_draft_a}_"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Draft B (Question):*\n_{alert.outreach_draft_b}_"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Acted"},
                        "action_id": f"acted_{alert.id}",
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✗ Not Relevant"},
                        "action_id": f"irrelevant_{alert.id}"
                    }
                ]
            }
        ]

        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"blocks": blocks})
