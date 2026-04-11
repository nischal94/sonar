import pytest
import uuid
from sqlalchemy import select
from app.models.person_signal_summary import PersonSignalSummary
from app.models.workspace import Workspace
from app.models.connection import Connection
from app.models.user import User


@pytest.mark.asyncio
async def test_should_persist_person_signal_summary(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        email="test@example.com",
        hashed_password="hashed",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    conn = Connection(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        linkedin_id="test-person",
        name="Test Person",
        degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    summary = PersonSignalSummary(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        connection_id=conn.id,
        aggregate_score=0.72,
        trend_direction="up",
    )
    db_session.add(summary)
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    loaded = result.scalar_one()
    assert loaded.aggregate_score == 0.72
    assert loaded.trend_direction == "up"
