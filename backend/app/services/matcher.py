import numpy as np
from app.services.embedding import embedding_provider


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


async def compute_relevance_score(
    post_content: str,
    capability_embedding: list[float],
) -> float:
    """
    Generate post embedding and compute cosine similarity
    against the workspace capability profile embedding.
    Returns a float between 0.0 and 1.0.
    """
    post_embedding = await embedding_provider.embed(post_content)
    return cosine_similarity(post_embedding, capability_embedding)
