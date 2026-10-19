import logging
from collections.abc import Iterator

import pytest
from asgiref.sync import async_to_sync
from django.core import mail
from django.core.management import call_command
from django.tasks import TaskResult, TaskResultStatus
from django.tasks.signals import task_enqueued
from django.test import override_settings
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import FLAKY, Alert, Welcome, WelcomeWithAlert

from goatnotify import Notifiable, Notification
from goatnotify.core.queue import NotificationJob
from goatnotify.django.notifier import get_notifier
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify.django.tasks import deliver_notification

ENQUEUED: list[str] = []


def _remember(*, task_result: TaskResult[..., object], **_: object) -> None:
    ENQUEUED.append(task_result.id)


@pytest.fixture(autouse=True)
def track_enqueued_tasks() -> Iterator[None]:
    ENQUEUED.clear()
    task_enqueued.connect(_remember)
    yield
    task_enqueued.disconnect(_remember)


def enqueue[R: Notifiable](recipient: R, notification: Notification[R]) -> None:
    job = NotificationJob(get_notifier(), recipient, notification)
    async_to_sync(DjangoTasksQueue(backend="database").enqueue)(job)


def run_worker() -> None:
    call_command("db_worker", "--batch", "--backend", "database", "--no-startup-delay", verbosity=0)


def statuses() -> list[TaskResultStatus]:
    return [deliver_notification.using(backend="database").get_result(i).status for i in ENQUEUED]


def test_the_worker_delivers_queued_notifications() -> None:
    member = Member.objects.create(email="ada@example.com")
    enqueue(member, Welcome(plan="pro"))
    assert mail.outbox == []
    run_worker()
    assert statuses() == [TaskResultStatus.SUCCESSFUL]
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]


def test_a_recipient_deleted_before_the_worker_runs_is_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    member = Member.objects.create(email="gone@example.com")
    enqueue(member, Welcome(plan="pro"))
    member.delete()
    with caplog.at_level(logging.WARNING, logger="goatnotify"):
        run_worker()
    assert statuses() == [TaskResultStatus.SUCCESSFUL]
    assert mail.outbox == []
    assert "no longer exists" in caplog.text


def retry(result_id: str) -> None:
    failed = deliver_notification.using(backend="database").get_result(result_id)
    deliver_notification.using(backend="database").enqueue(*failed.args, **failed.kwargs)


@override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_flaky_notifier")
def test_retrying_a_task_only_redelivers_what_failed() -> None:
    FLAKY.failures_left, FLAKY.sent = 1, []
    member = Member.objects.create(email="ada@example.com")
    enqueue(member, WelcomeWithAlert(plan="pro"))
    run_worker()
    assert statuses() == [TaskResultStatus.FAILED]
    assert len(mail.outbox) == 1
    assert FLAKY.sent == []

    retry(ENQUEUED[0])
    run_worker()
    assert statuses() == [TaskResultStatus.FAILED, TaskResultStatus.SUCCESSFUL]
    assert len(mail.outbox) == 1
    assert FLAKY.sent == [Alert("ada@example.com joined")]

    retry(ENQUEUED[1])
    run_worker()
    assert len(mail.outbox) == 1
    assert len(FLAKY.sent) == 1
