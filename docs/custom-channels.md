# Custom channels

A channel delivers one message type. Writing one takes three steps: a message class, a channel
class, and registering the channel on the notifier. GoatNotify itself is never modified.

## 1. The message

A message is a frozen dataclass deriving from `Message`. Its type is what routes it:

```python
@dataclass(frozen=True, slots=True)
class DiscordMessage(Message):
    content: str
    username: str | None = None
```

## 2. The channel

Derive from `Channel[YourMessage]`, set `name` and `message_type`, and implement `send()`.

- Get the address from `notifiable.route_notification(self.name)`, and raise `SkipDelivery` when
  there is none.
- Raise `RetryableError` for transient failures (network errors, 429, 5xx) and `PermanentError`
  for the rest; any other exception fails the delivery without retry.
- Return a provider identifier if the service gives one, `None` otherwise.
- Keep secrets out of error messages: Discord webhook URLs embed a token.

Depending on the `HttpTransport` protocol instead of an HTTP library keeps the channel testable
and dependency-free.

## Complete example

`examples/discord_channel.py`:

```python
"""A custom channel: Discord webhooks, built on the HttpTransport abstraction."""

import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    Channel,
    HttpRequest,
    HttpTransport,
    Message,
    Notifiable,
    Notification,
    Notifier,
    PermanentError,
    RetryableError,
    SkipDelivery,
    UrllibTransport,
)
from goatnotify.core.http import require_http_url
from goatnotify.core.testing import MemoryHttpTransport


@dataclass(frozen=True, slots=True)
class DiscordMessage(Message):
    content: str
    username: str | None = None


class DiscordChannel(Channel[DiscordMessage]):
    name = "discord"
    message_type = DiscordMessage

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self._transport = transport or UrllibTransport()

    async def send(self, notifiable: Notifiable, message: DiscordMessage) -> str | None:
        url = notifiable.route_notification(self.name)
        if url is None:
            raise SkipDelivery("no Discord webhook")
        require_http_url(url)
        payload = {"content": message.content}
        if message.username is not None:
            payload["username"] = message.username
        request = HttpRequest(
            "POST", url, {"Content-Type": "application/json"}, json.dumps(payload).encode(), 10.0
        )
        try:
            response = await self._transport.send(request)
        except OSError as error:
            raise RetryableError(f"Discord is unreachable: {type(error).__name__}") from error
        if response.status == 429 or response.status >= 500:
            raise RetryableError(f"Discord answered {response.status}")
        if response.status >= 400:
            raise PermanentError(f"Discord answered {response.status}")
        return None


@dataclass
class Team:
    discord_webhook: str

    def route_notification(self, channel: str) -> str | None:
        return self.discord_webhook if channel == "discord" else None


class Deployed(Notification[Team]):
    def messages(self, notifiable: Team) -> Iterable[Message]:
        yield DiscordMessage("Version 1.2.0 is live", username="GoatNotify")


async def main() -> None:
    http = MemoryHttpTransport()
    notifier = Notifier([DiscordChannel(http)])
    await notifier.notify(Team("https://discord.com/api/webhooks/1/token"), Deployed())
    print(f"discord requests={len(http.requests)}")


if __name__ == "__main__":
    asyncio.run(main())
```

Register it next to the built-in channels:

```python
notifier = Notifier([EmailChannel(mailer), DiscordChannel()])
```

## Testing it

```python
async def test_rate_limits_are_retried() -> None:
    http = MemoryHttpTransport()
    http.respond(HttpResponse(429, {}, b""), HttpResponse(204, {}, b""))
    notifier = Notifier([DiscordChannel(http)], sleep=no_sleep)
    result = await notifier.notify(Team("https://discord.com/api/webhooks/1/token"), Deployed())
    assert result.deliveries[0].attempts == 2
```
