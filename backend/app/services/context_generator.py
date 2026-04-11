import json
from dataclasses import dataclass, field
from app.services.llm import openai_provider, groq_provider
from app.services.scorer import Priority

CONTEXT_GENERATION_PROMPT = """
You are a B2B sales intelligence assistant.

COMPANY CAPABILITY PROFILE:
{capability_profile}

LINKEDIN POST:
Author: {author_name}, {author_headline} at {author_company}
Connection degree: {degree}
Company context: {enrichment_summary}
Post content: {post_content}

Return a JSON object with exactly these fields:
- match_reason: 2 sentences max. Why is this post relevant to the company's capabilities? Be specific — reference both the post and what the company does.
- outreach_draft_a: A Direct style LinkedIn message. Max 4 sentences. Reference the specific post. No emojis, no "I hope this finds you well." Sound like a human.
- outreach_draft_b: A Question-led style LinkedIn message. Opens with a curious question about their specific situation. Max 3 sentences.
- opportunity_type: exactly one of: service_need, product_pain, hiring_signal, funding_signal, competitive_mention, general_interest
- urgency_reason: One sentence on why timing matters for this specific signal.
- themes: Array of 3-5 short semantic theme tags describing what this post is about at a concept level. Examples: ["engineering hiring", "team scaling"], ["data pipelines", "ETL", "migration pain"]. These are used for trending topic aggregation, not for the match reason. Keep each theme under 4 words.

Valid JSON only. No preamble, no markdown fences.
"""


@dataclass
class AlertContext:
    match_reason: str
    outreach_draft_a: str
    outreach_draft_b: str
    opportunity_type: str
    urgency_reason: str
    themes: list[str] = field(default_factory=list)


async def generate_alert_context(
    post_content: str,
    author_name: str,
    author_headline: str,
    author_company: str,
    degree: int,
    enrichment_summary: str,
    capability_profile: str,
    priority: Priority,
) -> AlertContext:
    """
    Generate match reason, outreach drafts, and theme tags using LLM.
    Routes to GPT-4o mini for HIGH priority, Groq for MEDIUM/LOW.
    """
    prompt = CONTEXT_GENERATION_PROMPT.format(
        capability_profile=capability_profile,
        author_name=author_name,
        author_headline=author_headline,
        author_company=author_company,
        degree=degree,
        enrichment_summary=enrichment_summary or "No enrichment data available.",
        post_content=post_content[:1000],
    )

    if priority == Priority.HIGH:
        raw = await openai_provider.complete(prompt=prompt, model="gpt-4o-mini")
    else:
        raw = await groq_provider.complete(prompt=prompt, model="llama-3.3-70b-versatile")

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:]).rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"[ContextGenerator] LLM returned unparseable JSON: {exc}. "
            f"Raw (first 200 chars): {raw[:200]}"
        ) from exc

    themes = data.pop("themes", []) or []
    if not isinstance(themes, list):
        themes = []

    try:
        return AlertContext(themes=themes, **data)
    except TypeError as exc:
        raise ValueError(
            f"[ContextGenerator] LLM returned unexpected fields: {exc}. "
            f"Data keys: {list(data.keys())}"
        ) from exc
