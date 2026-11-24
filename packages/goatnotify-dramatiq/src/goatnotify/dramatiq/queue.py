import asyncio
from typing import Final, Protocol, Self, cast
from uuid import uuid4

import dramatiq
from dramatiq.errors import ActorNotFound
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_job

ACTOR_NAME: Final = "goatnotify.deliver"


class _Message(Protocol):
    @property
    def queue_name(self) -> str: ...

    def copy(self, **attributes: object) -> Self: ...


class _Broker(Protocol):
    def get_actor(self, actor_name: str) -> object: ...

    def get_declared_queues(self) -> set[str]: ...

    def declare_queue(self, queue_name: str) -> None: ...

    def enqueue(self, message: _Message) -> object: ...


class _Actor(Protocol):
    """The part of ``dramatiq.Actor`` used here; Dramatiq leaves its message types unknown."""

    queue_name: str

    def message_with_options(
        self, *, args: tuple[object, ...], kwargs: dict[str, object], **options: object
    ) -> _Message: ...


class DramatiqQueue:
    def __init__(self, *, queue_name: str | None = None, max_retries: int | None = None) -> None:
        self._queue_name = queue_name
        self._options: dict[str, object] = {}
        if max_retries is not None:
            self._options["max_retries"] = max_retries

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        notifiable, notification = dump_job(job, queue=type(self).__name__)
        broker = cast("_Broker", dramatiq.get_broker())
        actor = _actor(broker)
        job_id = str(uuid4())
        message = actor.message_with_options(
            args=(notifiable, notification, job_id), kwargs={}, **self._options
        ).copy(message_id=job_id, queue_name=self._queue_name or actor.queue_name)
        await asyncio.to_thread(_send, broker, message)


def _actor(broker: _Broker) -> _Actor:
    try:
        actor = broker.get_actor(ACTOR_NAME)
    except ActorNotFound as error:
        raise ConfigurationError(
            f"The {ACTOR_NAME!r} actor is not registered: add 'goatnotify.dramatiq' to "
            "INSTALLED_APPS so django_dramatiq discovers it"
        ) from error
    return cast("_Actor", actor)


def _send(broker: _Broker, message: _Message) -> None:
    if message.queue_name not in broker.get_declared_queues():
        broker.declare_queue(message.queue_name)
    broker.enqueue(message)
