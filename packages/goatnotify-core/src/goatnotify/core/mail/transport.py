"""Email transport protocol."""

from typing import Protocol

from goatnotify.core.mail.message import EmailMessage


class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> str | None: ...
