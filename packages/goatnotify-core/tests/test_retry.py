import pytest

from goatnotify.core.retry import NO_RETRY, ExponentialBackoff, RetryPolicy


def test_exponential_backoff_without_jitter_doubles_up_to_the_maximum() -> None:
    backoff = ExponentialBackoff(initial=1.0, multiplier=2.0, maximum=5.0, jitter=False)
    assert [backoff.delay(attempt) for attempt in range(1, 6)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_jitter_stays_between_zero_and_the_computed_delay() -> None:
    backoff = ExponentialBackoff(initial=2.0, multiplier=3.0, maximum=100.0)
    delays = [backoff.delay(3) for _ in range(200)]
    assert all(0.0 <= delay <= 18.0 for delay in delays)
    assert len(set(delays)) > 1


def test_huge_attempt_numbers_do_not_overflow() -> None:
    assert ExponentialBackoff(maximum=30.0, jitter=False).delay(5000) == 30.0


@pytest.mark.parametrize(
    ("initial", "multiplier", "maximum"),
    [(-1.0, 2.0, 60.0), (1.0, 0.5, 60.0), (10.0, 2.0, 1.0)],
)
def test_invalid_backoff_is_rejected(initial: float, multiplier: float, maximum: float) -> None:
    with pytest.raises(ValueError, match="ExponentialBackoff"):
        ExponentialBackoff(initial=initial, multiplier=multiplier, maximum=maximum)


def test_retry_policy_defaults_and_validation() -> None:
    assert RetryPolicy().max_attempts == 3
    assert NO_RETRY.max_attempts == 1
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
