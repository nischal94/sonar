from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from app.config import get_settings


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


class TelegramSender:
    def __init__(self):
        self._bot = Bot(token=get_settings().telegram_bot_token)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("telegram", {})
        chat_id = config.get("chat_id")
        if not chat_id:
            return

        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")

        text = (
            f"{emoji} *{alert.priority.upper()} SIGNAL*\n\n"
            f"🎯 *Why it matches:*\n{alert.match_reason}\n\n"
            f"📊 Relevance: `{_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}\n"
            f"📊 Relationship: `{_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}\n"
            f"📊 Timing: `{_score_bar(alert.timing_score)}` {alert.timing_score:.0%}\n\n"
            f"✉️ *Draft A \\(Direct\\):*\n_{alert.outreach_draft_a}_\n\n"
            f"✉️ *Draft B \\(Question\\):*\n_{alert.outreach_draft_b}_"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✓ Acted", callback_data=f"acted_{alert.id}"),
                InlineKeyboardButton("✗ Not Relevant", callback_data=f"irrelevant_{alert.id}")
            ]
        ])

        await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
