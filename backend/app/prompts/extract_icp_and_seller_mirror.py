"""Extract ICP paragraph + seller-mirror paragraph from a workspace's source text.

Single dual-output prompt per design §3.2 and §8. Outputs are consumed by
profile_extractor to persist icp / seller_mirror text + embeddings on
capability_profile_versions.

PROMPT_VERSION: bump on every content change. Logged alongside every call.
"""

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are a B2B sales intelligence analyst. Given a company's
self-description (from their website, a sales playbook, or a typed summary),
your job is to produce two paragraphs that describe (a) who that company's
buyers are and (b) what OTHER companies that sell the SAME capability look
like on LinkedIn.

Rules for the ICP paragraph:
1. Name the buyer's role, seniority, and company shape (industry, stage, size).
2. Phrase contrastively — explicitly name who the buyer is NOT. Example: "Not
   employees of martech SaaS vendors or competing agencies."
3. Written in plain English. No bullet lists, no headers. One dense paragraph.
4. 50-120 words.

Rules for the seller-mirror paragraph:
1. Describe what other SELLERS of this same capability look like on LinkedIn.
   Who would a competitor's founder, CEO, CPO, or sales director look like?
2. Focus on linguistic tells in LinkedIn headlines — product name-drops,
   stage signals ("Series B", "YC W22"), role words ("CEO", "Founder",
   "Head of Sales at X").
3. This paragraph is SUBTRACTED from the ICP signal during scoring, so
   precision matters: describe the seller-shape as specifically as you can.
4. 50-120 words.

Return strict JSON with exactly two keys: icp and seller_mirror. No other keys,
no prose outside the JSON."""


def build_user_message(source_text: str) -> str:
    """Compose the user turn. This is the only place user input is interpolated.

    Raises ValueError if source_text is empty or whitespace-only.
    """
    if not source_text or not source_text.strip():
        raise ValueError("source_text must be non-empty")
    return (
        "Here is the company's self-description. Produce the ICP and seller-mirror "
        "paragraphs per the rules.\n\n"
        "---\n"
        f"{source_text.strip()}\n"
        "---"
    )


RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "icp": {
            "type": "string",
            "minLength": 80,
            "maxLength": 1200,
        },
        "seller_mirror": {
            "type": "string",
            "minLength": 80,
            "maxLength": 1200,
        },
    },
    "required": ["icp", "seller_mirror"],
    "additionalProperties": False,
}
