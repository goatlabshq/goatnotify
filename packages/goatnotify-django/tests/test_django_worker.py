import logging
from collections.abc import Iterator

import pytest
from asgiref.sync import async_to_sync
from django.core import mail
from django.core.management import call_command
from django.tasks import TaskResult, TaskResultStatus
from django.tasks.signals import task_enqueued
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import Welcome

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
