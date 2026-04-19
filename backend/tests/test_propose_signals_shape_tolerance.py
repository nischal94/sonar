"""CI-safe unit tests for propose_signals LLM-output shape tolerance.

Complements tests/test_propose_signals_shape.py, which hits the real OpenAI
API and is skipped on forks without the secret. This file injects a FakeLLM
via FastAPI dependency_overrides so the list/dict/scalar branches in
app.routers.signals.propose_signals run in every CI build.

See the Wizard-dogfood PR (fix/wizard-llm-shape-and-params) for the bug that
motivated the shape tolerance: gpt-5.4-mini occasionally returns a top-level
list `[{...}]` instead of the documented `{"signals": [...]}` dict.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any

import pytest
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider


# 9 signals fits the 8-10 schema bound in ProposeSignalsResponse.
_NINE_SIGNALS = [
    {
        "phrase": f"signal {i}",
        "example_post": f"example post body {i} with enough length to satisfy validation",
        "intent_strength": 0.5 + i * 0.01,
    }
    for i in range(9)
]


@dataclass
class _ScriptedLLM:
    """Returns a caller-supplied string verbatim from complete().

    Naming: NOT FakeLLM — the other Wizard tests already bind `FakeLLM` to a
    dict-shape fixture and this file is about the DIFFERENT shapes. Distinct
    name keeps future grep-based test discovery unambiguous.
    """

    payload: Any

    async def complete(self, prompt: str, model: str, **kwargs) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


class _FakeEmbed:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


async def _auth_headers(client) -> dict:
    """Register a throwaway workspace and return an Authorization header."""
    email = "shape-tolerance@test.com"
    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "Shape Tolerance Test",
            "email": email,
            "password": "pass123",
        },
    )
    tok = (
        await client.post(
            "/auth/token", data={"username": email, "password": "pass123"}
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_propose_accepts_dict_with_signals_key(client, db_session):
    """Documented shape: {"signals": [...]}. Canonical happy path."""
    app.dependency_overrides[get_llm_client] = lambda: _ScriptedLLM(
        {"signals": _NINE_SIGNALS}
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FakeEmbed()
    try:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "fractional CTO", "icp": "Series A founders"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["signals"]) == 9
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propose_accepts_top_level_list(client, db_session):
    """Bug #2 from dogfood: gpt-5.4-mini emits `[{...}]` instead of
    `{"signals": [...]}`. The router must tolerate both identically."""
    app.dependency_overrides[get_llm_client] = lambda: _ScriptedLLM(_NINE_SIGNALS)
    app.dependency_overrides[get_embedding_provider] = lambda: _FakeEmbed()
    try:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "fractional CTO", "icp": "Series A founders"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["signals"]) == 9
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_propose_rejects_scalar_payload(client, db_session):
    """Bare scalars (bool, int, string after json.loads) must 502 cleanly,
    not TypeError. Covers the `else: raise ValueError` branch."""
    app.dependency_overrides[get_llm_client] = lambda: _ScriptedLLM(42)
    app.dependency_overrides[get_embedding_provider] = lambda: _FakeEmbed()
    try:
        headers = await _auth_headers(client)
        resp = await client.post(
            "/workspace/signals/propose",
            json={"what_you_sell": "fractional CTO", "icp": "Series A founders"},
            headers=headers,
        )
        assert resp.status_code == 502
        assert "unexpected LLM output type" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()
