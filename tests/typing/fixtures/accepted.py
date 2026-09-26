from collections.abc import Iterable
from dataclasses import dataclass
from typing import assert_never, assert_type

from goatnotify import (
    Channel,
    DatabaseMessage,
    DeliveryFailed,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notifiable,
    Notification,
    NotificationResult,
    Notifier,
    RetryPolicy,
    WebhookMessage,
    events,
)
from goatnotify.core.testing import MemoryTransport


@dataclass
class User:
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None


class Welcome(Mailable):
    subject = "Welcome"

    def text(self) -> str | None:
        return "Hi"


class Joined(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Welcome()
        yield DatabaseMessage(kind="joined", data={"email": notifiable.email, "tags": ["new"]})
        yield WebhookMessage(payload={"event": "joined"}, method="PUT")


class Broadcast(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        return []


@dataclass(frozen=True, slots=True)
class Sms(Message):
    body: str


class SmsChannel(Channel[Sms]):
    name = "sms"
    message_type = Sms

    async def send(self, notifiable: Notifiable, message: Sms) -> str | None:
        return message.body


def describe(event: events.Event) -> str:
    match event:
        case events.Sending() | events.Sent():
            return event.name
        case events.Retrying(delay=delay):
            return f"retry in {delay}"
        case events.Failed(error=error):
            return repr(error)
        case events.Skipped(reason=reason):
            return reason
        case _:
            assert_never(event)


async def log(event: events.Event) -> None:
    describe(event)


async def usage(user: User) -> None:
    notifier = Notifier(
        [EmailChannel(Mailer(MemoryTransport(), sender="noreply@goat.dev")), SmsChannel()],
        retry=RetryPolicy(max_attempts=5),
        hooks=[log],
    )
    assert_type(await notifier.notify(user, Joined()), NotificationResult)
    assert_type(notifier.notify_sync(user, Broadcast()), NotificationResult)
    try:
        await notifier.notify(user, Joined())
    except DeliveryFailed as failure:
        assert_type(failure.result, NotificationResult)


class RenamedParameter(Notification[User]):
    def messages(self, user: User) -> Iterable[Message]:
        yield DatabaseMessage(kind="renamed", data={"email": user.email})
