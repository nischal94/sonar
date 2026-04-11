import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from app.services.matcher import compute_relevance_score


@pytest.mark.asyncio
async def test_high_relevance_for_matching_content():
    with patch("app.services.matcher.embedding_provider") as mock_emb:
        mock_emb.embed = AsyncMock(return_value=[0.9] * 1536)

        score = await compute_relevance_score(
            post_content="We need help integrating AI agents into our sales workflow.",
            capability_embedding=[0.9] * 1536,
        )

    # Same vector → cosine similarity = 1.0
    assert score > 0.95


@pytest.mark.asyncio
async def test_low_relevance_for_unrelated_content():
    # Orthogonal vector → near-zero cosine similarity
    capability = [1.0] + [0.0] * 1535
    post_embedding = [0.0, 1.0] + [0.0] * 1534  # orthogonal to capability

    with patch("app.services.matcher.embedding_provider") as mock_emb:
        mock_emb.embed = AsyncMock(return_value=post_embedding)

        score = await compute_relevance_score(
            post_content="Just got back from an amazing hiking trip!",
            capability_embedding=capability,
        )

    assert score < 0.1


@pytest.mark.asyncio
async def test_cosine_similarity_orthogonal_vectors():
    from app.services.matcher import cosine_similarity
    # Orthogonal vectors → 0 similarity
    a = [1.0] + [0.0] * 1535
    b = [0.0, 1.0] + [0.0] * 1534
    assert cosine_similarity(a, b) == 0.0


@pytest.mark.asyncio
async def test_cosine_similarity_identical_vectors():
    from app.services.matcher import cosine_similarity
    v = [0.5] * 1536
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6
