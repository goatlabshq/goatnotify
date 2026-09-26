"""A plain asyncio application sending email, database and webhook notifications."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from html import escape

from goatnotify import (
    DatabaseChannel,
    DatabaseMessage,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
    WebhookChannel,
    WebhookMessage,
    events,
)
from goatnotify.core.testing import MemoryHttpTransport, MemoryStore, MemoryTransport


@dataclass
class User:
    id: int
    name: str
    email: str
    slack_webhook: str | None = None

    def route_notification(self, channel: str) -> str | None:
        match channel:
            case "email":
                return self.email
            case "webhook":
                return self.slack_webhook
            case _:
                return None


class WelcomeMail(Mailable):
    subject = "Welcome to Goat"

    def __init__(self, user: User) -> None:
        self.user = user

    def html(self) -> str | None:
        return f"<h1>Welcome, {escape(self.user.name)}!</h1>"

    def text(self) -> str | None:
        return f"Welcome, {self.user.name}!"


class Welcome(Notification[User]):
    def __init__(self, plan: str) -> None:
        self.plan = plan

    def messages(self, notifiable: User) -> Iterable[Message]:
        yield WelcomeMail(notifiable)
        yield DatabaseMessage(kind="welcome", data={"plan": self.plan})
        if notifiable.slack_webhook:
            yield WebhookMessage(payload={"text": f"{notifiable.name} joined on {self.plan}"})


def log(event: events.Event) -> None:
    print(f"{event.name:<24} {event.channel:<9} attempt {event.attempt}")


async def main() -> None:
    outbox, store, http = MemoryTransport(), MemoryStore(), MemoryHttpTransport()
    notifier = Notifier(
        [
            EmailChannel(Mailer(outbox, sender="Goat <noreply@goat.dev>")),
            DatabaseChannel(store),
            WebhookChannel(http),
        ],
        hooks=[log],
    )
    user = User(1, "Ada", "ada@example.com", slack_webhook="https://hooks.slack.com/services/T/B/X")
    result = await notifier.notify(user, Welcome(plan="pro"))
    print(
        f"ok={result.ok} email={outbox.outbox[0].subject!r} "
        f"stored={store.records[0][1].kind!r} webhooks={len(http.requests)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
