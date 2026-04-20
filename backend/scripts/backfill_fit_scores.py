"""One-shot script: populate connection.fit_score for a workspace.

Loads the active CapabilityProfileVersion for the workspace (must have
icp_embedding + seller_mirror_embedding). For each connection in the workspace:
  1. Embed headline + company.
  2. Compute fit_score via fit_scorer.
  3. Persist.

Usage inside api container:
  python scripts/backfill_fit_scores.py --workspace-id <uuid>
  python scripts/backfill_fit_scores.py --workspace-id <uuid> --recompute-all

The --recompute-all flag forces re-embed of every connection, overwriting any
existing fit_score. Useful after an ICP change.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Allow direct invocation via `python scripts/backfill_fit_scores.py ...` by
# inserting the backend root on sys.path. Matches the sibling pattern in
# calibrate_matching.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models.connection import Connection  # noqa: E402
from app.models.workspace import CapabilityProfileVersion  # noqa: E402
from app.services.embedding import get_embedding_provider  # noqa: E402
from app.services.fit_scorer import compute_fit_score  # noqa: E402


# Commit every COMMIT_BATCH connections so a mid-loop embedding failure
# doesn't lose all prior progress. At 10k connections a transient 429/503
# otherwise rolls back the entire session.
COMMIT_BATCH = 100

# Rough cost estimate for operator-facing logging. text-embedding-3-small
# is billed per input token; we approximate at ~50 tokens per connection
# (headline + company) × $0.02 / 1M tokens = ~$0.000001 per call. The
# constant may drift with OpenAI pricing; this is a signal, not a budget.
_EMBED_COST_PER_CALL_USD = 0.000001


async def run(
    db, workspace_id: UUID, *, recompute_all: bool = False, lambda_: float = 0.3
) -> dict:
    profile = (
        await db.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if profile is None:
        raise RuntimeError(
            f"No active capability_profile_version for workspace {workspace_id}"
        )
    if profile.icp_embedding is None or profile.seller_mirror_embedding is None:
        raise RuntimeError(
            f"Workspace {workspace_id} active profile has no ICP/seller_mirror embeddings. "
            "Run /profile/extract first."
        )

    emb = get_embedding_provider()

    q = select(Connection).where(Connection.workspace_id == workspace_id)
    if not recompute_all:
        q = q.where(Connection.fit_score.is_(None))
    connections = (await db.execute(q)).scalars().all()

    icp_emb = list(profile.icp_embedding)
    mirror_emb = list(profile.seller_mirror_embedding)

    total = len(connections)
    updated = 0
    skipped_empty = 0
    for i, conn in enumerate(connections, 1):
        text = f"{conn.headline or ''} {conn.company or ''}".strip()
        if not text:
            conn.fit_score = 0.0
            skipped_empty += 1
        else:
            conn_emb = await emb.embed(text)
            conn.fit_score = compute_fit_score(
                icp_embedding=icp_emb,
                seller_mirror_embedding=mirror_emb,
                connection_embedding=conn_emb,
                lambda_=lambda_,
            )
            updated += 1
        if i % COMMIT_BATCH == 0:
            await db.commit()
            print(f"[backfill_fit_scores] progress {i}/{total}")

    await db.commit()
    return {
        "updated": updated,
        "skipped_empty": skipped_empty,
        "total": total,
        "estimated_cost_usd": round(updated * _EMBED_COST_PER_CALL_USD, 6),
    }


async def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--recompute-all", action="store_true")
    parser.add_argument(
        "--lambda",
        type=float,
        default=0.3,
        dest="lambda_",
        help="Subtractive weight on seller_mirror term (default 0.3)",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with Session() as db:
            summary = await run(
                db,
                workspace_id=args.workspace_id,
                recompute_all=args.recompute_all,
                lambda_=args.lambda_,
            )
            print(f"[backfill_fit_scores] done: {summary}")
    except (ValueError, RuntimeError) as e:
        print(f"[backfill_fit_scores] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
