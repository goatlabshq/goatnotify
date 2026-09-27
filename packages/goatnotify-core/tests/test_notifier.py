import asyncio
import logging
import warnings
from collections.abc import Iterable

import pytest
from core_support import LoudPing, Ping, PingChannel, Pings, SleepRecorder, User

from goatnotify.core import events
from goatnotify.core.channel import Channel
from goatnotify.core.errors import (
    ConfigurationError,
    DeliveryFailed,
    PermanentError,
    RetryableError,
    SkipDelivery,
)
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.retry import NO_RETRY, ExponentialBackoff, RetryPolicy
from goatnotify.core.testing import no_sleep

FAST = RetryPolicy(max_attempts=3, backoff=ExponentialBackoff(jitter=False))


class Other(Message):
    __slots__ = ()


class Mixed(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        return [Ping("a"), Other()]


class Loud(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield LoudPing("hey")


async def test_a_message_is_delivered_through_its_channel() -> None:
    channel = PingChannel()
    result = await Notifier([channel]).notify(User(), Pings("hello"))
    assert channel.sent == [Ping("hello")]
    assert result.ok
    (delivery,) = result.deliveries
    assert delivery.status is DeliveryStatus.SENT
    assert (delivery.channel, delivery.attempts, delivery.provider_id) == ("ping", 1, "ping-1")


async def test_routing_follows_the_message_class_hierarchy() -> None:
    channel = PingChannel()
    await Notifier([channel]).notify(User(), Loud())
    assert channel.sent == [LoudPing("hey")]


def test_two_channels_for_one_message_type_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="both handle Ping"):
        Notifier([PingChannel(), PingChannel()])


async def test_an_unroutable_message_aborts_before_anything_is_sent() -> None:
    channel = PingChannel()
    with pytest.raises(ConfigurationError, match="No channel handles Other"):
        await Notifier([channel]).notify(User(), Mixed())
    assert channel.sent == []


async def test_results_keep_message_order() -> None:
    result = await Notifier([PingChannel()]).notify(User(), Pings("a", "b", "c"))
    assert [d.message for d in result.deliveries] == [Ping("a"), Ping("b"), Ping("c")]


async def test_messages_are_delivered_concurrently() -> None:
    second_started = asyncio.Event()

    class Waiting(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            # Sequential delivery would time out here: "second" only starts after "first".
            if message.text == "first":
                await asyncio.wait_for(second_started.wait(), timeout=1)
            else:
                second_started.set()
            return await super().send(notifiable, message)

    result = await Notifier([Waiting()]).notify(User(), Pings("first", "second"))
    assert result.ok


async def test_skip_delivery_is_reported_without_failing() -> None:
    channel = PingChannel(SkipDelivery("muted"))
    result = await Notifier([channel]).notify(User(), Pings("x"))
    assert result.ok
    assert result.deliveries[0].status is DeliveryStatus.SKIPPED
    assert result.deliveries[0].reason == "muted"


async def test_retryable_errors_are_retried_with_backoff() -> None:
    sleep = SleepRecorder()
    channel = PingChannel(RetryableError("busy"), RetryableError("busy"))
    result = await Notifier([channel], retry=FAST, sleep=sleep).notify(User(), Pings("x"))
    assert result.deliveries[0].status is DeliveryStatus.SENT
    assert result.deliveries[0].attempts == 3
    assert sleep.delays == [1.0, 2.0]


async def test_retry_after_overrides_the_backoff() -> None:
    sleep = SleepRecorder()
    channel = PingChannel(RetryableError("slow down", retry_after=7.5))
    await Notifier([channel], retry=FAST, sleep=sleep).notify(User(), Pings("x"))
    assert sleep.delays == [7.5]


async def test_exhausted_retries_raise_delivery_failed() -> None:
    errors = [RetryableError("busy") for _ in range(3)]
    notifier = Notifier([PingChannel(*errors)], retry=FAST, sleep=no_sleep)
    with pytest.raises(DeliveryFailed) as caught:
        await notifier.notify(User(), Pings("x"))
    (delivery,) = caught.value.result.deliveries
    assert (delivery.status, delivery.attempts, delivery.error) == (
        DeliveryStatus.FAILED,
        3,
        errors[2],
    )


@pytest.mark.parametrize("error", [PermanentError("gone"), ValueError("bug")])
async def test_permanent_and_unexpected_errors_are_not_retried(error: Exception) -> None:
    sleep = SleepRecorder()
    notifier = Notifier([PingChannel(error)], retry=FAST, sleep=sleep)
    result = await notifier.notify(User(), Pings("x"), raise_on_failure=False)
    assert not result.ok
    assert (result.deliveries[0].attempts, result.deliveries[0].error) == (1, error)
    assert sleep.delays == []


async def test_other_deliveries_complete_when_one_fails() -> None:
    class Flaky(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            if message.text == "bad":
                raise PermanentError("rejected")
            return await super().send(notifiable, message)

    channel = Flaky()
    result = await Notifier([channel]).notify(User(), Pings("bad", "good"), raise_on_failure=False)
    assert [d.status for d in result.deliveries] == [DeliveryStatus.FAILED, DeliveryStatus.SENT]
    assert channel.sent == [Ping("good")]


async def test_a_channel_retry_policy_overrides_the_notifier_default() -> None:
    channel = PingChannel(RetryableError("busy"), retry=NO_RETRY)
    result = await Notifier([channel], retry=FAST, sleep=no_sleep).notify(
        User(), Pings("x"), raise_on_failure=False
    )
    assert result.deliveries[0].attempts == 1


async def test_hooks_receive_every_event_in_order() -> None:
    received: list[events.Event] = []

    async def async_hook(event: events.Event) -> None:
        await asyncio.sleep(0)

    channel = PingChannel(RetryableError("busy"))
    notifier = Notifier([channel], retry=FAST, sleep=no_sleep, hooks=[received.append, async_hook])
    result = await notifier.notify(User(), Pings("x"))
    assert [event.name for event in received] == [
        "notification.sending",
        "notification.retrying",
        "notification.sending",
        "notification.sent",
    ]
    assert all(event.notification_id == result.id for event in received)
    sent = received[-1]
    assert isinstance(sent, events.Sent)
    assert (sent.attempt, sent.provider_id, sent.channel) == (2, "ping-1", "ping")


async def test_failed_and_skipped_events_are_emitted() -> None:
    received: list[events.Event] = []
    channel = PingChannel(PermanentError("no"), SkipDelivery("muted"))
    await Notifier([channel], hooks=[received.append]).notify(
        User(), Pings("a", "b"), raise_on_failure=False
    )
    names = {event.name for event in received}
    assert {"notification.failed", "notification.skipped"} <= names


async def test_a_failing_hook_is_logged_and_does_not_change_the_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(event: events.Event) -> None:
        raise RuntimeError("hook bug")

    with caplog.at_level(logging.ERROR, logger="goatnotify"):
        result = await Notifier([PingChannel()], hooks=[broken]).notify(User(), Pings("x"))
    assert result.ok
    assert "hook bug" in caplog.text


async def test_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="goatnotify"):
        await Notifier([PingChannel(PermanentError("no"))]).notify(
            User(), Pings("x"), raise_on_failure=False
        )
    assert "failed after 1 attempt" in caplog.text


async def test_a_notification_without_messages_sends_nothing() -> None:
    result = await Notifier([PingChannel()]).notify(User(), Pings())
    assert result.ok
    assert result.deliveries == ()


def test_notify_sync_outside_a_loop() -> None:
    channel = PingChannel()
    result = Notifier([channel]).notify_sync(User(), Pings("sync"))
    assert result.ok
    assert channel.sent == [Ping("sync")]


async def test_notify_sync_inside_a_loop_is_refused() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ConfigurationError, match="await notify"):
            Notifier([PingChannel()]).notify_sync(User(), Pings("x"))


def test_channels_keep_their_declared_name() -> None:
    channel: Channel[Ping] = PingChannel()
    assert channel.name == "ping"


async def test_retry_after_is_capped_by_the_policy() -> None:
    sleep = SleepRecorder()
    channel = PingChannel(RetryableError("come back tomorrow", retry_after=86_400))
    policy = RetryPolicy(max_attempts=2, max_delay=120.0)
    await Notifier([channel], retry=policy, sleep=sleep).notify(User(), Pings("x"))
    assert sleep.delays == [120.0]


def test_the_default_policy_caps_delays_at_five_minutes() -> None:
    assert RetryPolicy().max_delay == 300.0
