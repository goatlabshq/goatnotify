import asyncio
from typing import Final
from uuid import uuid4

from celery import Celery
from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_job

TASK_NAME: Final = "goatnotify.deliver"


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
        await asyncio.to_thread(
            self._app.send_task,
            TASK_NAME,
            args=[notifiable, notification, job_id],
            task_id=job_id,
            queue=self._queue,
            priority=self._priority,
        )
