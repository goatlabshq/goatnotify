from collections.abc import Iterable

import pytest
from django.core.management import call_command
from goatnotify_testapp.models import Member

from goatnotify import (
    ConfigurationError,
    DatabaseChannel,
    DatabaseMessage,
    Message,
    Notifiable,
    Notification,
    Notifier,
)
from goatnotify.django.models import NotificationRecord
from goatnotify.django.store import DjangoNotificationStore


class Paid(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield DatabaseMessage(kind="invoice.paid", data={"amount": 42})


class Plain:
    def route_notification(self, channel: str) -> str | None:
        return None


async def test_records_are_stored_for_the_recipient() -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    bob = await Member.objects.acreate(email="bob@example.com")
    notifier = Notifier([DatabaseChannel(DjangoNotificationStore())])
    result = await notifier.notify(ada, Paid())
    await notifier.notify(bob, Paid())
    records = [record async for record in NotificationRecord.objects.for_recipient(ada)]
    assert len(records) == 1
    assert (records[0].kind, records[0].data, str(records[0].id)) == (
        "invoice.paid",
        {"amount": 42},
        result.deliveries[0].provider_id,
    )


def test_unread_and_mark_as_read() -> None:
    ada = Member.objects.create(email="ada@example.com")
    Notifier([DatabaseChannel(DjangoNotificationStore())]).notify_sync(ada, Paid())
    assert NotificationRecord.objects.for_recipient(ada).unread().count() == 1
    assert NotificationRecord.objects.for_recipient(ada).mark_as_read() == 1
    assert NotificationRecord.objects.for_recipient(ada).unread().count() == 0


async def test_a_non_model_recipient_is_a_configuration_error() -> None:
    notifier = Notifier([DatabaseChannel(DjangoNotificationStore())])
    result = await notifier.notify(Plain(), Paid(), raise_on_failure=False)
    assert isinstance(result.deliveries[0].error, ConfigurationError)


def test_migrations_are_up_to_date() -> None:
    try:
        call_command("makemigrations", "goatnotify", check=True, dry_run=True, verbosity=0)
    except SystemExit as exit_:
        pytest.fail(f"Missing migration for goatnotify (exit code {exit_.code})")
