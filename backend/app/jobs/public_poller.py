# backend/app/jobs/public_poller.py
"""
Public post poller — fallback for workspaces without Chrome extension.
Runs hourly via Celery Beat. Uses Apify LinkedIn scrapers.
"""
import uuid
import httpx
import asyncio
from app.workers.celery_app import celery_app
from app.config import get_settings

APIFY_LINKEDIN_ACTOR = "curious_coder/linkedin-post-search-scraper"


@celery_app.task(name="app.jobs.public_poller.poll_public_posts")
def poll_public_posts():
    asyncio.run(_poll_all_workspaces())


async def _poll_all_workspaces():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.user import User
    from app.models.post import Post
    from app.models.connection import Connection
    from app.workers.pipeline import process_post_pipeline

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Find workspaces without any extension-installed users
        result = await db.execute(
            select(Workspace).join(User, User.workspace_id == Workspace.id)
            .where(User.extension_installed == False)
        )
        workspaces = result.scalars().all()

        for workspace in workspaces:
            # Get active capability profile keywords
            profile_result = await db.execute(
                select(CapabilityProfileVersion)
                .where(CapabilityProfileVersion.workspace_id == workspace.id)
                .where(CapabilityProfileVersion.is_active == True)
            )
            profile = profile_result.scalar_one_or_none()
            if not profile or not profile.signal_keywords:
                continue

            # Use first 3 signal keywords as search query
            query = " OR ".join(profile.signal_keywords[:3])
            posts = await fetch_apify_posts(query=query, limit=50)

            owner_result = await db.execute(
                select(User)
                .where(User.workspace_id == workspace.id)
                .where(User.role == "owner")
                .limit(1)
            )
            owner = owner_result.scalar_one_or_none()
            if not owner:
                continue

            for raw_post in posts:
                linkedin_id = raw_post.get("author_id") or raw_post.get("author_name") or "unknown"

                # Upsert connection
                conn_stmt = pg_insert(Connection).values(
                    id=uuid.uuid4(),
                    workspace_id=workspace.id,
                    user_id=owner.id,
                    linkedin_id=linkedin_id,
                    name=raw_post.get("author_name", "Unknown"),
                    headline=raw_post.get("author_headline", ""),
                    degree=3,  # Unknown degree for public posts
                ).on_conflict_do_update(
                    index_elements=["workspace_id", "linkedin_id"],
                    set_={"name": raw_post.get("author_name", "Unknown")},
                ).returning(Connection.id)

                conn_result = await db.execute(conn_stmt)
                connection_id = conn_result.scalar_one()

                # Skip duplicate posts
                existing = await db.execute(
                    select(Post.id).where(
                        Post.workspace_id == workspace.id,
                        Post.linkedin_post_id == raw_post["post_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                post = Post(
                    workspace_id=workspace.id,
                    connection_id=connection_id,
                    linkedin_post_id=raw_post["post_id"],
                    content=raw_post.get("text", ""),
                    post_type="post",
                    source="public_fallback",
                )
                db.add(post)
                await db.flush()

                process_post_pipeline.delay(str(post.id), str(workspace.id))

            await db.commit()

    await engine.dispose()


async def fetch_apify_posts(query: str, limit: int = 50) -> list[dict]:
    """
    Call Apify LinkedIn post search actor and return normalized post list.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Start Apify run
        start_resp = await client.post(
            f"https://api.apify.com/v2/acts/{APIFY_LINKEDIN_ACTOR}/runs",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            json={"searchQuery": query, "maxResults": limit},
        )
        if not start_resp.is_success:
            return []

        run_id = start_resp.json()["data"]["id"]

        # Poll for completion (max 60s)
        status_resp = None
        for _ in range(12):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            )
            if status_resp.json()["data"]["status"] == "SUCCEEDED":
                break

        if not status_resp:
            return []

        # Fetch results
        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        results_resp = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
        )
        if not results_resp.is_success:
            return []

        items = results_resp.json()
        return [
            {
                "post_id": item.get("id") or item.get("url") or str(uuid.uuid4()),
                "text": item.get("text", ""),
                "author_name": item.get("authorName", "Unknown"),
                "author_headline": item.get("authorHeadline", ""),
                "author_id": item.get("authorProfileUrl", "").split("/in/")[-1].split("/")[0] or "unknown",
            }
            for item in items
            if item.get("text")
        ]
