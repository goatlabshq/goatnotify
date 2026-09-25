"""In-memory fakes for testing code that sends notifications."""

from collections import deque

from goatnotify.core.mail.message import EmailMessage


async def no_sleep(delay: float) -> None:
    """Drop-in for asyncio.sleep that makes retries instantaneous."""


class MemoryTransport:
    """EmailTransport keeping sent messages in `outbox`."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []
        self._failures: deque[Exception] = deque()

    def fail_next(self, *errors: Exception) -> None:
        self._failures.extend(errors)

    async def send(self, message: EmailMessage) -> str | None:
        if self._failures:
            raise self._failures.popleft()
        self.outbox.append(message)
        return f"memory-{len(self.outbox)}"
