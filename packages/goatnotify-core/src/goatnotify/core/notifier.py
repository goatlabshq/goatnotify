"""The notifier routes messages to channels, retries, fires hooks and reports results."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final, TypedDict
from uuid import UUID, uuid4

from goatnotify.core import events
from goatnotify.core.channel import Channel
from goatnotify.core.errors import ConfigurationError, RetryableError, SkipDelivery
from goatnotify.core.events import Event, Hook
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.queue import NotificationJob, Queue
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult
from goatnotify.core.retry import RetryPolicy

logger: Final = logging.getLogger("goatnotify")

type Sleep = Callable[[float], Awaitable[None]]


class _Scope(TypedDict):
    notification_id: UUID
    notification: Notification[Any]
    notifiable: Notifiable
    channel: str
    message: Message


class Notifier:
    def __init__(
        self,
        channels: Iterable[Channel[Any]],
        *,
        retry: RetryPolicy | None = None,
        hooks: Iterable[Hook] = (),
        queue: Queue | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._routes: dict[type[Message], Channel[Any]] = {}
        for channel in channels:
            existing = self._routes.get(channel.message_type)
            if existing is not None:
                raise ConfigurationError(
                    f"Channels {existing.name!r} and {channel.name!r} both handle "
                    f"{channel.message_type.__qualname__}"
                )
            self._routes[channel.message_type] = channel
        self._retry = retry or RetryPolicy()
        self._hooks = tuple(hooks)
        self._queue = queue
        self._sleep = sleep

    async def notify[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult:
        routed = [
            (self._channel_for(message), message) for message in notification.messages(notifiable)
        ]
        notification_id = uuid4()
        deliveries = await asyncio.gather(
            *(
                self._deliver(
                    _Scope(
                        notification_id=notification_id,
                        notification=notification,
                        notifiable=notifiable,
                        channel=channel.name,
                        message=message,
                    ),
                    channel,
                )
                for channel, message in routed
            )
        )
        result = NotificationResult(
            id=notification_id, notification=notification, deliveries=tuple(deliveries)
        )
        if raise_on_failure:
            result.raise_for_failures()
        return result

    @property
    def queue(self) -> Queue | None:
        return self._queue

    async def enqueue[R: Notifiable](self, notifiable: R, notification: Notification[R]) -> None:
        if self._queue is None:
            raise ConfigurationError("No queue configured: pass queue= to Notifier")
        await self._queue.enqueue(NotificationJob(self, notifiable, notification))

    def notify_sync[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.notify(notifiable, notification, raise_on_failure=raise_on_failure)
            )
        raise ConfigurationError("notify_sync() cannot run inside an event loop: await notify()")

    def _channel_for(self, message: Message) -> Channel[Any]:
        for cls in type(message).__mro__:
            channel = self._routes.get(cls)
            if channel is not None:
                return channel
        raise ConfigurationError(f"No channel handles {type(message).__qualname__}")

    async def _deliver(self, scope: _Scope, channel: Channel[Any]) -> DeliveryResult:
        policy = channel.retry or self._retry
        message = scope["message"]
        attempt = 1
        while True:
            await self._emit(events.Sending(**scope, attempt=attempt))
            try:
                provider_id = await channel.send(scope["notifiable"], message)
            except SkipDelivery as skip:
                await self._emit(events.Skipped(**scope, attempt=attempt, reason=skip.reason))
                return DeliveryResult(
                    channel=channel.name,
                    message=message,
                    status=DeliveryStatus.SKIPPED,
                    attempts=attempt,
                    reason=skip.reason,
                )
            except RetryableError as error:
                if attempt >= policy.max_attempts:
                    return await self._failed(scope, attempt, error)
                delay = (
                    error.retry_after
                    if error.retry_after is not None
                    else policy.backoff.delay(attempt)
                )
                await self._emit(
                    events.Retrying(**scope, attempt=attempt, delay=delay, error=error)
                )
                await self._sleep(delay)
                attempt += 1
            except Exception as error:
                return await self._failed(scope, attempt, error)
            else:
                await self._emit(events.Sent(**scope, attempt=attempt, provider_id=provider_id))
                return DeliveryResult(
                    channel=channel.name,
                    message=message,
                    status=DeliveryStatus.SENT,
                    attempts=attempt,
                    provider_id=provider_id,
                )

    async def _failed(self, scope: _Scope, attempt: int, error: Exception) -> DeliveryResult:
        logger.warning(
            "Delivery of %s through %r failed after %d attempt(s): %r",
            type(scope["message"]).__qualname__,
            scope["channel"],
            attempt,
            error,
        )
        await self._emit(events.Failed(**scope, attempt=attempt, error=error))
        return DeliveryResult(
            channel=scope["channel"],
            message=scope["message"],
            status=DeliveryStatus.FAILED,
            attempts=attempt,
            error=error,
        )

    async def _emit(self, event: Event) -> None:
        for hook in self._hooks:
            try:
                outcome = hook(event)
                if outcome is not None:
                    await outcome
            except Exception:
                logger.exception("Hook %r failed while handling %s", hook, event.name)
