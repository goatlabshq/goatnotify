import asyncio
from collections.abc import Iterable
from importlib.resources import files

from goatnotify import DatabaseChannel, DatabaseMessage, Message, Notifiable, Notification, Notifier
from goatnotify.core.testing import MemoryStore

PACKAGES = ("core", "jinja", "django", "fastapi")


class Recipient:
    def route_notification(self, channel: str) -> str | None:
        return None


class Ping(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield DatabaseMessage(kind="ping", data={"ok": True})


store = MemoryStore()
result = asyncio.run(Notifier([DatabaseChannel(store)]).notify(Recipient(), Ping()))

assert result.ok, result
assert store.records[0][1].kind == "ping"
assert files("goatnotify").joinpath("py.typed").is_file()
for package in PACKAGES:
    assert files(f"goatnotify.{package}").joinpath("py.typed").is_file(), package
