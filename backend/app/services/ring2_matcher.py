"""Ring 2 matcher — semantic similarity between a post embedding and the
workspace's active signals via pgvector cosine distance.

Returns a list of {signal_id, similarity} dicts for signals whose cosine
similarity to the post embedding exceeds the cutoff. Similarity is
1 - cosine_distance, converted from pgvector's `<=>` operator.
"""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def match_post_embedding_to_ring2_signals(
    db: AsyncSession,
    workspace_id: UUID,
    post_embedding: list[float],
    cutoff: float = 0.35,
) -> list[dict]:
    """Find signals semantically similar to the given post embedding.

    Args:
        db: active async session
        workspace_id: scope the query to a single workspace
        post_embedding: 1536-dim embedding vector of the post
        cutoff: minimum cosine similarity (0-1). Signals below this are omitted.

    Returns:
        List of dicts: [{"signal_id": "uuid-string", "similarity": 0.87}, ...]
        Sorted by similarity descending.
    """
    if not post_embedding:
        return []

    emb_str = "[" + ",".join(str(x) for x in post_embedding) + "]"

    # pgvector cosine distance operator: <=>  (returns 0 = identical, 2 = opposite)
    # similarity = 1 - distance
    sql = text(
        """
        SELECT
          id::text AS signal_id,
          1 - (embedding <=> CAST(:emb AS vector)) AS similarity
        FROM signals
        WHERE workspace_id = :ws
          AND enabled = TRUE
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> CAST(:emb AS vector)) >= :cutoff
        ORDER BY similarity DESC
        """
    )

    result = await db.execute(
        sql, {"emb": emb_str, "ws": str(workspace_id), "cutoff": cutoff}
    )
    rows = result.mappings().all()

    return [{"signal_id": r["signal_id"], "similarity": float(r["similarity"])} for r in rows]
