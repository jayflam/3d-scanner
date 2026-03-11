"""Celery application configuration with Redis broker."""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_init

from app.config import settings

celery = Celery(
    "insurascan",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_hijack_root_logger=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    include=[
        "app.tasks.extract_frames",
        "app.tasks.run_splatting",
        "app.tasks.analyze_damage",
        "app.tasks.generate_report",
        "app.tasks.pipeline",
    ],
)


@worker_init.connect
def init_blob_storage(**kwargs):
    """Initialize blob storage when the Celery worker starts."""
    from app.services.blob_storage import blob_storage
    blob_storage.init()
