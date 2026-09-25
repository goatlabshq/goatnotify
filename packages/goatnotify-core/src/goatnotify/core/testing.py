"""In-memory fakes for testing code that sends notifications."""

from collections import deque

from goatnotify.core.channels.database import StoredNotification
from goatnotify.core.mail.message import EmailMessage
from goatnotify.core.notification import Notifiable


async def no_sleep(delay: float) -> None:
    """Drop-in for asyncio.sleep that makes retries instantaneous."""


class MemoryTransport:
    """EmailTransport keeping sent messages in `outbox`."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []
        self._failures: deque[Exception] = deque()

    def fail_next(self, *errors: Exception) -> None:
        self._failures.extend(errors)

    async def send(self, message: EmailMessage) -> str | None:
        if self._failures:
            raise self._failures.popleft()
        self.outbox.append(message)
        return f"memory-{len(self.outbox)}"


class MemoryStore:
    """NotificationStore keeping records in memory."""

    def __init__(self) -> None:
        self.records: list[tuple[Notifiable, StoredNotification]] = []

    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        self.records.append((notifiable, record))

    def for_notifiable(self, notifiable: Notifiable) -> list[StoredNotification]:
        return [record for owner, record in self.records if owner is notifiable]
