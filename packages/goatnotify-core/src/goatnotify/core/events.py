"""Events passed to notifier hooks."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Literal
from uuid import UUID

from goatnotify.core.errors import RetryableError
from goatnotify.core.notification import Message, Notifiable, Notification


@dataclass(frozen=True, slots=True, kw_only=True)
class _DeliveryEvent:
    notification_id: UUID
    notification: Notification[Any]
    notifiable: Notifiable
    channel: str
    message: Message
    attempt: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Sending(_DeliveryEvent):
    name: ClassVar[Literal["notification.sending"]] = "notification.sending"


@dataclass(frozen=True, slots=True, kw_only=True)
class Retrying(_DeliveryEvent):
    name: ClassVar[Literal["notification.retrying"]] = "notification.retrying"
    delay: float
    error: RetryableError


@dataclass(frozen=True, slots=True, kw_only=True)
class Sent(_DeliveryEvent):
    name: ClassVar[Literal["notification.sent"]] = "notification.sent"
    provider_id: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed(_DeliveryEvent):
    name: ClassVar[Literal["notification.failed"]] = "notification.failed"
    error: Exception


@dataclass(frozen=True, slots=True, kw_only=True)
class Skipped(_DeliveryEvent):
    name: ClassVar[Literal["notification.skipped"]] = "notification.skipped"
    reason: str


type Event = Sending | Retrying | Sent | Failed | Skipped
type Hook = Callable[[Event], Awaitable[None] | None]
