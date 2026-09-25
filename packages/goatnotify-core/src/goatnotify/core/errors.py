"""Exception hierarchy shared by every GoatNotify component."""

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from goatnotify.core.results import NotificationResult


class NotificationError(Exception):
    """Base class of every GoatNotify error."""


class ConfigurationError(NotificationError):
    """GoatNotify is wired incorrectly: retrying cannot help."""


class DeliveryError(NotificationError):
    """Raised by channels and transports to describe a delivery outcome."""


class RetryableError(DeliveryError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(DeliveryError):
    pass


class InvalidMessageError(PermanentError):
    pass


class SkipDelivery(DeliveryError):  # noqa: N818 (a control-flow signal, not an error)
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DeliveryFailed(ExceptionGroup[Exception]):
    """Raised once every delivery of a notification has finished and at least one failed."""

    result: NotificationResult

    @classmethod
    def from_result(cls, result: NotificationResult) -> Self:
        errors = [delivery.error for delivery in result.deliveries if delivery.error is not None]
        group = cls(f"{len(errors)} of {len(result.deliveries)} deliveries failed", errors)
        group.result = result
        return group
