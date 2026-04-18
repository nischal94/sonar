from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from app.models.user import User
from app.models.connection import Connection
from app.models.workspace import Workspace
from app.routers.auth import create_access_token


def _tok(user_id, workspace_id):
    return create_access_token(user_id=user_id, workspace_id=workspace_id)


async def _seed_workspace(db_session, email: str):
    ws = Workspace(name=f"WS {email}")
    db_session.add(ws)
    await db_session.flush()
    user = User(workspace_id=ws.id, email=email, hashed_password="x", role="owner")
    db_session.add(user)
    await db_session.commit()
    return ws, user


@pytest.mark.asyncio
async def test_connections_bulk_upserts_rows(client, db_session):
    ws, user = await _seed_workspace(db_session, "a@a.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post(
        "/extension/connections/bulk",
        json={
            "connections": [
                {
                    "linkedin_id": "li-1",
                    "name": "Alice",
                    "headline": "VP Eng",
                    "company": "Acme",
                    "profile_url": "https://linkedin.com/in/alice",
                },
                {
                    "linkedin_id": "li-2",
                    "name": "Bob",
                    "headline": None,
                    "company": None,
                    "profile_url": "https://linkedin.com/in/bob",
                },
            ]
        },
        headers=hdrs,
    )
    assert resp.status_code == 200
    assert resp.json() == {"upserted": 2, "received": 2, "deduped": 0}

    rows = (
        (
            await db_session.execute(
                select(Connection).where(Connection.workspace_id == ws.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_connections_bulk_dedupes_on_linkedin_id(client, db_session):
    ws, user = await _seed_workspace(db_session, "b@b.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    await client.post(
        "/extension/connections/bulk",
        json={
            "connections": [
                {
                    "linkedin_id": "li-dup",
                    "name": "Old",
                    "headline": None,
                    "company": None,
                    "profile_url": "https://linkedin.com/in/dup",
                }
            ]
        },
        headers=hdrs,
    )
    # Send again with the same linkedin_id but updated name
    await client.post(
        "/extension/connections/bulk",
        json={
            "connections": [
                {
                    "linkedin_id": "li-dup",
                    "name": "New",
                    "headline": "Updated",
                    "company": "NewCo",
                    "profile_url": "https://linkedin.com/in/dup",
                }
            ]
        },
        headers=hdrs,
    )

    rows = (
        (
            await db_session.execute(
                select(Connection).where(Connection.workspace_id == ws.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].name == "New"
    assert rows[0].company == "NewCo"


@pytest.mark.asyncio
async def test_connections_bulk_dedupes_within_single_request(client, db_session):
    # LinkedIn's virtualized connections list re-emits rows when the extension
    # re-scrolls past an already-captured row. The endpoint must collapse
    # same-request dups on linkedin_id (last-wins), not IntegrityError.
    ws, user = await _seed_workspace(db_session, "bd@b.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post(
        "/extension/connections/bulk",
        json={
            "connections": [
                {
                    "linkedin_id": "li-same",
                    "name": "First Pass",
                    "headline": None,
                    "company": "OldCo",
                    "profile_url": "https://linkedin.com/in/same",
                },
                {
                    "linkedin_id": "li-same",
                    "name": "Second Pass",
                    "headline": "Updated",
                    "company": "NewCo",
                    "profile_url": "https://linkedin.com/in/same",
                },
                {
                    "linkedin_id": "li-other",
                    "name": "Other",
                    "headline": None,
                    "company": None,
                    "profile_url": "https://linkedin.com/in/other",
                },
            ]
        },
        headers=hdrs,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"upserted": 2, "received": 3, "deduped": 1}

    rows = (
        (
            await db_session.execute(
                select(Connection).where(Connection.workspace_id == ws.id)
            )
        )
        .scalars()
        .all()
    )
    by_lid = {r.linkedin_id: r for r in rows}
    assert len(by_lid) == 2
    # Last occurrence wins for the duplicated linkedin_id
    assert by_lid["li-same"].name == "Second Pass"
    assert by_lid["li-same"].company == "NewCo"


@pytest.mark.asyncio
async def test_connections_bulk_rejects_unauthenticated(client):
    resp = await client.post(
        "/extension/connections/bulk",
        json={"connections": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trigger_sets_started_at_on_first_call(client, db_session):
    ws, user = await _seed_workspace(db_session, "trig1@t.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post("/workspace/backfill/trigger", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert "task_id" in body
    assert "backfill_started_at" in body

    reloaded = (
        await db_session.execute(select(Workspace).where(Workspace.id == ws.id))
    ).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None


@pytest.mark.asyncio
async def test_trigger_returns_409_on_second_call(client, db_session):
    ws, user = await _seed_workspace(db_session, "trig2@t.com")
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post("/workspace/backfill/trigger", headers=hdrs)
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_reports_idle_before_trigger(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat1@s.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    resp = await client.get("/workspace/backfill/status", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "idle"
    assert body["profile_count"] == 0


@pytest.mark.asyncio
async def test_status_reports_running_after_start(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat2@s.com")
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    resp = await client.get("/workspace/backfill/status", headers=hdrs)
    assert resp.json()["state"] == "running"


@pytest.mark.asyncio
async def test_status_reports_done_after_completion(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat3@s.com")
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    ws.backfill_completed_at = now
    ws.backfill_profile_count = 127
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    body = (await client.get("/workspace/backfill/status", headers=hdrs)).json()
    assert body["state"] == "done"
    assert body["profile_count"] == 127


@pytest.mark.asyncio
async def test_status_reports_failed_when_failed_at_set(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat4@s.com")
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    ws.backfill_failed_at = now
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    body = (await client.get("/workspace/backfill/status", headers=hdrs)).json()
    assert body["state"] == "failed"
