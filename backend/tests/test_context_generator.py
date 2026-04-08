import pytest
from unittest.mock import AsyncMock, patch
from app.services.context_generator import generate_alert_context, AlertContext
from app.services.scorer import Priority


@pytest.mark.asyncio
async def test_generates_context_with_all_required_fields():
    mock_response = """{
        "match_reason": "John is evaluating AI agents for sales, which matches your core service offering of building custom AI agents.",
        "outreach_draft_a": "Hey John, saw your post about evaluating AI agents for sales — we have helped 3 SaaS companies with exactly this. Worth a quick 20-min call?",
        "outreach_draft_b": "John — curious what specific sales workflow you are trying to automate? We have been seeing this challenge come up a lot lately.",
        "opportunity_type": "service_need",
        "urgency_reason": "Post is fresh and the evaluation is actively underway."
    }"""

    with patch("app.services.context_generator.openai_provider") as mock_openai, \
         patch("app.services.context_generator.groq_provider") as mock_groq:

        mock_openai.complete = AsyncMock(return_value=mock_response)
        mock_groq.complete = AsyncMock(return_value=mock_response)

        context = await generate_alert_context(
            post_content="We're actively evaluating AI agent platforms for our sales team.",
            author_name="John Smith",
            author_headline="VP Sales at Acme Corp",
            author_company="Acme Corp",
            degree=1,
            enrichment_summary="Acme Corp: 200 employees, Series B, CRM stack includes Salesforce.",
            capability_profile="We build custom AI agents for B2B sales teams integrating with CRM systems.",
            priority=Priority.HIGH,
        )

    assert isinstance(context, AlertContext)
    assert len(context.match_reason) > 10
    assert len(context.outreach_draft_a) > 10
    assert len(context.outreach_draft_b) > 10
    assert context.opportunity_type in ["service_need", "product_pain", "hiring_signal", "funding_signal", "competitive_mention", "general_interest"]
    assert len(context.urgency_reason) > 5


@pytest.mark.asyncio
async def test_high_priority_uses_openai_not_groq():
    mock_response = """{
        "match_reason": "Relevant.",
        "outreach_draft_a": "Draft A.",
        "outreach_draft_b": "Draft B.",
        "opportunity_type": "service_need",
        "urgency_reason": "Fresh signal."
    }"""

    with patch("app.services.context_generator.openai_provider") as mock_openai, \
         patch("app.services.context_generator.groq_provider") as mock_groq:

        mock_openai.complete = AsyncMock(return_value=mock_response)
        mock_groq.complete = AsyncMock(return_value=mock_response)

        await generate_alert_context(
            post_content="Need AI help.",
            author_name="Jane", author_headline="CTO", author_company="Corp",
            degree=1, enrichment_summary="", capability_profile="We build AI agents.",
            priority=Priority.HIGH,
        )

        mock_openai.complete.assert_called_once()
        mock_groq.complete.assert_not_called()
