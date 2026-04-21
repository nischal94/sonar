"""Integration test: POST /profile/extract persists ICP + seller_mirror."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.workspace import CapabilityProfileVersion
from app.prompts import extract_icp_and_seller_mirror as icp_prompt


class _FakeLLMForICP:
    """Returns capability JSON first, then ICP+mirror JSON."""

    def __init__(self):
        self.calls = []

    async def complete(self, prompt, model=None, *, system=None, max_tokens=2048):
        self.calls.append(("complete", system, prompt[:60]))
        # Route by reference equality on the known prompt constant so that
        # any future rewording of SYSTEM_PROMPT doesn't silently misroute
        # this fake and surface as a confusing parse error.
        if system is icp_prompt.SYSTEM_PROMPT:
            # ICP prompt
            return json.dumps(
                {
                    "icp": "Marketing and growth leaders at D2C brands. Not competing martech vendors or agency employees. Must own a budget for outbound tooling.",
                    "seller_mirror": "Founders, CEOs, CPOs at CDP or marketing-automation SaaS companies. LinkedIn headlines typically name-drop the product and include Series A/B signals.",
                }
            )
        # Capability prompt (existing path)
        return json.dumps(
            {
                "company_name": "Acme CDP",
                "company_description": "A customer data platform for D2C brands.",
                "primary_services": ["CDP"],
                "target_customers": ["D2C brands"],
                "pain_points_solved": ["data fragmentation"],
                "technologies_used": ["Python"],
                "signal_keywords": ["customer data", "cdp migration"],
                "anti_keywords": ["looking for job"],
                "capability_summary": "We sell a CDP for D2C brands.",
            }
        )


class _FakeEmbedding:
    async def embed(self, text: str) -> list[float]:
        # Deterministic fake embedding keyed by first char, so we can distinguish
        # ICP / seller_mirror / capability in assertions
        seed = ord(text[0]) if text else 0
        return [float((seed + i) % 10) / 10.0 for i in range(1536)]


@pytest.mark.asyncio
async def test_profile_extract_persists_icp_and_seller_mirror(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    from app.main import app
    from app.services.embedding import get_embedding_provider
    from app.services.llm import get_llm_client

    fake_llm = _FakeLLMForICP()
    fake_emb = _FakeEmbedding()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb

    try:
        resp = await client.post(
            "/profile/extract",
            json={"text": "Acme CDP sells customer-data tooling to D2C brands."},
            headers=auth_headers,
        )
    finally:
        # Exhaustive cleanup — don't rely on the outer `client` fixture's
        # dependency_overrides.clear() to sweep get_current_user, since that
        # couples teardown safety to fixture ordering.
        from app.routers.auth import get_current_user

        app.dependency_overrides.pop(get_llm_client, None)
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["icp"].startswith("Marketing")
    assert body["seller_mirror"].startswith("Founders")

    row = (
        await db_session.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active.is_(True))
        )
    ).scalar_one()

    assert row.icp is not None and "D2C" in row.icp
    assert row.seller_mirror is not None and "CDP" in row.seller_mirror
    assert row.icp_embedding is not None
    assert len(list(row.icp_embedding)) == 1536
    assert row.seller_mirror_embedding is not None
    assert len(list(row.seller_mirror_embedding)) == 1536
