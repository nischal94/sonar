import asyncio
import logging
from uuid import UUID
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.pipeline.process_post_pipeline", bind=True, max_retries=3)
def process_post_pipeline(self, post_id: str, workspace_id: str):
    """
    Main processing pipeline for a single ingested post.
    Phase 2: no keyword-filter gate. All posts flow through embed →
    Ring 1 (keyword) → Ring 2 (semantic) → scoring → context → alert.
    """
    asyncio.run(_run_pipeline(UUID(post_id), UUID(workspace_id)))


async def _run_pipeline(post_id: UUID, workspace_id: UUID):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, update, text
    from datetime import datetime, timezone
    import json
    from app.config import get_settings
    from app.models.post import Post
    from app.models.connection import Connection
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.signal import Signal
    from app.models.alert import Alert
    from app.models.feedback import SignalEffectiveness
    from app.services.embedding import embedding_provider
    from app.services.matcher import cosine_similarity
    from app.services.ring1_matcher import match_post_to_ring1_signals
    from app.services.ring2_matcher import match_post_embedding_to_ring2_signals
    from app.services.scorer import compute_combined_score
    from app.services.context_generator import generate_alert_context
    from app.services.keyword_filter import DEFAULT_BLOCKLIST
    from app.delivery.router import DeliveryRouter

    engine = create_async_engine(get_settings().database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        post = await db.get(Post, post_id)
        if not post or post.processed_at:
            await engine.dispose()
            return

        result = await db.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active == True)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            await engine.dispose()
            return

        # Hard spam blocklist stays as a pre-check — only posts about birthdays,
        # new jobs, etc. are dropped. This is NOT the keyword filter.
        #
        # Workspace-configured anti_keywords are still honored here so the
        # Phase 1 behavior is preserved — Ring 2 semantic matching should not
        # rescue posts the workspace explicitly told us to ignore.
        content_lower = post.content.lower()
        full_blocklist = DEFAULT_BLOCKLIST + [
            kw.lower() for kw in (profile.anti_keywords or [])
        ]
        if any(term in content_lower for term in full_blocklist):
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        # Stage 1: Embed the post (always)
        post_embedding = await embedding_provider.embed(post.content)

        # Stage 2: Load active signals
        signal_rows = (await db.execute(
            select(Signal).where(
                Signal.workspace_id == workspace_id,
                Signal.enabled == True,
            )
        )).scalars().all()

        # Stage 3: Ring 1 — keyword matches
        ring1_matches = match_post_to_ring1_signals(post.content, signal_rows)

        # Stage 4: Ring 2 — pgvector semantic matches
        ring2_matches = await match_post_embedding_to_ring2_signals(
            db, workspace_id, post_embedding, cutoff=0.35
        )

        # Stage 5: Legacy capability-profile relevance score
        row = await db.execute(
            text("SELECT embedding::text FROM capability_profile_versions WHERE id = :id"),
            {"id": str(profile.id)},
        )
        emb_str = row.scalar_one_or_none()
        capability_embedding = json.loads(emb_str) if emb_str else None

        if capability_embedding is None:
            # Workspace has a capability profile but no embedding yet. Mark the
            # post processed so it isn't retried forever, and log loudly so the
            # operator knows to re-run profile extraction for this workspace.
            logger.warning(
                "pipeline_skipped_missing_capability_embedding "
                "workspace_id=%s profile_id=%s post_id=%s",
                workspace_id, profile.id, post_id,
            )
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        relevance_score = cosine_similarity(post_embedding, capability_embedding)

        # Stage 6: Compute keyword_match_strength (0-1)
        active_signal_count = max(len(signal_rows), 1)
        keyword_match_strength = min(1.0, len(ring1_matches) / active_signal_count)

        workspace = await db.get(Workspace, workspace_id)
        connection = await db.get(Connection, post.connection_id)

        # Persist ring matches, themes, embedding immediately — even if we
        # decide below that this post doesn't cross the alert threshold.
        post_emb_str = "[" + ",".join(str(x) for x in post_embedding) + "]"
        await db.execute(
            text("UPDATE posts SET embedding = CAST(:e AS vector) WHERE id = :id"),
            {"e": post_emb_str, "id": str(post_id)},
        )
        await db.execute(
            update(Post).where(Post.id == post_id).values(
                ring1_matches=ring1_matches,
                ring2_matches=ring2_matches,
                relevance_score=relevance_score,
            )
        )

        # Stage 7: Scoring
        if connection is None:
            # Orphan post — can't score relationship dimension, mark processed
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        scoring = compute_combined_score(
            relevance_score=relevance_score,
            connection=connection,
            posted_at=post.posted_at or post.ingested_at,
            weights=workspace.scoring_weights,
            keyword_match_strength=keyword_match_strength,
        )

        threshold = workspace.matching_threshold or 0.72
        if scoring.combined_score < threshold:
            await db.execute(
                update(Post).where(Post.id == post_id).values(
                    processed_at=datetime.now(timezone.utc),
                    matched=False,
                    relevance_score=scoring.relevance_score,
                    relationship_score=scoring.relationship_score,
                    timing_score=scoring.timing_score,
                    combined_score=scoring.combined_score,
                )
            )
            await db.commit()
            await engine.dispose()
            return

        # Stage 8: Context generation (includes themes)
        context = await generate_alert_context(
            post_content=post.content,
            author_name=connection.name,
            author_headline=connection.headline or "",
            author_company=connection.company or "",
            degree=connection.degree,
            enrichment_summary=str(connection.enrichment_data or ""),
            capability_profile=profile.raw_text,
            priority=scoring.priority,
        )

        # Stage 9: Persist themes + final scores
        await db.execute(
            update(Post).where(Post.id == post_id).values(
                processed_at=datetime.now(timezone.utc),
                matched=True,
                relevance_score=scoring.relevance_score,
                relationship_score=scoring.relationship_score,
                timing_score=scoring.timing_score,
                combined_score=scoring.combined_score,
                themes=context.themes,
            )
        )

        # Stage 10: Create alert
        alert = Alert(
            workspace_id=workspace_id,
            post_id=post_id,
            connection_id=post.connection_id,
            relevance_score=scoring.relevance_score,
            relationship_score=scoring.relationship_score,
            timing_score=scoring.timing_score,
            combined_score=scoring.combined_score,
            priority=scoring.priority.value,
            match_reason=context.match_reason,
            outreach_draft_a=context.outreach_draft_a,
            outreach_draft_b=context.outreach_draft_b,
            opportunity_type=context.opportunity_type,
            urgency_reason=context.urgency_reason,
        )
        db.add(alert)
        await db.flush()

        effectiveness = SignalEffectiveness(
            workspace_id=workspace_id,
            alert_id=alert.id,
            predicted_score=scoring.combined_score,
        )
        db.add(effectiveness)
        await db.flush()

        await DeliveryRouter().deliver(alert=alert, db=db)
        await db.commit()

    await engine.dispose()
