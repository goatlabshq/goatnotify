from uuid import uuid4

from django.db import models
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_model, dump_notification
from goatnotify.django.tasks import deliver_notification


class DjangoTasksQueue:
    def __init__(
        self,
        *,
        queue_name: str | None = None,
        priority: int | None = None,
        backend: str | None = None,
    ) -> None:
        self._queue_name = queue_name
        self._priority = priority
        self._backend = backend

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        if not isinstance(job.notifiable, models.Model):
            raise ConfigurationError("DjangoTasksQueue needs a Django model instance as notifiable")
        notifiable = dump_model(job.notifiable)
        notification = dump_notification(job.notification)
        task = deliver_notification.using(
            queue_name=self._queue_name, priority=self._priority, backend=self._backend
        )
        await task.aenqueue(notifiable, notification, job_id=str(uuid4()))
