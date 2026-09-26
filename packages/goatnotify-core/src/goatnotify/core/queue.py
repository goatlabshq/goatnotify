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
class DrainableQueue(Queue, Protocol):
    async def drain(self) -> None: ...


class AsyncioQueue:
    """In-process queue running jobs as asyncio tasks; drain or close it on shutdown."""

    def __init__(self, *, concurrency: int = 10) -> None:
        if concurrency < 1:
            raise ValueError("AsyncioQueue.concurrency must be at least 1")
        self._concurrency = concurrency
        self._semaphore: tuple[asyncio.AbstractEventLoop, asyncio.Semaphore] | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        if self._closed:
            raise ConfigurationError("AsyncioQueue is closed")
        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        # Finished tasks leave the set one loop iteration later, and gather() over finished
        # tasks never yields, so waiting only on unfinished ones is what lets that happen.
        while pending := [task for task in self._tasks if not task.done()]:
            await asyncio.wait(pending)

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

    def _semaphore_for(self, loop: asyncio.AbstractEventLoop) -> asyncio.Semaphore:
        # A semaphore binds to the first loop it waits on; test clients start a loop per run.
        if self._semaphore is None or self._semaphore[0] is not loop:
            self._semaphore = (loop, asyncio.Semaphore(self._concurrency))
        return self._semaphore[1]

    async def _run[R: Notifiable](self, job: NotificationJob[R]) -> None:
        async with self._semaphore_for(asyncio.get_running_loop()):
            try:
                await job.run()
            except Exception:
                logger.exception(
                    "Queued notification %s failed", type(job.notification).__qualname__
                )
