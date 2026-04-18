import pytest
from datetime import datetime, timezone
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.person_signal_summary import PersonSignalSummary
from app.models.signal import Signal
from app.models.post import Post


async def _seed_person(db_session, *, workspace_name, email, score, degree=1):
    workspace = Workspace(name=workspace_name)
    db_session.add(workspace)
    await db_session.flush()
    user = User(
        workspace_id=workspace.id,
        email=email,
        hashed_password="x",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    conn = Connection(
        workspace_id=workspace.id,
        user_id=user.id,
        linkedin_id=f"li-{email}",
        name=f"Person {email}",
        headline="VP Engineering",
        company="Acme",
        degree=degree,
    )
    db_session.add(conn)
    await db_session.flush()
    signal = Signal(
        workspace_id=workspace.id,
        phrase="struggling to hire",
        example_post="example body text",
        intent_strength=0.7,
        embedding=[0.0] * 1536,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    post = Post(
        workspace_id=workspace.id,
        connection_id=conn.id,
        linkedin_post_id=f"p-{email}",
        content="We've been interviewing for 4 months.",
        post_type="text",
        source="feed",
        combined_score=score,
        matched=True,
    )
    db_session.add(post)
    await db_session.flush()
    summary = PersonSignalSummary(
        workspace_id=workspace.id,
        connection_id=conn.id,
        aggregate_score=score,
        trend_direction="up",
        last_signal_at=datetime.now(timezone.utc),
        recent_post_id=post.id,
        recent_signal_id=signal.id,
    )
    db_session.add(summary)
    await db_session.commit()
    return workspace, conn, user


def _make_token(user_id, workspace_id):
    """Helper: forge a JWT for the seeded user so the test doesn't need
    to re-register (which would create a different workspace)."""
    from app.routers.auth import create_access_token

    return create_access_token(user_id=user_id, workspace_id=workspace_id)


@pytest.mark.asyncio
async def test_dashboard_people_returns_ranked_list(client, db_session):
    workspace, conn, user = await _seed_person(
        db_session,
        workspace_name="Test Agency",
        email="dash@a.com",
        score=0.85,
        degree=1,
    )
    hdrs = {"Authorization": f"Bearer {_make_token(user.id, workspace.id)}"}

    resp = await client.get("/workspace/dashboard/people", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["people"]) == 1
    row = body["people"][0]
    assert row["name"].startswith("Person ")
    assert row["aggregate_score"] == pytest.approx(0.85)
    assert row["relationship_degree"] == 1
    assert row["matching_signal_phrase"] == "struggling to hire"


@pytest.mark.asyncio
async def test_dashboard_people_filters_by_threshold(client, db_session):
    workspace, conn, user = await _seed_person(
        db_session,
        workspace_name="Threshold Test",
        email="thr@a.com",
        score=0.5,
        degree=1,
    )
    hdrs = {"Authorization": f"Bearer {_make_token(user.id, workspace.id)}"}

    # Threshold 0.65 excludes the 0.5 score
    resp = await client.get("/workspace/dashboard/people?threshold=0.65", headers=hdrs)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # Threshold 0.4 includes it
    resp = await client.get("/workspace/dashboard/people?threshold=0.4", headers=hdrs)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_dashboard_people_filters_by_relationship(client, db_session):
    workspace, conn, user = await _seed_person(
        db_session,
        workspace_name="Rel Test",
        email="rel@a.com",
        score=0.9,
        degree=2,
    )
    hdrs = {"Authorization": f"Bearer {_make_token(user.id, workspace.id)}"}

    # Only 1st degree — excludes the 2nd-degree seed
    resp = await client.get("/workspace/dashboard/people?relationship=1", headers=hdrs)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # 2nd degree only — includes it
    resp = await client.get("/workspace/dashboard/people?relationship=2", headers=hdrs)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_dashboard_people_workspace_isolation(client, db_session):
    # Seed workspace A with a person
    workspace_a, conn_a, user_a = await _seed_person(
        db_session,
        workspace_name="A",
        email="a@a.com",
        score=0.9,
    )
    # Seed workspace B with a different person
    workspace_b, conn_b, user_b = await _seed_person(
        db_session,
        workspace_name="B",
        email="b@b.com",
        score=0.9,
    )

    hdrs_a = {"Authorization": f"Bearer {_make_token(user_a.id, workspace_a.id)}"}

    resp = await client.get("/workspace/dashboard/people", headers=hdrs_a)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    # The one person we see MUST be from workspace A
    assert body["people"][0]["connection_id"] == str(conn_a.id)


@pytest.mark.asyncio
async def test_dashboard_people_rejects_unauthenticated(client):
    resp = await client.get("/workspace/dashboard/people")
    assert resp.status_code == 401
