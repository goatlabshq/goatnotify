from collections.abc import Iterator
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from celery import Celery
from celery.contrib.testing.worker import start_worker
from celery.signals import after_task_publish, task_postrun
from django.core import mail
from django.db import connections
from django.test import override_settings
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import FLAKY, Alert, Welcome, WelcomeWithAlert

from goatnotify import ConfigurationError, Notifiable, Notification
from goatnotify.celery import CeleryQueue
from goatnotify.celery.tasks import deliver_notification
from goatnotify.core.queue import NotificationJob
from goatnotify.django.notifier import get_notifier
from goatnotify.django.serialization import dump_model, dump_notification


def close_connections(**_: object) -> None:
    connections.close_all()


@pytest.fixture
def app() -> Iterator[Celery]:
    app = Celery("goatnotify-tests", broker="memory://", backend="cache+memory://")
    app.conf.task_default_queue = "notifications"
    # Celery's Django fixup does this in real workers; the test worker thread has no fixup.
    task_postrun.connect(close_connections)
    with start_worker(app, pool="solo", perform_ping_check=False, shutdown_timeout=10):
        yield app
    task_postrun.disconnect(close_connections)


def enqueue[R: Notifiable](queue: CeleryQueue, recipient: R, notification: Notification[R]) -> None:
    async_to_sync(queue.enqueue)(NotificationJob(get_notifier(), recipient, notification))


def test_the_worker_delivers_queued_notifications(app: Celery) -> None:
    published: list[str] = []

    def remember(*, headers: dict[str, str], **_: object) -> None:
        published.append(headers["id"])

    after_task_publish.connect(remember)
    member = Member.objects.create(email="ada@example.com")
    enqueue(CeleryQueue(app), member, Welcome(plan="pro"))
    after_task_publish.disconnect(remember)
    app.AsyncResult(published[0]).get(timeout=10)
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]


def test_routing_options_reach_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Celery("goatnotify-routing", broker="memory://")
    calls: list[tuple[str, dict[str, object]]] = []

    def record(name: str, **options: object) -> None:
        calls.append((name, options))

    monkeypatch.setattr(app, "send_task", record)
    member = Member.objects.create(email="ada@example.com")
    enqueue(CeleryQueue(app, queue="mail", priority=3), member, Welcome(plan="pro"))
    [(name, options)] = calls
    assert name == "goatnotify.deliver"
    assert (options["queue"], options["priority"]) == ("mail", 3)
    arguments = options["args"]
    assert isinstance(arguments, list)
    assert arguments[2] == options["task_id"]


def test_a_recipient_that_is_not_a_model_is_rejected_at_enqueue() -> None:
    app = Celery("goatnotify-reject", broker="memory://")
    with pytest.raises(ConfigurationError, match="CeleryQueue needs a Django model"):
        enqueue(CeleryQueue(app), object(), Welcome(plan="pro"))  # pyright: ignore[reportArgumentType]


@override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_flaky_notifier")
def test_a_retried_task_only_redelivers_what_failed() -> None:
    FLAKY.failures_left, FLAKY.sent = 1, []
    member = Member.objects.create(email="ada@example.com")
    arguments = (dump_model(member), dump_notification(WelcomeWithAlert(plan="pro")), str(uuid4()))

    assert deliver_notification.apply(args=arguments).failed()
    assert len(mail.outbox) == 1
    assert FLAKY.sent == []

    assert deliver_notification.apply(args=arguments).successful()
    assert len(mail.outbox) == 1
    assert FLAKY.sent == [Alert("ada@example.com joined")]
