import asyncio
import time
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager

import pytest
from core_support import User
from fastapi import FastAPI
from fastapi.testclient import TestClient

from goatnotify import (
    AsyncioQueue,
    ConfigurationError,
    EmailChannel,
    EmailMessage,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
)
from goatnotify.core.testing import MemoryTransport
from goatnotify.fastapi import NotifierDep, attach, lifespan


class Hello(Mailable):
    subject = "Hello"

    def text(self) -> str | None:
        return "Hello!"


class Greeting(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Hello()


def _app(app: FastAPI) -> FastAPI:
    @app.post("/now")
    async def now(notifier: NotifierDep) -> dict[str, bool]:
        result = await notifier.notify(User(), Greeting())
        return {"ok": result.ok}

    @app.post("/later")
    async def later(notifier: NotifierDep) -> dict[str, bool]:
        await notifier.enqueue(User(), Greeting())
        return {"queued": True}

    return app


def _notifier() -> tuple[Notifier, MemoryTransport]:
    transport = MemoryTransport()
    mailer = Mailer(transport, sender="noreply@goat.dev")
    return Notifier([EmailChannel(mailer)], queue=AsyncioQueue()), transport


def test_the_notifier_is_injected() -> None:
    notifier, transport = _notifier()
    with TestClient(_app(FastAPI(lifespan=lifespan(notifier)))) as client:
        assert client.post("/now").json() == {"ok": True}
    assert len(transport.outbox) == 1


def test_queued_notifications_are_drained_on_shutdown() -> None:
    notifier, transport = _notifier()
    with TestClient(_app(FastAPI(lifespan=lifespan(notifier)))) as client:
        assert client.post("/later").json() == {"queued": True}
    assert len(transport.outbox) == 1


def test_attach_composes_with_an_existing_lifespan() -> None:
    notifier, transport = _notifier()

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with attach(app, notifier):
            yield

    with TestClient(_app(FastAPI(lifespan=app_lifespan))) as client:
        client.post("/now")
    assert len(transport.outbox) == 1


def test_a_missing_notifier_is_a_configuration_error() -> None:
    with TestClient(_app(FastAPI())) as client, pytest.raises(ConfigurationError, match="lifespan"):
        client.post("/now")


def test_the_same_app_can_start_twice() -> None:
    notifier, transport = _notifier()
    app = _app(FastAPI(lifespan=lifespan(notifier)))
    for _ in range(2):
        with TestClient(app) as client:
            assert client.post("/later").json() == {"queued": True}
    assert len(transport.outbox) == 2


def test_shutdown_does_not_wait_forever_for_stuck_notifications() -> None:
    class Stuck(MemoryTransport):
        async def send(self, message: EmailMessage) -> str | None:
            await asyncio.sleep(60)
            return await super().send(message)

    transport = Stuck()
    mailer = Mailer(transport, sender="noreply@goat.dev")
    notifier = Notifier([EmailChannel(mailer)], queue=AsyncioQueue())
    app = _app(FastAPI(lifespan=lifespan(notifier, shutdown_timeout=0.05)))
    started = time.monotonic()
    with TestClient(app) as client:
        client.post("/later")
    assert time.monotonic() - started < 5
    assert transport.outbox == []
