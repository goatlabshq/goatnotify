"""Retry policies applied by the notifier to RetryableError."""

import random
from dataclasses import dataclass, field
from typing import Final, Protocol

_random: Final = random.SystemRandom()


class Backoff(Protocol):
    def delay(self, attempt: int) -> float: ...


@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    initial: float = 1.0
    multiplier: float = 2.0
    maximum: float = 60.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.initial < 0 or self.maximum < self.initial:
            raise ValueError("ExponentialBackoff needs 0 <= initial <= maximum")
        if self.multiplier < 1:
            raise ValueError("ExponentialBackoff.multiplier must be at least 1")

    def delay(self, attempt: int) -> float:
        try:
            computed = min(self.maximum, self.initial * self.multiplier ** (attempt - 1))
        except OverflowError:
            computed = self.maximum
        return _random.uniform(0, computed) if self.jitter else computed


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Backoff = field(default_factory=ExponentialBackoff)
    max_delay: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("RetryPolicy.max_attempts must be at least 1")
        if self.max_delay < 0:
            raise ValueError("RetryPolicy.max_delay must not be negative")

    def delay(self, attempt: int, retry_after: float | None) -> float:
        wanted = self.backoff.delay(attempt) if retry_after is None else retry_after
        return min(wanted, self.max_delay)


NO_RETRY: Final = RetryPolicy(max_attempts=1)
