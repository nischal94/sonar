import json
import httpx
from dataclasses import dataclass
from app.config import OPENAI_MODEL_EXPENSIVE
from app.services.llm import llm_client, LLMProvider
from app.prompts import extract_icp_and_seller_mirror as icp_prompt

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
    llm_override: LLMProvider | None = None,
) -> CapabilityProfile:
    """
    Extract capability profile from either raw text or a URL.
    Uses GPT-4o for highest quality — this runs once at onboarding.

    `llm_override` is optional so existing callers keep working; when omitted,
    the module-level `llm_client` is used. Routers that want to inject a test
    double via FastAPI Depends should pass it explicitly. Parameter is named
    `llm_override` (not `llm_client`) so it doesn't shadow the module-level
    name that existing tests patch.
    """
    if not text and not url:
        raise ValueError("Either text or url must be provided")

    content = text or await fetch_url_content(url)
    prompt = PROFILE_EXTRACTION_PROMPT.format(content=content)

    client = llm_override if llm_override is not None else llm_client
    raw = await client.complete(prompt=prompt, model=OPENAI_MODEL_EXPENSIVE)

    # Strip markdown fences if model adds them despite instruction
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return CapabilityProfile(**data)


async def extract_icp_and_seller_mirror(
    *,
    source_text: str,
    llm_override=None,
) -> tuple[str, str]:
    """Call the ICP+seller_mirror prompt. Returns (icp, seller_mirror) strings.

    Parse JSON, minimal schema check. Raises ValueError on malformed output.
    """
    from app.services.llm import get_llm_client

    llm = llm_override or get_llm_client()
    user_msg = icp_prompt.build_user_message(source_text=source_text)

    raw = await llm.complete(
        prompt=user_msg,
        system=icp_prompt.SYSTEM_PROMPT,
        model=OPENAI_MODEL_EXPENSIVE,
        max_tokens=1200,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"[profile_extractor] ICP prompt returned non-JSON: {e}. Raw: {raw[:200]}"
        )
    if "icp" not in parsed or "seller_mirror" not in parsed:
        raise ValueError(
            f"[profile_extractor] ICP response missing required keys. Got: {list(parsed.keys())}"
        )
    return parsed["icp"], parsed["seller_mirror"]
