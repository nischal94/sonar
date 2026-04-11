import asyncio
from uuid import UUID
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.pipeline.process_post_pipeline", bind=True, max_retries=3)
def process_post_pipeline(self, post_id: str, workspace_id: str):
    """
    Main processing pipeline for a single ingested post.
    Chain: keyword filter → embed → score → generate context → create alert → deliver
    """
    asyncio.run(_run_pipeline(UUID(post_id), UUID(workspace_id)))


async def _run_pipeline(post_id: UUID, workspace_id: UUID):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import get_settings
    from app.models.post import Post
    from app.models.connection import Connection
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.alert import Alert
    from app.models.feedback import SignalEffectiveness
    from app.services.keyword_filter import keyword_prefilter
    from app.services.matcher import compute_relevance_score
    from app.services.scorer import compute_combined_score
    from app.services.context_generator import generate_alert_context
    from app.delivery.router import DeliveryRouter
    from sqlalchemy import select, update, text
    from datetime import datetime, timezone
    import json

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
        version = result.scalar_one_or_none()
        if not version:
            await engine.dispose()
            return

        # Stage 1: Keyword pre-filter
        passes = keyword_prefilter(
            content=post.content,
            signal_keywords=version.signal_keywords or [],
            anti_keywords=version.anti_keywords or [],
        )
        if not passes:
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        # Stage 2+3: Embedding + semantic similarity
        row = await db.execute(
            text("SELECT embedding::text FROM capability_profile_versions WHERE id = :id"),
            {"id": str(version.id)}
        )
        emb_str = row.scalar_one_or_none()
        if not emb_str:
            await engine.dispose()
            return
        capability_embedding = json.loads(emb_str)

        relevance_score = await compute_relevance_score(
            post_content=post.content,
            capability_embedding=capability_embedding,
        )

        workspace = await db.get(Workspace, workspace_id)
        if relevance_score < (workspace.matching_threshold or 0.72):
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(
                    processed_at=datetime.now(timezone.utc),
                    matched=False,
                    relevance_score=relevance_score,
                )
            )
            await db.commit()
            await engine.dispose()
            return

        connection = await db.get(Connection, post.connection_id)
        if connection is None:
            await engine.dispose()
            return

        # Stage 5: 3-dimension scoring
        scoring = compute_combined_score(
            relevance_score=relevance_score,
            connection=connection,
            posted_at=post.posted_at or post.ingested_at,
            weights=workspace.scoring_weights,
        )

        # Stage 6: Context generation
        context = await generate_alert_context(
            post_content=post.content,
            author_name=connection.name if connection else "Unknown",
            author_headline=connection.headline or "",
            author_company=connection.company or "",
            degree=connection.degree if connection else 3,
            enrichment_summary=str(connection.enrichment_data) if connection else "",
            capability_profile=version.raw_text,
            priority=scoring.priority,
        )

        # Stage 7: Create alert
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

        effectiveness = SignalEffectiveness(
            workspace_id=workspace_id,
            alert_id=alert.id,
            predicted_score=scoring.combined_score,
        )
        db.add(effectiveness)

        await db.execute(
            update(Post).where(Post.id == post_id).values(
                processed_at=datetime.now(timezone.utc),
                matched=True,
                relevance_score=relevance_score,
                relationship_score=scoring.relationship_score,
                timing_score=scoring.timing_score,
                combined_score=scoring.combined_score,
            )
        )
        await db.flush()

        await DeliveryRouter().deliver(alert=alert, db=db)
        await db.commit()

    await engine.dispose()
