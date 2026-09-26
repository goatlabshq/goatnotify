from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    Channel,
    DatabaseMessage,
    Mailable,
    Message,
    Notifiable,
    Notification,
    Notifier,
    RetryPolicy,
    WebhookMessage,
)


@dataclass
class User:
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email


@dataclass
class Admin(User):
    level: int = 1


class Anonymous:
    pass


class ForUsers(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        return []


class AdminOnly(Notification[Admin]):
    def messages(self, notifiable: Admin) -> Iterable[Message]:
        return []


class WrongSend(Channel[Mailable]):
    name = "wrong"
    message_type = Mailable

    async def send(self, notifiable: Notifiable, message: WebhookMessage) -> str | None:  # expect-error
        return None


class WrongType(Channel[Mailable]):
    name = "wrong"
    message_type = WebhookMessage  # expect-error

    async def send(self, notifiable: Notifiable, message: Mailable) -> str | None:
        return None


class NotAMessage(Channel[str]):  # expect-error
    pass


async def misuse(notifier: Notifier, user: User) -> None:
    await notifier.notify(user, AdminOnly())  # expect-error
    await notifier.notify(Anonymous(), ForUsers())  # expect-error
    await notifier.notify(user, ForUsers(), raise_on_failure="yes")  # expect-error
    DatabaseMessage(kind="x", data={"when": object()})  # expect-error
    RetryPolicy(max_attempts="3")  # expect-error
    WebhookMessage(payload={}, method="GET")  # expect-error
    Notifier([object()])  # expect-error
