"""Background dispatch of notifications."""

import asyncio
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Final, Protocol, Self, runtime_checkable

from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable, Notification
from goatnotify.core.results import NotificationResult

if TYPE_CHECKING:
    from goatnotify.core.notifier import Notifier

logger: Final = logging.getLogger("goatnotify")


@dataclass(frozen=True, slots=True)
class NotificationJob[R: Notifiable]:
    notifier: Notifier
    notifiable: R
    notification: Notification[R]

    async def run(self) -> NotificationResult:
        return await self.notifier.notify(self.notifiable, self.notification)


class Queue(Protocol):
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None: ...


@runtime_checkable
class ClosableQueue(Queue, Protocol):
    async def aclose(self) -> None: ...


class AsyncioQueue:
    """In-process queue running jobs as asyncio tasks; drain or close it on shutdown."""

    def __init__(self, *, concurrency: int = 10) -> None:
        if concurrency < 1:
            raise ValueError("AsyncioQueue.concurrency must be at least 1")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        if self._closed:
            raise ConfigurationError("AsyncioQueue is closed")
        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def aclose(self) -> None:
        self._closed = True
        await self.drain()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _run[R: Notifiable](self, job: NotificationJob[R]) -> None:
        async with self._semaphore:
            try:
                await job.run()
            except Exception:
                logger.exception(
                    "Queued notification %s failed", type(job.notification).__qualname__
                )
