import os
from celery import Celery

# Read directly from env to avoid eager pydantic settings instantiation at import time.
# Celery needs broker/backend URLs at construction; os.environ is safe at module level.
_redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "sonar",
    broker=_redis_url,
    backend=_redis_url,
    include=[
        "app.workers.pipeline",
        "app.jobs.public_poller",
        "app.jobs.digest_sender",
        "app.jobs.day_one_backfill_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "public-post-poller": {
            "task": "app.jobs.public_poller.poll_public_posts",
            "schedule": 3600.0,  # every hour
        },
        "email-digest-sender": {
            "task": "app.jobs.digest_sender.send_digests",
            "schedule": 3600.0,  # every hour
        },
    },
)
