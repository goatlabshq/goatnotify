from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from django.core import mail
from django.test import override_settings
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import MEMORY, Welcome

from goatnotify import ConfigurationError, Message, Notification
from goatnotify.django.models import NotificationRecord
from goatnotify.django.notifier import get_notifier
from goatnotify.django.serialization import (
    dump_model,
    dump_notification,
    load_notifiable,
    load_notification,
)


class NotADataclass(Notification[Member]):
    def messages(self, notifiable: Member) -> Iterable[Message]:
        return []


@dataclass
class HasDatetime(Notification[Member]):
    when: datetime

    def messages(self, notifiable: Member) -> Iterable[Message]:
        return []


class Plain:
    def route_notification(self, channel: str) -> str | None:
        return None


def test_models_and_notifications_round_trip() -> None:
    ada = Member.objects.create(email="ada@example.com")
    bob = Member.objects.create(email="bob@example.com")
    assert load_notifiable(dump_model(ada)) == ada
    restored = load_notification(dump_notification(Welcome(plan="pro", referrer=bob)))
    assert restored == Welcome(plan="pro", referrer=bob)


async def test_enqueue_runs_through_django_tasks() -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    bob = await Member.objects.acreate(email="bob@example.com")
    await get_notifier().enqueue(ada, Welcome(plan="pro", referrer=bob))
    (sent,) = mail.outbox
    assert (sent.to, sent.body) == (["ada@example.com"], "Welcome on the pro plan")
    record = await NotificationRecord.objects.aget()
    assert record.data == {"plan": "pro", "referrer": "bob@example.com"}


@pytest.mark.parametrize(
    ("notification", "match"),
    [
        (NotADataclass(), "dataclass"),
        (HasDatetime(when=datetime(2026, 1, 1, tzinfo=UTC)), "JSON"),
    ],
)
async def test_unserializable_notifications_fail_at_enqueue(
    notification: Notification[Member], match: str
) -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    with pytest.raises(ConfigurationError, match=match):
        await get_notifier().enqueue(ada, notification)
    assert mail.outbox == []


async def test_unsaved_and_non_model_recipients_fail_at_enqueue() -> None:
    with pytest.raises(ConfigurationError, match="saved"):
        await get_notifier().enqueue(Member(email="x@example.com"), Welcome(plan="pro"))
    with pytest.raises(ConfigurationError, match="model instance"):
        await get_notifier().enqueue(Plain(), Welcome(plan="pro"))  # pyright: ignore[reportArgumentType]


def test_a_custom_notifier_factory_is_used() -> None:
    with override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_notifier"):
        ada = Member.objects.create(email="ada@example.com")
        get_notifier().notify_sync(ada, Welcome(plan="team"))
        assert [m.subject for m in MEMORY.outbox][-1] == "Welcome"
    assert get_notifier() is not None


def test_a_factory_must_return_a_notifier() -> None:
    with (
        override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_nothing"),
        pytest.raises(ConfigurationError, match="Notifier"),
    ):
        get_notifier()
