from uuid import uuid4

import pytest
from core_support import Ping, Pings

from goatnotify.core.errors import DeliveryFailed, PermanentError, RetryableError
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult


def _result(*deliveries: DeliveryResult) -> NotificationResult:
    return NotificationResult(id=uuid4(), notification=Pings(), deliveries=deliveries)


def _delivery(status: DeliveryStatus, error: Exception | None = None) -> DeliveryResult:
    return DeliveryResult(channel="ping", message=Ping("x"), status=status, attempts=1, error=error)


def test_a_result_without_failures_is_ok() -> None:
    result = _result(_delivery(DeliveryStatus.SENT), _delivery(DeliveryStatus.SKIPPED))
    assert result.ok
    assert result.failed == ()
    result.raise_for_failures()


def test_raise_for_failures_groups_every_error() -> None:
    retryable, permanent = RetryableError("later"), PermanentError("never")
    result = _result(
        _delivery(DeliveryStatus.FAILED, retryable),
        _delivery(DeliveryStatus.SENT),
        _delivery(DeliveryStatus.FAILED, permanent),
    )
    with pytest.raises(DeliveryFailed) as caught:
        result.raise_for_failures()
    assert caught.value.result is result
    assert list(caught.value.exceptions) == [retryable, permanent]
    assert str(caught.value).startswith("2 of 3 deliveries failed")


def test_delivery_failed_supports_except_star() -> None:
    result = _result(_delivery(DeliveryStatus.FAILED, PermanentError("never")))
    handled: list[Exception] = []
    try:
        result.raise_for_failures()
    except* PermanentError as group:
        handled.extend(group.exceptions)
    assert len(handled) == 1


def test_messages_are_slotted_value_objects() -> None:
    assert Ping("a") == Ping("a")
    assert not hasattr(Ping("a"), "__dict__")
