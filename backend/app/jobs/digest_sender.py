# backend/app/jobs/digest_sender.py
"""
Hourly email digest for MEDIUM and LOW priority alerts.
Batches unsent medium/low alerts and sends a single digest email per workspace.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from app.workers.celery_app import celery_app


@celery_app.task(name="app.jobs.digest_sender.send_digests")
def send_digests():
    asyncio.run(_send_all_digests())


async def _send_all_digests():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, update
    from app.models.alert import Alert
    from app.models.workspace import Workspace
    from app.delivery.email import EmailSender
    from app.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    sender = EmailSender()

    async with Session() as db:
        # Find unsent medium/low alerts from the last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(Alert)
            .where(Alert.priority.in_(["medium", "low"]))
            .where(Alert.status == "pending")
            .where(Alert.created_at >= one_hour_ago)
        )
        alerts = result.scalars().all()

        if not alerts:
            await engine.dispose()
            return

        # Group by workspace
        by_workspace: dict = {}
        for alert in alerts:
            ws_id = str(alert.workspace_id)
            by_workspace.setdefault(ws_id, []).append(alert)

        for ws_id, ws_alerts in by_workspace.items():
            from uuid import UUID
            workspace = await db.get(Workspace, UUID(ws_id))
            if not workspace:
                continue

            email_config = (workspace.delivery_channels or {}).get("email", {})
            if not email_config.get("address"):
                continue

            now = datetime.now(timezone.utc)
            for alert in ws_alerts:
                await sender.send(alert=alert, workspace=workspace)
                await db.execute(
                    update(Alert).where(Alert.id == alert.id)
                    .values(status="delivered", delivered_at=now)
                )

        await db.commit()

    await engine.dispose()
