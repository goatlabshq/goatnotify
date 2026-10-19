from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from goatnotify import (
    Channel,
    DatabaseChannel,
    DatabaseMessage,
    EmailChannel,
    JsonValue,
    Mailable,
    Mailer,
    Message,
    Notifiable,
    Notification,
    Notifier,
    PermanentError,
)
from goatnotify.core.testing import MemoryStore, MemoryTransport
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify_testapp.models import Member


class WelcomeMail(Mailable):
    subject = "Welcome"

    def __init__(self, plan: str) -> None:
        self.plan = plan

    def text(self) -> str | None:
        return f"Welcome on the {self.plan} plan"


@dataclass
class Welcome(Notification[Member]):
    plan: str
    referrer: Member | None = None

    def messages(self, notifiable: Member) -> Iterable[Message]:
        yield WelcomeMail(self.plan)
        referrer = None if self.referrer is None else self.referrer.email
        yield DatabaseMessage(kind="welcome", data={"plan": self.plan, "referrer": referrer})


MEMORY = MemoryTransport()


def build_notifier() -> Notifier:
    return Notifier(
        [EmailChannel(Mailer(MEMORY, sender="noreply@goat.dev")), DatabaseChannel(MemoryStore())]
    )


def build_nothing() -> object:
    return object()


class Tier(StrEnum):
    PRO = "pro"


@dataclass
class Tagged(Notification[Member]):
    tags: tuple[str, ...] | None = None
    tier: Tier | None = None
    labels: dict[int, str] = field(default_factory=dict[int, str])
    extra: dict[str, JsonValue] = field(default_factory=dict[str, JsonValue])

    def messages(self, notifiable: Member) -> Iterable[Message]:
        return []


@dataclass(frozen=True, slots=True)
class Alert(Message):
    text: str


class FlakyChannel(Channel[Alert]):
    name = "alert"
    message_type = Alert

    def __init__(self) -> None:
        self.failures_left = 0
        self.sent: list[Alert] = []

    async def send(self, notifiable: Notifiable, message: Alert) -> str | None:
        if self.failures_left:
            self.failures_left -= 1
            raise PermanentError("alert service down")
        self.sent.append(message)
        return None


FLAKY = FlakyChannel()


@dataclass
class WelcomeWithAlert(Notification[Member]):
    plan: str

    def messages(self, notifiable: Member) -> Iterable[Message]:
        yield WelcomeMail(self.plan)
        yield Alert(f"{notifiable.email} joined")


def build_flaky_notifier() -> Notifier:
    mailer = Mailer(DjangoEmailTransport(), sender="noreply@goat.dev")
    return Notifier([EmailChannel(mailer), FLAKY], queue=DjangoTasksQueue(backend="database"))
