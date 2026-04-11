"""One-shot backfill: convert existing CapabilityProfileVersion.signal_keywords
into rows in the new signals table.

Run once after migration 002 is applied, before any real Phase 2 traffic.

Usage:
    docker compose exec -T api python scripts/backfill_signals_from_keywords.py
"""
import asyncio
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.workspace import CapabilityProfileVersion
from app.models.signal import Signal
from app.services.embedding import embedding_provider


async def run(db):
    """Core backfill logic: read active capability profiles and insert one
    Signal row per keyword. Idempotent — workspaces that already have signals
    are skipped. Takes an async session so tests can drive it directly."""
    result = await db.execute(
        select(CapabilityProfileVersion).where(
            CapabilityProfileVersion.is_active == True
        )
    )
    profiles = result.scalars().all()
    print(f"[backfill] Found {len(profiles)} active capability profiles")

    created = 0
    skipped = 0

    for profile in profiles:
        keywords = profile.signal_keywords or []
        if not keywords:
            skipped += 1
            continue

        # Check if this workspace already has signals — if so, skip
        existing = await db.execute(
            select(Signal).where(Signal.workspace_id == profile.workspace_id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            print(
                f"[backfill] workspace {profile.workspace_id} already has "
                f"signals, skipping"
            )
            skipped += 1
            continue

        for phrase in keywords:
            phrase_stripped = phrase.strip()
            if not phrase_stripped:
                continue

            embedding = await embedding_provider.embed(phrase_stripped)
            emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

            signal_id = uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO signals
                      (id, workspace_id, profile_version_id, phrase,
                       intent_strength, enabled, embedding, created_at, updated_at)
                    VALUES
                      (:id, :ws, :pv, :phrase, :is_, TRUE,
                       CAST(:emb AS vector), now(), now())
                    """
                ),
                {
                    "id": str(signal_id),
                    "ws": str(profile.workspace_id),
                    "pv": str(profile.id),
                    "phrase": phrase_stripped,
                    "is_": 0.7,
                    "emb": emb_str,
                },
            )
            created += 1
            print(
                f"[backfill] created signal for workspace "
                f"{profile.workspace_id}: {phrase_stripped!r}"
            )

    await db.commit()
    print(f"[backfill] done. created={created} skipped_profiles={skipped}")
    return {"created": created, "skipped_profiles": skipped}


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        await run(db)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
