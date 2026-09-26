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
