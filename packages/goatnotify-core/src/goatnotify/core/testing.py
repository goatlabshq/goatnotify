from collections import deque

from goatnotify.core.channels.database import StoredNotification
from goatnotify.core.http import HttpRequest, HttpResponse
from goatnotify.core.mail.message import EmailMessage
from goatnotify.core.notification import Notifiable

OK = HttpResponse(200, {}, b"")


async def no_sleep(delay: float) -> None:
    pass


class MemoryTransport:
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
    def __init__(self) -> None:
        self.records: list[tuple[Notifiable, StoredNotification]] = []

    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        self.records.append((notifiable, record))

    def for_notifiable(self, notifiable: Notifiable) -> list[StoredNotification]:
        return [record for owner, record in self.records if owner is notifiable]


class MemoryHttpTransport:
    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self._outcomes: deque[HttpResponse | Exception] = deque()

    def respond(self, *outcomes: HttpResponse | Exception) -> None:
        self._outcomes.extend(outcomes)

    async def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        outcome = self._outcomes.popleft() if self._outcomes else OK
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
