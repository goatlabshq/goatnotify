"""FastAPI integration for GoatNotify."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated, Final

from fastapi import Depends, FastAPI, Request
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import DrainableQueue

__all__ = ["NotifierDep", "attach", "get_notifier", "lifespan"]

STATE_KEY: Final = "goatnotify"
DEFAULT_SHUTDOWN_TIMEOUT: Final = 30.0


@asynccontextmanager
async def attach(
    app: FastAPI, notifier: Notifier, *, shutdown_timeout: float | None = DEFAULT_SHUTDOWN_TIMEOUT
) -> AsyncGenerator[None]:
    setattr(app.state, STATE_KEY, notifier)
    try:
        yield
    finally:
        if isinstance(notifier.queue, DrainableQueue):
            await notifier.queue.drain(timeout=shutdown_timeout)


def lifespan(
    notifier: Notifier, *, shutdown_timeout: float | None = DEFAULT_SHUTDOWN_TIMEOUT
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    def _lifespan(app: FastAPI) -> AbstractAsyncContextManager[None]:
        return attach(app, notifier, shutdown_timeout=shutdown_timeout)

    return _lifespan


def get_notifier(request: Request) -> Notifier:
    notifier: object = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(notifier, Notifier):
        raise ConfigurationError(
            "No notifier attached: use FastAPI(lifespan=goatnotify.fastapi.lifespan(notifier))"
        )
    return notifier


NotifierDep = Annotated[Notifier, Depends(get_notifier)]
