import pytest
import uuid
from sqlalchemy import select
from app.models.post import Post
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_post_should_store_ring1_and_ring2_matches(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        linkedin_post_id="lnkd-post-1",
        content="We are struggling to hire senior engineers.",
        post_type="post",
        source="extension",
        ring1_matches=["signal-123"],
        ring2_matches=[{"signal_id": "signal-456", "similarity": 0.82}],
        themes=["engineering hiring", "team scaling"],
        engagement_counts={"likes": 42, "comments": 11, "shares": 3},
    )
    db_session.add(post)
    await db_session.commit()

    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    assert loaded.ring1_matches == ["signal-123"]
    assert loaded.ring2_matches[0]["similarity"] == 0.82
    assert "engineering hiring" in loaded.themes
    assert loaded.engagement_counts["likes"] == 42
