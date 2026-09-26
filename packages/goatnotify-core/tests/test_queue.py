import asyncio
import gc
import logging
import threading
from typing import Any

import pytest
from core_support import Ping, PingChannel, Pings, User

from goatnotify.core.errors import ConfigurationError, PermanentError
from goatnotify.core.notification import Notifiable
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import AsyncioQueue, DrainableQueue


async def test_enqueue_without_a_queue_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="queue"):
        await Notifier([PingChannel()]).enqueue(User(), Pings("x"))


async def test_jobs_run_in_the_background_and_drain_waits_for_them() -> None:
    queue = AsyncioQueue()
    channel = PingChannel()
    notifier = Notifier([channel], queue=queue)
    await notifier.enqueue(User(), Pings("later"))
    assert channel.sent == []
    await queue.drain()
    assert channel.sent == [Ping("later")]
    assert notifier.queue is queue


async def test_background_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    loop_errors: list[dict[str, Any]] = []
    asyncio.get_running_loop().set_exception_handler(lambda _, context: loop_errors.append(context))
    queue = AsyncioQueue()
    notifier = Notifier([PingChannel(PermanentError("rejected"))], queue=queue)
    with caplog.at_level(logging.ERROR, logger="goatnotify"):
        await notifier.enqueue(User(), Pings("x"))
        await queue.drain()
    gc.collect()
    assert "Queued notification Pings failed" in caplog.text
    assert loop_errors == []


async def test_a_closed_queue_rejects_new_jobs() -> None:
    async with AsyncioQueue() as queue:
        notifier = Notifier([PingChannel()], queue=queue)
    with pytest.raises(ConfigurationError, match="closed"):
        await notifier.enqueue(User(), Pings("x"))


async def test_concurrency_is_bounded() -> None:
    running = 0
    peak = 0

    class Slow(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            return None

    queue = AsyncioQueue(concurrency=2)
    notifier = Notifier([Slow()], queue=queue)
    for index in range(6):
        await notifier.enqueue(User(), Pings(str(index)))
    await queue.drain()
    assert peak == 2


def test_asyncio_queue_is_drainable_and_validates_concurrency() -> None:
    assert isinstance(AsyncioQueue(), DrainableQueue)
    with pytest.raises(ValueError, match="concurrency"):
        AsyncioQueue(concurrency=0)


def test_drain_returns_when_a_finished_task_is_still_tracked() -> None:
    # The done-callback that untracks a task runs one loop iteration after the task ends;
    # a drain() that never yields would spin forever, so the scenario runs in a watched thread.
    async def scenario() -> None:
        queue = AsyncioQueue()
        await Notifier([PingChannel()], queue=queue).enqueue(User(), Pings())
        await asyncio.sleep(0)
        await queue.drain()

    worker = threading.Thread(target=asyncio.run, args=(scenario(),), daemon=True)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()


def test_a_queue_survives_successive_event_loops() -> None:
    queue = AsyncioQueue(concurrency=1)
    channel = PingChannel()
    notifier = Notifier([channel], queue=queue)

    async def burst() -> None:
        for text in ("a", "b", "c"):
            await notifier.enqueue(User(), Pings(text))
        await queue.drain()

    asyncio.run(burst())
    asyncio.run(burst())
    assert len(channel.sent) == 6
