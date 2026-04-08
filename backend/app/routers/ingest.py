from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.connection import Connection
from app.routers.auth import get_current_user
from app.schemas.ingest import PostIngestPayload, IngestResponse
from app.workers.pipeline import process_post_pipeline
import uuid

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestResponse)
async def ingest_posts(
    payload: PostIngestPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queued = 0
    skipped = 0

    for item in payload.posts:
        # Upsert connection
        conn_stmt = insert(Connection).values(
            id=uuid.uuid4(),
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            linkedin_id=item.author.linkedin_id,
            name=item.author.name,
            headline=item.author.headline,
            profile_url=item.author.profile_url,
            degree=item.author.degree,
        ).on_conflict_do_update(
            index_elements=["workspace_id", "linkedin_id"],
            set_={
                "name": item.author.name,
                "headline": item.author.headline,
                "degree": item.author.degree,
            }
        ).returning(Connection.id)

        conn_result = await db.execute(conn_stmt)
        connection_id = conn_result.scalar_one()

        # Check for duplicate post
        existing = await db.execute(
            select(Post.id).where(
                Post.workspace_id == current_user.workspace_id,
                Post.linkedin_post_id == item.linkedin_post_id,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        post = Post(
            workspace_id=current_user.workspace_id,
            connection_id=connection_id,
            linkedin_post_id=item.linkedin_post_id,
            content=item.content,
            post_type=item.post_type,
            source="extension",
            posted_at=item.posted_at,
            extraction_version=payload.extraction_version,
        )
        db.add(post)
        await db.flush()

        process_post_pipeline.delay(str(post.id), str(current_user.workspace_id))
        queued += 1

    await db.commit()
    return IngestResponse(queued=queued, skipped=skipped)
