import pytest
from unittest.mock import AsyncMock, patch
from app.services.context_generator import generate_alert_context, AlertContext
from app.services.scorer import Priority


@pytest.mark.asyncio
async def test_alert_context_should_include_themes():
    fake_response = (
        '{"match_reason": "They need data tooling.", '
        '"outreach_draft_a": "Hey — saw your post about pipelines.", '
        '"outreach_draft_b": "Curious: what broke in your stack?", '
        '"opportunity_type": "product_pain", '
        '"urgency_reason": "Active pain right now.", '
        '"themes": ["data pipelines", "migration pain", "tooling gap"]}'
    )

    with patch("app.services.context_generator.openai_provider") as mock_provider:
        mock_provider.complete = AsyncMock(return_value=fake_response)
        context = await generate_alert_context(
            post_content="Our data pipeline broke again.",
            author_name="Alice",
            author_headline="VP Eng at Foo",
            author_company="Foo Inc",
            degree=1,
            enrichment_summary="",
            capability_profile="We sell data tooling.",
            priority=Priority.HIGH,
        )

    assert isinstance(context, AlertContext)
    assert context.themes == ["data pipelines", "migration pain", "tooling gap"]
    assert context.match_reason == "They need data tooling."


@pytest.mark.asyncio
async def test_alert_context_defaults_themes_to_empty_list_when_missing():
    fake_response = (
        '{"match_reason": "They need data tooling.", '
        '"outreach_draft_a": "Hey.", '
        '"outreach_draft_b": "Curious?", '
        '"opportunity_type": "product_pain", '
        '"urgency_reason": "Active."}'
    )

    with patch("app.services.context_generator.openai_provider") as mock_provider:
        mock_provider.complete = AsyncMock(return_value=fake_response)
        context = await generate_alert_context(
            post_content="Our data pipeline broke again.",
            author_name="Alice",
            author_headline="VP Eng",
            author_company="Foo",
            degree=1,
            enrichment_summary="",
            capability_profile="We sell tools.",
            priority=Priority.HIGH,
        )

    assert context.themes == []
