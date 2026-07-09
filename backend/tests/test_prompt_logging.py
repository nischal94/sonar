"""Regression tests for PROMPT_VERSION structured logging.

Every LLM call site that has a prompt module must emit a log record on the
"app.prompts" logger after a successful call. These tests assert that the log
fires with the expected fields so we catch any future call sites that drop the
instrumentation.

Issue #121.

Implementation note on caplog + Alembic interaction
----------------------------------------------------
test_migration_008_009_010.py calls alembic.command.upgrade/downgrade which
invokes logging.config.fileConfig with disable_existing_loggers=True (the
Python default). This disables any logger that was created before the call but
is not listed in alembic.ini — including "app.prompts". A disabled logger
silently drops all records regardless of level or handlers. To keep these tests
deterministic regardless of execution order we temporarily reset the disabled
flag on the "app.prompts" logger via the _enable_prompts_logger fixture.
"""

from __future__ import annotations

import json
import logging

import pytest

from app.config import OPENAI_MODEL_EXPENSIVE


@pytest.fixture(autouse=True)
def _enable_prompts_logger():
    """Re-enable the app.prompts logger for the duration of each test.

    alembic.command.{upgrade,downgrade} calls logging.config.fileConfig which
    sets disable_existing_loggers=True, disabling any logger not listed in
    alembic.ini. Reset the flag here so tests run in any order.
    """
    logger = logging.getLogger("app.prompts")
    was_disabled = logger.disabled
    logger.disabled = False
    yield
    logger.disabled = was_disabled


# ---------------------------------------------------------------------------
# propose_signals — router-level (FastAPI DI pattern)
# ---------------------------------------------------------------------------


class _FakeLLMForPropose:
    async def complete(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        return json.dumps(
            {
                "signals": [
                    {
                        "phrase": f"phrase {i}",
                        "example_post": f"example post {i}",
                        "intent_strength": 0.5,
                    }
                    for i in range(8)
                ]
            }
        )


@pytest.mark.asyncio
async def test_propose_signals_emits_prompt_version_log(client, db_session, caplog):
    from app.main import app
    from app.services.llm import get_llm_client

    fake = _FakeLLMForPropose()
    app.dependency_overrides[get_llm_client] = lambda: fake

    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "LogTestWS",
            "email": "logtest@example.com",
            "password": "pass123",
        },
    )
    tok = (
        await client.post(
            "/auth/token",
            data={"username": "logtest@example.com", "password": "pass123"},
        )
    ).json()["access_token"]

    with caplog.at_level(logging.INFO):
        resp = await client.post(
            "/workspace/signals/propose",
            json={
                "what_you_sell": "Fractional CTO services",
                "icp": "CEOs at startups",
            },
            headers={"Authorization": f"Bearer {tok}"},
        )

    app.dependency_overrides.pop(get_llm_client, None)

    assert resp.status_code == 200

    log_records = [r for r in caplog.records if r.name == "app.prompts"]
    assert len(log_records) == 1, f"Expected 1 prompt log, got {len(log_records)}"

    record = log_records[0]
    payload = record.__dict__["prompt_log"]
    assert payload["feature"] == "propose_signals"
    assert payload["prompt_version"] == "v1"
    assert payload["model"] == OPENAI_MODEL_EXPENSIVE
    assert "workspace_id" in payload


# ---------------------------------------------------------------------------
# extract_icp_and_seller_mirror — service-level (llm_override DI pattern)
# ---------------------------------------------------------------------------


class _FakeLLMForICP:
    async def complete(
        self,
        prompt: str,
        model: str = None,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        return json.dumps(
            {
                "icp": "Marketing leaders at D2C brands. Not competing vendors.",
                "seller_mirror": "Founders, CEOs at martech SaaS. Series A/B signals.",
            }
        )


@pytest.mark.asyncio
async def test_extract_icp_emits_prompt_version_log(caplog):
    from app.services.profile_extractor import extract_icp_and_seller_mirror

    fake = _FakeLLMForICP()

    with caplog.at_level(logging.INFO):
        icp, seller_mirror = await extract_icp_and_seller_mirror(
            source_text="Acme CDP sells customer-data tooling to D2C brands.",
            llm_override=fake,
        )

    assert icp.startswith("Marketing")
    assert seller_mirror.startswith("Founders")

    log_records = [r for r in caplog.records if r.name == "app.prompts"]
    assert len(log_records) == 1, f"Expected 1 prompt log, got {len(log_records)}"

    record = log_records[0]
    payload = record.__dict__["prompt_log"]
    assert payload["feature"] == "extract_icp_and_seller_mirror"
    assert payload["prompt_version"] == "v1"
    assert payload["model"] == OPENAI_MODEL_EXPENSIVE
