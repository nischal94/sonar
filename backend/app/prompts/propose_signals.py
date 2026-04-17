"""Wizard prompt — turns user's 'what you sell' + 'ICP' into 8–10 embedded buying signals.

See docs/phase-2/design.md §4.1 and docs/phase-2/wizard-decisions.md §3c for rationale.
Rules (sonar/CLAUDE.md 'LLM and agent discipline'):
  - Static system prompt, user input only in the user-message position (no f-strings in system)
  - JSON-schema-validated output via OpenAI Structured Outputs, strict mode
  - PROMPT_VERSION bumped on EVERY content change, logged with every call for v1→v2 comparison
"""

from __future__ import annotations

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "You are a sales intelligence analyst helping the user define buying signals "
    "for their product. A buying signal is a short phrase a prospect might post on "
    "LinkedIn that indicates they are experiencing the problem the user's product "
    "solves, or are actively evaluating solutions like it.\n"
    "\n"
    "Given the user's description of what they sell and their ICP, produce 8–10 "
    "distinct buying signals. For each signal, write:\n"
    "  - phrase: a short human-readable label (3–10 words) in the prospect's voice\n"
    "  - example_post: a realistic LinkedIn post excerpt (1–3 sentences) that this signal would match\n"
    "  - intent_strength: your confidence (0.0–1.0) that a post matching this phrase indicates real buying intent\n"
    "\n"
    "Signals must be distinct from each other (no near-duplicates) and specific to what the user sells. "
    "Avoid generic pain phrases that apply to any business."
)


def build_user_message(what_you_sell: str, icp: str | None) -> str:
    """Compose the user message from the wizard inputs.
    NEVER interpolate user input into SYSTEM_PROMPT. Only here."""
    lines = [f"What I sell: {what_you_sell}"]
    if icp:
        lines.append(f"My ICP: {icp}")
    lines.append("Produce 8–10 buying signals now, matching the schema you were given.")
    return "\n".join(lines)


RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "minItems": 8,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string", "minLength": 3, "maxLength": 120},
                    "example_post": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 500,
                    },
                    "intent_strength": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["phrase", "example_post", "intent_strength"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["signals"],
    "additionalProperties": False,
}
