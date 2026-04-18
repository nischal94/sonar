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
    assert resp.json() == {"upserted": 2}

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
async def test_connections_bulk_rejects_unauthenticated(client):
    resp = await client.post(
        "/extension/connections/bulk",
        json={"connections": []},
    )
    assert resp.status_code == 401
