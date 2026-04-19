"""Structural CI gate for the propose_signals prompt.

Hits the REAL OpenAI API. Runs the prompt against 3 fixed inputs and
asserts output SHAPE, not semantic quality:
  - Valid JSON
  - signals array has length 8-10
  - Each signal has phrase (non-empty), example_post (non-empty), intent_strength in [0,1]
  - No duplicate phrases

Gated by OPENAI_API_KEY being a real key, not the placeholder. Skipped otherwise
so CI on a fork (no secret) doesn't fail.
"""

import json
import pytest
from app.config import OPENAI_MODEL_EXPENSIVE, get_settings
from app.prompts.propose_signals import SYSTEM_PROMPT, build_user_message
from app.services.llm import OpenAILLMProvider

SANITY_INPUTS = [
    {
        "what_you_sell": "Fractional CTO services for Series A-B SaaS startups",
        "icp": "CEOs and VPs Eng at 20-50 person startups",
    },
    {
        "what_you_sell": "AI copywriting tool for e-commerce product descriptions",
        "icp": "DTC brand founders running on Shopify",
    },
    {
        "what_you_sell": "B2B data enrichment API for sales teams",
        "icp": None,
    },
]


def _has_real_openai_key() -> bool:
    key = get_settings().openai_api_key
    return bool(key) and not key.startswith("placeholder-") and key.startswith("sk-")


@pytest.mark.asyncio
@pytest.mark.skipif(not _has_real_openai_key(), reason="real OPENAI_API_KEY required")
@pytest.mark.parametrize("inputs", SANITY_INPUTS)
async def test_propose_signals_prompt_produces_valid_shape(inputs):
    """Does NOT assert quality — asserts shape. Quality is measured via
    production acceptance rate, not here. See docs/phase-2/wizard-decisions.md §3b."""
    provider = OpenAILLMProvider()
    user_msg = build_user_message(inputs["what_you_sell"], inputs["icp"])
    # Mirror the production call site (app/routers/signals.py::propose_signals):
    # pass SYSTEM_PROMPT via the system kwarg, NOT concatenated into the user
    # message. Inlining violates the prompt-injection discipline in CLAUDE.md —
    # user input must only appear in the user-role message. max_tokens matches
    # the router so truncation behavior is identical.
    raw = await provider.complete(
        user_msg,
        model=OPENAI_MODEL_EXPENSIVE,
        system=SYSTEM_PROMPT,
        max_tokens=4096,
    )

    # Strip markdown fence if present
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
    payload = json.loads(s.strip())

    # Mirror the router's shape tolerance EXACTLY: three-way branch that
    # accepts a top-level list `[{...}]`, the documented `{"signals": [...]}`
    # dict form, OR fails loudly on a scalar/None. gpt-5.4-mini emits both
    # valid shapes depending on the call. Keeping this in lockstep with
    # app/routers/signals.py::propose_signals means a future scalar-output
    # regression fails with a clear message here, same as in production.
    # Long-term fix is Structured Outputs via response_format=json_schema;
    # tracked in followup.
    if isinstance(payload, list):
        signals = payload
    elif isinstance(payload, dict):
        signals = payload["signals"]
    else:
        raise AssertionError(f"unexpected LLM output type: {type(payload).__name__}")
    assert 8 <= len(signals) <= 10, f"expected 8-10 signals, got {len(signals)}"

    phrases_seen = set()
    for i, sig in enumerate(signals):
        assert (
            "phrase" in sig
            and isinstance(sig["phrase"], str)
            and len(sig["phrase"]) > 0
        )
        assert (
            "example_post" in sig
            and isinstance(sig["example_post"], str)
            and len(sig["example_post"]) > 0
        )
        assert "intent_strength" in sig
        strength = sig["intent_strength"]
        assert isinstance(strength, (int, float)) and 0 <= strength <= 1
        normalized = sig["phrase"].strip().lower()
        assert (
            normalized not in phrases_seen
        ), f"duplicate phrase at index {i}: {sig['phrase']}"
        phrases_seen.add(normalized)
