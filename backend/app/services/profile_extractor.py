import json
import httpx
from dataclasses import dataclass
from app.services.llm import llm_client

PROFILE_EXTRACTION_PROMPT = """
Analyze this company's website/document to build a sales intelligence capability profile.

CONTENT:
{content}

Return a JSON object with exactly these fields:
- company_name: string
- company_description: 2-3 sentence summary of what they do
- primary_services: list of specific services/products offered
- target_customers: list of industries, roles, or company sizes they serve
- pain_points_solved: list of specific problems they solve
- technologies_used: list of tech stack, tools, platforms they work with
- signal_keywords: list of 20-30 keywords/phrases that would indicate a prospect needs this company (what would someone post about on LinkedIn if they needed this company?)
- anti_keywords: list of 10-15 phrases indicating irrelevance (e.g. job seekers, unrelated topics)
- capability_summary: A single dense paragraph (150-200 words) covering ALL capabilities. Written to maximize semantic vector search coverage — not marketing copy.

Respond with valid JSON only. No preamble, no markdown fences.
"""


@dataclass
class CapabilityProfile:
    company_name: str
    company_description: str
    primary_services: list[str]
    target_customers: list[str]
    pain_points_solved: list[str]
    technologies_used: list[str]
    signal_keywords: list[str]
    anti_keywords: list[str]
    capability_summary: str


async def fetch_url_content(url: str) -> str:
    """Fetch and return text content from a URL."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:12000]


async def extract_capability_profile(
    text: str | None = None,
    url: str | None = None,
) -> CapabilityProfile:
    """
    Extract capability profile from either raw text or a URL.
    Uses GPT-4o for highest quality — this runs once at onboarding.
    """
    if not text and not url:
        raise ValueError("Either text or url must be provided")

    content = text or await fetch_url_content(url)
    prompt = PROFILE_EXTRACTION_PROMPT.format(content=content)

    raw = await llm_client.complete(prompt=prompt, model="gpt-4o")

    # Strip markdown fences if model adds them despite instruction
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return CapabilityProfile(**data)
