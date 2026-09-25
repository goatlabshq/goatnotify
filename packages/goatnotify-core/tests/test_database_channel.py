from collections.abc import Iterable
from datetime import UTC, datetime

from core_support import User

from goatnotify.core.channels.database import DatabaseChannel, DatabaseMessage
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.testing import MemoryStore

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


class Invoice(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield DatabaseMessage(kind="invoice.paid", data={"amount": 42, "lines": ["a", "b"]})


async def test_the_message_is_stored_for_the_notifiable() -> None:
    store = MemoryStore()
    user = User(email=None)
    notifier = Notifier([DatabaseChannel(store, clock=lambda: NOW)])
    result = await notifier.notify(user, Invoice())
    (record,) = store.for_notifiable(user)
    assert (record.kind, dict(record.data), record.created_at) == (
        "invoice.paid",
        {"amount": 42, "lines": ["a", "b"]},
        NOW,
    )
    assert result.deliveries[0].provider_id == str(record.id)


async def test_records_are_kept_per_notifiable() -> None:
    store = MemoryStore()
    ada, bob = User(), User()
    notifier = Notifier([DatabaseChannel(store)])
    await notifier.notify(ada, Invoice())
    await notifier.notify(ada, Invoice())
    await notifier.notify(bob, Invoice())
    assert len(store.for_notifiable(ada)) == 2
    assert len(store.for_notifiable(bob)) == 1
    assert store.for_notifiable(ada)[0].created_at.tzinfo is UTC
