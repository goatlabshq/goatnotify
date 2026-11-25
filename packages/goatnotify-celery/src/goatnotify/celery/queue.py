import asyncio
from typing import Any
from uuid import uuid4

from celery import Celery
from goatnotify.celery.tasks import TASK_NAME
from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_job


class CeleryQueue:
    def __init__(
        self, app: Celery, *, queue: str | None = None, priority: int | None = None
    ) -> None:
        self._app = app
        self._queue = queue
        self._priority = priority

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        notifiable, notification = dump_job(job, queue=type(self).__name__)
        job_id = str(uuid4())
        # send_task ignores task_always_eager; the registered task honours it.
        task = self._app.tasks[TASK_NAME]
        routing: dict[str, Any] = {"queue": self._queue, "priority": self._priority}
        await asyncio.to_thread(
            task.apply_async,
            args=(notifiable, notification, job_id),
            task_id=job_id,
            **{key: value for key, value in routing.items() if value is not None},
        )
