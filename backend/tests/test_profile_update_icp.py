"""Integration tests: POST /profile/update-icp updates ICP text and re-embeds."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.workspace import CapabilityProfileVersion


class _FakeEmbedding:
    """Deterministic fake embedding keyed by first char for distinguishability."""

    async def embed(self, text: str) -> list[float]:
        seed = ord(text[0]) if text else 0
        return [float((seed + i) % 10) / 10.0 for i in range(1536)]


async def _seed_active_version(db_session, workspace_id):
    """Insert an active CapabilityProfileVersion for the given workspace."""
    from sqlalchemy import text as sql_text

    profile = CapabilityProfileVersion(
        workspace_id=workspace_id,
        version=1,
        raw_text="Acme CDP: customer data platform for D2C brands.",
        source="text",
        signal_keywords=["cdp"],
        anti_keywords=[],
        icp="Original ICP text. Marketing leaders at D2C brands.",
        seller_mirror="Original seller mirror. Founders at martech SaaS.",
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    # Populate pgvector columns with a distinct initial embedding (all 0.1)
    fake_emb = "[" + ",".join(["0.1"] * 1536) + "]"
    await db_session.execute(
        sql_text(
            "UPDATE capability_profile_versions "
            "SET embedding = CAST(:e AS vector), "
            "    icp_embedding = CAST(:e AS vector), "
            "    seller_mirror_embedding = CAST(:e AS vector) "
            "WHERE id = :id"
        ),
        {"e": fake_emb, "id": str(profile.id)},
    )
    await db_session.commit()
    return profile.id


@pytest.mark.asyncio
async def test_update_icp_updates_both_text_fields_and_reembeds(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    from app.main import app
    from app.services.embedding import get_embedding_provider

    await _seed_active_version(db_session, workspace_id)

    fake_emb = _FakeEmbedding()
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb

    try:
        resp = await client.post(
            "/profile/update-icp",
            json={
                "icp": "Updated ICP: CMOs at Series A SaaS startups.",
                "seller_mirror": "Updated mirror: VCs and agency growth leads.",
            },
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    # Expire and re-fetch to bypass session cache
    await db_session.rollback()
    row = (
        await db_session.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active.is_(True))
        )
    ).scalar_one()

    assert row.icp == "Updated ICP: CMOs at Series A SaaS startups."
    assert row.seller_mirror == "Updated mirror: VCs and agency growth leads."

    # _FakeEmbedding seeds on first char; "U" = 85, "Updated ICP..." → different from 0.1
    icp_emb = list(row.icp_embedding)
    mirror_emb = list(row.seller_mirror_embedding)
    assert len(icp_emb) == 1536
    assert len(mirror_emb) == 1536
    # Initial embeddings were all 0.1; fake embeds keyed to 'U' (85) should differ
    assert not all(v == pytest.approx(0.1) for v in icp_emb)
    assert not all(v == pytest.approx(0.1) for v in mirror_emb)


@pytest.mark.asyncio
async def test_update_icp_requires_at_least_one_field(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    await _seed_active_version(db_session, workspace_id)

    resp = await client.post(
        "/profile/update-icp",
        json={},
        headers=auth_headers,
    )

    assert resp.status_code == 400
    assert (
        "icp" in resp.json()["detail"].lower()
        or "seller_mirror" in resp.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_update_icp_rejects_whitespace_only(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    """Whitespace-only strings must be treated as missing, not embedded.
    Without the strip + non-empty check, the endpoint would happily embed
    "   \\n\\t " and corrupt the active profile's ICP signal."""
    await _seed_active_version(db_session, workspace_id)

    resp = await client.post(
        "/profile/update-icp",
        json={"icp": "   ", "seller_mirror": "\n\t "},
        headers=auth_headers,
    )

    assert resp.status_code == 400
    assert "non-empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_icp_accepts_icp_only(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    from app.main import app
    from app.services.embedding import get_embedding_provider

    await _seed_active_version(db_session, workspace_id)

    fake_emb = _FakeEmbedding()
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb

    try:
        resp = await client.post(
            "/profile/update-icp",
            json={"icp": "ICP-only update: Head of Growth at Fintech startups."},
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)

    assert resp.status_code == 200, resp.text

    await db_session.rollback()
    row = (
        await db_session.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active.is_(True))
        )
    ).scalar_one()

    # ICP text and embedding should be updated
    assert row.icp == "ICP-only update: Head of Growth at Fintech startups."
    icp_emb = list(row.icp_embedding)
    assert len(icp_emb) == 1536
    assert not all(v == pytest.approx(0.1) for v in icp_emb)

    # seller_mirror text should remain unchanged
    assert row.seller_mirror == "Original seller mirror. Founders at martech SaaS."
    # seller_mirror_embedding should remain the initial 0.1 values
    mirror_emb = list(row.seller_mirror_embedding)
    assert all(v == pytest.approx(0.1) for v in mirror_emb)
