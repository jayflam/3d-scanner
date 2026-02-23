"""Celery application configuration with Redis broker."""

from __future__ import annotations

from celery import Celery

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
)

# Auto-discover tasks in the tasks package
celery.autodiscover_tasks(["app.tasks"])
