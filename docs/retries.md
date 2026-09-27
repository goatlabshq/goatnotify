# Retries and failures

GoatNotify never swallows a failure: every delivery ends in a `DeliveryResult`, failures are
logged on the `goatnotify` logger, and `notify()` raises unless you opt out.

## Errors raised by channels and transports

```text
NotificationError
├── ConfigurationError            wiring problem, never retried
└── DeliveryError
    ├── RetryableError            retried (retry_after= overrides the delay)
    ├── PermanentError            fails immediately
    │   └── InvalidMessageError
    └── SkipDelivery(reason)      reported as skipped
```

Any other exception fails the delivery immediately, without retry, and is kept in
`DeliveryResult.error`. `asyncio.CancelledError` always propagates.

## Retry policy

```python
from goatnotify import ExponentialBackoff, NO_RETRY, Notifier, RetryPolicy

notifier = Notifier(
    channels,
    retry=RetryPolicy(
        max_attempts=5,
        backoff=ExponentialBackoff(initial=1.0, multiplier=2.0, maximum=60.0, jitter=True),
    ),
)
```

The delay after attempt `n` is `min(maximum, initial * multiplier ** (n - 1))`. With `jitter`
(the default) the actual delay is drawn uniformly between 0 and that value ("full jitter"), which
spreads retries from many workers.

Every delay, including a channel's `retry_after`, is capped by `RetryPolicy.max_delay` (300 seconds
by default), so no delivery waits for hours in memory.

A channel's own `retry=` overrides the notifier's policy:

```python
WebhookChannel(retry=RetryPolicy(max_attempts=8))
EmailChannel(mailer, retry=NO_RETRY)
```

Retries happen in-process with `asyncio.sleep`. For retries that must survive a restart, send
through a durable [queue](queues.md).

## DeliveryFailed

When at least one delivery failed, `notify()` raises `DeliveryFailed` after **all** deliveries
have finished. It is an `ExceptionGroup` carrying every error and the full result:

```python
try:
    await notifier.notify(user, InvoicePaid(invoice))
except DeliveryFailed as failure:
    for delivery in failure.result.failed:
        log.error("%s failed after %d attempts", delivery.channel, delivery.attempts)
```

`except*` works too:

```python
try:
    await notifier.notify(user, InvoicePaid(invoice))
except* PermanentError as group:
    disable_addresses(group.exceptions)
```

To inspect the result instead, pass `raise_on_failure=False`:

```python
result = await notifier.notify(user, InvoicePaid(invoice), raise_on_failure=False)
if not result.ok:
    ...
```

## Hooks

Hooks observe every step of every delivery. They receive typed events and may be sync or async:

```python
from goatnotify import events


async def record(event: events.Event) -> None:
    match event:
        case events.Sent(channel=channel, provider_id=provider_id):
            metrics.increment("notifications.sent", tags={"channel": channel})
        case events.Failed(error=error):
            sentry_sdk.capture_exception(error)
        case _:
            pass


notifier = Notifier(channels, hooks=[record])
```

| Event | `name` | Extra fields |
|---|---|---|
| `Sending` | `notification.sending` | |
| `Retrying` | `notification.retrying` | `delay`, `error` |
| `Sent` | `notification.sent` | `provider_id` |
| `Failed` | `notification.failed` | `error` |
| `Skipped` | `notification.skipped` | `reason` |

Every event also carries `notification_id`, `notification`, `notifiable`, `channel`, `message`
and `attempt`. A hook that raises is logged and never changes the delivery outcome.
