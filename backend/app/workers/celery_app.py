from celery import Celery
from app.config import get_settings

celery_app = Celery(
    "sonar",
    broker=get_settings().redis_url,
    backend=get_settings().redis_url,
    include=[
        "app.workers.pipeline",
        "app.jobs.public_poller",
        "app.jobs.digest_sender",
    ]
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
    }
)
