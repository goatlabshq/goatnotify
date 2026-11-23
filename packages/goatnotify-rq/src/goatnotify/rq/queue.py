import asyncio
from typing import Final, Protocol, cast
from uuid import uuid4

from redis import Redis

from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_job
from rq import Queue, Retry

FUNCTION: Final = "goatnotify.rq.tasks.deliver_notification"
DEFAULT_QUEUE: Final = "default"


class _Queue(Protocol):
    """The typed subset of ``rq.Queue`` used here (RQ leaves some parameters unannotated)."""

    def enqueue_call(
        self,
        func: str,
        args: tuple[object, ...],
        *,
        job_id: str,
        retry: Retry | None,
    ) -> object: ...


class RQQueue:
    def __init__(
        self, connection: Redis, *, queue: str = DEFAULT_QUEUE, retry: Retry | None = None
    ) -> None:
        self._connection = connection
        self._queue = queue
        self._retry = retry

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        notifiable, notification = dump_job(job, queue=type(self).__name__)
        job_id = str(uuid4())
        queue = cast("_Queue", Queue(self._queue, connection=self._connection))
        await asyncio.to_thread(
            queue.enqueue_call,
            FUNCTION,
            (notifiable, notification, job_id),
            job_id=job_id,
            retry=self._retry,
        )
