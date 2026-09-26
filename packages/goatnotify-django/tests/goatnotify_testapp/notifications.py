from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from goatnotify import (
    DatabaseChannel,
    DatabaseMessage,
    EmailChannel,
    JsonValue,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
)
from goatnotify.core.testing import MemoryStore, MemoryTransport
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
