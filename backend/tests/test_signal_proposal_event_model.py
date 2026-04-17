import pytest
from sqlalchemy import select
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_signal_proposal_event_persists_all_fields(db_session):
    workspace = Workspace(name="Test Agency")
    db_session.add(workspace)
    await db_session.flush()

    event = SignalProposalEvent(
        workspace_id=workspace.id,
        prompt_version="v1",
        what_you_sell="Fractional CTO services for Series A-B SaaS",
        icp="CEOs and VPs Eng at 20-50 person startups",
        proposed=[
            {
                "phrase": "struggling to hire senior engineers",
                "example_post": "We've been interviewing for 4 months.",
                "intent_strength": 0.82,
            },
        ],
        accepted_ids=["0"],
        edited_pairs=[],
        rejected_ids=[],
        user_added=[],
    )
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(
        select(SignalProposalEvent).where(SignalProposalEvent.id == event.id)
    )
    loaded = result.scalar_one()
    assert loaded.prompt_version == "v1"
    assert loaded.what_you_sell.startswith("Fractional CTO")
    assert loaded.icp is not None
    assert loaded.proposed[0]["phrase"] == "struggling to hire senior engineers"
    assert loaded.accepted_ids == ["0"]
    assert loaded.completed_at is None  # not yet completed
    assert loaded.created_at is not None


@pytest.mark.asyncio
async def test_signal_proposal_event_allows_null_icp_and_empty_arrays(db_session):
    """ICP is optional (design.md §4.1 Step 2). Arrays default to empty."""
    workspace = Workspace(name="Test Agency 2")
    db_session.add(workspace)
    await db_session.flush()

    event = SignalProposalEvent(
        workspace_id=workspace.id,
        prompt_version="v1",
        what_you_sell="Something",
        icp=None,
        proposed=[],
    )
    db_session.add(event)
    await db_session.commit()
    assert event.icp is None
    assert event.accepted_ids == []
    assert event.rejected_ids == []
    assert event.user_added == []
