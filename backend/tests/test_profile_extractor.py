import pytest
from unittest.mock import AsyncMock, patch
from app.services.profile_extractor import extract_capability_profile

@pytest.mark.asyncio
async def test_extract_from_text():
    sample_text = """
    Acme AI Agency builds custom AI agents for B2B sales teams.
    We specialize in integrating LLMs with existing CRM systems like Salesforce and HubSpot.
    Our clients are mid-market SaaS companies struggling with sales automation.
    """

    with patch("app.services.profile_extractor.llm_client") as mock_llm:
        mock_llm.complete = AsyncMock(return_value="""{
            "company_name": "Acme AI Agency",
            "company_description": "Builds custom AI agents for B2B sales teams.",
            "primary_services": ["custom AI agents", "LLM integration", "sales automation"],
            "target_customers": ["mid-market SaaS companies"],
            "pain_points_solved": ["sales automation", "CRM integration"],
            "technologies_used": ["LLMs", "Salesforce", "HubSpot"],
            "signal_keywords": ["AI agent", "sales automation", "CRM integration", "LLM"],
            "anti_keywords": ["looking for job", "open to work"],
            "capability_summary": "Acme AI Agency builds custom AI agents and LLM integrations for B2B sales teams at mid-market SaaS companies, solving sales automation and CRM integration challenges."
        }""")

        profile = await extract_capability_profile(text=sample_text)

    assert profile.company_name == "Acme AI Agency"
    assert "AI agent" in profile.signal_keywords
    assert len(profile.signal_keywords) >= 4
    assert profile.capability_summary != ""
