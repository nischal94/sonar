import pytest
import uuid
from sqlalchemy import select
from app.models.signal import Signal
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_signal_row(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test Workspace", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    signal = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="struggling to hire senior engineers",
        example_post="Been interviewing for 3 months and still can't find the right person.",
        intent_strength=0.85,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.commit()

    result = await db_session.execute(
        select(Signal).where(Signal.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.phrase == "struggling to hire senior engineers"
    assert loaded.intent_strength == 0.85
    assert loaded.enabled is True
