import pytest
import uuid
import json
from sqlalchemy import text
from app.models.workspace import Workspace
from app.models.signal import Signal
from app.services.ring2_matcher import match_post_embedding_to_ring2_signals


def _make_embedding(seed: float) -> list[float]:
    """Generate a 1536-dim test embedding seeded to a single value."""
    vec = [seed] * 1536
    # normalize-ish so cosine is meaningful
    return vec


@pytest.mark.asyncio
async def test_should_return_empty_when_no_signals(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.commit()

    post_emb = _make_embedding(0.5)
    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, post_emb, cutoff=0.35
    )
    assert result == []


@pytest.mark.asyncio
async def test_should_return_matches_above_cutoff(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS 2", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    # Signal with identical embedding to post -> similarity 1.0 -> distance 0.0
    close_signal = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="close match",
        intent_strength=0.8,
        enabled=True,
    )
    db_session.add(close_signal)
    await db_session.flush()

    # Set embeddings via raw SQL (pgvector)
    emb_vec = _make_embedding(0.5)
    emb_str = "[" + ",".join(str(x) for x in emb_vec) + "]"
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(close_signal.id)},
    )
    await db_session.commit()

    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, emb_vec, cutoff=0.35
    )

    assert len(result) == 1
    assert result[0]["signal_id"] == str(close_signal.id)
    assert result[0]["similarity"] > 0.99


@pytest.mark.asyncio
async def test_should_skip_disabled_signals(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS 3", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    disabled = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="disabled",
        intent_strength=0.8,
        enabled=False,
    )
    db_session.add(disabled)
    await db_session.flush()

    emb_vec = _make_embedding(0.5)
    emb_str = "[" + ",".join(str(x) for x in emb_vec) + "]"
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(disabled.id)},
    )
    await db_session.commit()

    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, emb_vec, cutoff=0.35
    )
    assert result == []
