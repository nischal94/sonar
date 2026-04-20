"""Prompt module: structure + schema validation.

This file does NOT test LLM output quality (that's for calibration), only that
the prompt module is well-formed: version set, system prompt static, user
message builder interpolates the right inputs, schema validates realistic JSON.
"""

import pytest
from jsonschema import validate, ValidationError

from app.prompts import extract_icp_and_seller_mirror as mod


def test_prompt_version_is_semver_like():
    assert isinstance(mod.PROMPT_VERSION, str)
    assert mod.PROMPT_VERSION.startswith("v")


def test_system_prompt_is_static_and_nonempty():
    assert isinstance(mod.SYSTEM_PROMPT, str)
    assert len(mod.SYSTEM_PROMPT) > 100
    # Must not contain user-controlled placeholders
    assert "{" not in mod.SYSTEM_PROMPT
    assert "}" not in mod.SYSTEM_PROMPT


def test_build_user_message_interpolates_source_text():
    source = "We sell CDP tooling for D2C brands."
    msg = mod.build_user_message(source_text=source)
    assert source in msg


def test_build_user_message_rejects_empty():
    with pytest.raises(ValueError):
        mod.build_user_message(source_text="")


def test_response_schema_validates_well_formed_output():
    sample = {
        "icp": "Marketing, growth, or e-commerce leaders at D2C or direct-to-consumer brands generating >$1M ARR. Not employees of martech SaaS vendors or competing agencies.",
        "seller_mirror": "Founders, CEOs, CPOs, and sales directors at CDP / marketing-automation / customer-engagement SaaS companies. People whose LinkedIn headlines name-drop their own product.",
    }
    validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)


def test_response_schema_rejects_missing_field():
    sample = {"icp": "..."}  # missing seller_mirror
    with pytest.raises(ValidationError):
        validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)


def test_response_schema_rejects_short_fields():
    sample = {"icp": "short", "seller_mirror": "also short"}
    with pytest.raises(ValidationError):
        validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)
