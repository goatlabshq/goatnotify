from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Protocol


class Notifiable(Protocol):
    def route_notification(self, channel: str) -> str | None: ...


class Message:
    __slots__ = ()


class Notification[R: Notifiable](ABC):
    @abstractmethod
    def messages(self, notifiable: R, /) -> Iterable[Message]: ...
