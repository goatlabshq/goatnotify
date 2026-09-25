"""Base class of delivery channels."""

from abc import ABC, abstractmethod

from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy


class Channel[M: Message](ABC):
    name: str
    message_type: type[M]
    retry: RetryPolicy | None = None

    @abstractmethod
    async def send(self, notifiable: Notifiable, message: M) -> str | None: ...
