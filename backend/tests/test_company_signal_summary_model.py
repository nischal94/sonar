import pytest
import uuid
from sqlalchemy import select
from app.models.company_signal_summary import CompanySignalSummary
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_company_signal_summary(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    summary = CompanySignalSummary(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        company_name="Acme Corp",
        aggregate_score=0.81,
        active_signal_count=3,
    )
    db_session.add(summary)
    await db_session.commit()

    result = await db_session.execute(
        select(CompanySignalSummary).where(
            CompanySignalSummary.workspace_id == workspace.id
        )
    )
    loaded = result.scalar_one()
    assert loaded.company_name == "Acme Corp"
    assert loaded.active_signal_count == 3
