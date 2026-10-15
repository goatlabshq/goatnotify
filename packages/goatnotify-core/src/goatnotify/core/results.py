from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from goatnotify.core.errors import DeliveryFailed
from goatnotify.core.notification import Message, Notification


class DeliveryStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryResult:
    channel: str
    message: Message
    status: DeliveryStatus
    attempts: int
    provider_id: str | None = None
    error: Exception | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationResult:
    id: UUID
    notification: Notification[Any]
    deliveries: tuple[DeliveryResult, ...]

    @property
    def ok(self) -> bool:
        return not self.failed

    @property
    def failed(self) -> tuple[DeliveryResult, ...]:
        return tuple(d for d in self.deliveries if d.status is DeliveryStatus.FAILED)

    def raise_for_failures(self) -> None:
        if self.failed:
            raise DeliveryFailed.from_result(self)
