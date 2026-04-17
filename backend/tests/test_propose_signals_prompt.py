from app.prompts.propose_signals import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_message,
    RESPONSE_JSON_SCHEMA,
)


def test_prompt_version_is_v1():
    """Locks the initial version. Bump when prompt content changes."""
    assert PROMPT_VERSION == "v1"


def test_system_prompt_is_static_and_does_not_interpolate_user_input():
    """Per sonar/CLAUDE.md 'Prompt injection defense is mandatory':
    user-controlled input goes in the user message position only. If the
    system prompt is an f-string with {...} placeholders, that's a bug."""
    assert "{" not in SYSTEM_PROMPT or "{{" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT looks like it contains interpolation placeholders — "
        "user input belongs in build_user_message, not in the system prompt."
    )


def test_build_user_message_includes_what_you_sell():
    msg = build_user_message(what_you_sell="Fractional CTO services", icp=None)
    assert "Fractional CTO services" in msg


def test_build_user_message_includes_icp_when_provided():
    msg = build_user_message(
        what_you_sell="Fractional CTO services",
        icp="CEOs at 20-50 person startups",
    )
    assert "CEOs at 20-50 person startups" in msg


def test_build_user_message_handles_null_icp_gracefully():
    msg = build_user_message(what_you_sell="X", icp=None)
    assert isinstance(msg, str) and len(msg) > 0


def test_response_schema_enforces_signal_shape():
    """Schema must require phrase, example_post, intent_strength per signal;
    signals array must have 8–10 items to meet design.md §4.1 Step 3."""
    schema = RESPONSE_JSON_SCHEMA
    assert schema["type"] == "object"
    signals = schema["properties"]["signals"]
    assert signals["type"] == "array"
    assert signals["minItems"] == 8
    assert signals["maxItems"] == 10
    item_props = signals["items"]["properties"]
    assert "phrase" in item_props
    assert "example_post" in item_props
    assert "intent_strength" in item_props
    assert item_props["intent_strength"]["minimum"] == 0
    assert item_props["intent_strength"]["maximum"] == 1
    # strict mode requirements
    assert signals["items"]["additionalProperties"] is False
    assert set(signals["items"]["required"]) == {
        "phrase",
        "example_post",
        "intent_strength",
    }
