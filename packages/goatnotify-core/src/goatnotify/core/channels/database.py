"""Database channel: persists notifications through a NotificationStore."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy


@dataclass(frozen=True, slots=True)
class DatabaseMessage(Message):
    kind: str
    data: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StoredNotification:
    id: UUID
    kind: str
    data: Mapping[str, JsonValue]
    created_at: datetime


class NotificationStore(Protocol):
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class DatabaseChannel(Channel[DatabaseMessage]):
    name = "database"
    message_type = DatabaseMessage

    def __init__(
        self,
        store: NotificationStore,
        *,
        retry: RetryPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._store = store
        self._clock = clock
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: DatabaseMessage) -> str | None:
        record = StoredNotification(
            id=uuid4(), kind=message.kind, data=message.data, created_at=self._clock()
        )
        await self._store.store(notifiable, record)
        return str(record.id)
