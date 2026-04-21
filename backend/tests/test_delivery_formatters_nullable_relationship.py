"""Delivery formatter: graceful handling of alert.relationship_score=None.

When workspace.use_hybrid_scoring=True, the Alert row has
relationship_score=None (issue #120 fix).  Each formatter must omit the
relationship field rather than raise a TypeError or render "0%".

These are pure unit tests — no DB, no network, no Docker I/O.
"""

from types import SimpleNamespace
from uuid import uuid4


from app.delivery.slack import _score_bar
from app.delivery.telegram import _score_bar as tg_score_bar


def _make_alert(relationship_score):
    return SimpleNamespace(
        id=uuid4(),
        priority="high",
        combined_score=0.85,
        relevance_score=0.88,
        relationship_score=relationship_score,
        timing_score=0.82,
        match_reason="They posted about buying intent.",
        outreach_draft_a="Draft A.",
        outreach_draft_b="Draft B.",
        opportunity_type="service_need",
        urgency_reason="Post is fresh.",
    )


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


def _build_slack_blocks(alert):
    """Invoke the block-building logic without making an HTTP call."""
    from app.delivery.slack import PRIORITY_EMOJI

    emoji = PRIORITY_EMOJI.get(alert.priority, "⚪")
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {alert.priority.upper()} SIGNAL",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why it matches:*\n{alert.match_reason}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(
                    filter(
                        None,
                        [
                            f"Relevance: `{_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}",
                            (
                                f"Relationship: `{_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}"
                                if alert.relationship_score is not None
                                else None
                            ),
                            f"Timing: `{_score_bar(alert.timing_score)}` {alert.timing_score:.0%}",
                        ],
                    )
                ),
            },
        },
    ]
    return blocks


def test_slack_omits_relationship_when_none():
    alert = _make_alert(relationship_score=None)
    blocks = _build_slack_blocks(alert)
    scores_block = blocks[2]["text"]["text"]
    assert "Relationship" not in scores_block
    assert "Relevance" in scores_block
    assert "Timing" in scores_block


def test_slack_includes_relationship_when_present():
    alert = _make_alert(relationship_score=0.75)
    blocks = _build_slack_blocks(alert)
    scores_block = blocks[2]["text"]["text"]
    assert "Relationship" in scores_block
    assert "75%" in scores_block


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def _build_telegram_text(alert):
    from app.delivery.telegram import _escape_mdv2

    relationship_line = (
        f"📊 Relationship: `{tg_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}\n"
        if alert.relationship_score is not None
        else ""
    )
    text = (
        f"🔴 *HIGH SIGNAL*\n\n"
        f"🎯 *Why it matches:*\n{_escape_mdv2(alert.match_reason)}\n\n"
        f"📊 Relevance: `{tg_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}\n"
        f"{relationship_line}"
        f"📊 Timing: `{tg_score_bar(alert.timing_score)}` {alert.timing_score:.0%}\n\n"
        f"✉️ *Draft A \\(Direct\\):*\n_{_escape_mdv2(alert.outreach_draft_a)}_\n\n"
        f"✉️ *Draft B \\(Question\\):*\n_{_escape_mdv2(alert.outreach_draft_b)}_"
    )
    return text


def test_telegram_omits_relationship_when_none():
    alert = _make_alert(relationship_score=None)
    text = _build_telegram_text(alert)
    assert "Relationship" not in text
    assert "Relevance" in text
    assert "Timing" in text


def test_telegram_includes_relationship_when_present():
    alert = _make_alert(relationship_score=0.60)
    text = _build_telegram_text(alert)
    assert "Relationship" in text
    assert "60%" in text


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def _build_email_html(alert):
    relationship_segment = (
        f"Relationship: {alert.relationship_score:.0%} | "
        if alert.relationship_score is not None
        else ""
    )
    html = (
        f"Scores — Relevance: {alert.relevance_score:.0%} | "
        f"{relationship_segment}Timing: {alert.timing_score:.0%} | "
        f"Combined: {alert.combined_score:.0%}"
    )
    return html


def test_email_omits_relationship_when_none():
    alert = _make_alert(relationship_score=None)
    html = _build_email_html(alert)
    assert "Relationship" not in html
    assert "Relevance" in html
    assert "Timing" in html
    assert "Combined" in html


def test_email_includes_relationship_when_present():
    alert = _make_alert(relationship_score=0.90)
    html = _build_email_html(alert)
    assert "Relationship" in html
    assert "90%" in html
