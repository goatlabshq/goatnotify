from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify.core.channel import Channel
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.retry import RetryPolicy


@dataclass
class User:
    email: str | None = "ada@example.com"
    webhook: str | None = None

    def route_notification(self, channel: str) -> str | None:
        match channel:
            case "email":
                return self.email
            case "webhook":
                return self.webhook
            case _:
                return None


@dataclass(frozen=True, slots=True)
class Ping(Message):
    text: str


@dataclass(frozen=True, slots=True)
class LoudPing(Ping):
    pass


class PingChannel(Channel[Ping]):
    name = "ping"
    message_type = Ping

    def __init__(self, *outcomes: Exception, retry: RetryPolicy | None = None) -> None:
        self.sent: list[Ping] = []
        self.retry = retry
        self._outcomes = deque(outcomes)

    async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
        if self._outcomes:
            raise self._outcomes.popleft()
        self.sent.append(message)
        return f"ping-{len(self.sent)}"


class Pings(Notification[User]):
    def __init__(self, *texts: str) -> None:
        self.texts = texts

    def messages(self, notifiable: User) -> Iterable[Message]:
        return [Ping(text) for text in self.texts]


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
