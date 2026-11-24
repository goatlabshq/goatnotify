from uuid import uuid4

import fakeredis
import pytest
from asgiref.sync import async_to_sync
from django.core import mail
from django.test import override_settings
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import FLAKY, Alert, Welcome, WelcomeWithAlert
from redis import Redis
from rq import Queue, Retry, SimpleWorker

from goatnotify import ConfigurationError, Notifiable, Notification
from goatnotify.core.queue import NotificationJob
from goatnotify.django.notifier import get_notifier
from goatnotify.django.serialization import dump_model, dump_notification
from goatnotify.rq import RQQueue
from goatnotify.rq.tasks import deliver_notification


@pytest.fixture
def redis() -> Redis:
    return fakeredis.FakeRedis()


def enqueue[R: Notifiable](queue: RQQueue, recipient: R, notification: Notification[R]) -> None:
    async_to_sync(queue.enqueue)(NotificationJob(get_notifier(), recipient, notification))


def test_the_worker_delivers_queued_notifications(redis: Redis) -> None:
    member = Member.objects.create(email="ada@example.com")
    enqueue(RQQueue(redis, queue="mail"), member, Welcome(plan="pro"))
    queue = Queue("mail", connection=redis)
    SimpleWorker([queue], connection=redis).work(burst=True)
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]


def test_the_rq_job_id_is_the_receipt_job_id(redis: Redis) -> None:
    member = Member.objects.create(email="ada@example.com")
    enqueue(RQQueue(redis, retry=Retry(max=3)), member, Welcome(plan="pro"))
    [job] = Queue("default", connection=redis).get_jobs()
    assert job.func_name == "goatnotify.rq.tasks.deliver_notification"
    assert job.args[2] == job.id  # pyright: ignore[reportUnknownMemberType]
    assert job.retries_left == 3


def test_a_recipient_that_is_not_a_model_is_rejected_at_enqueue(redis: Redis) -> None:
    with pytest.raises(ConfigurationError, match="RQQueue needs a Django model"):
        enqueue(RQQueue(redis), object(), Welcome(plan="pro"))  # pyright: ignore[reportArgumentType]


@override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_flaky_notifier")
def test_a_retried_job_only_redelivers_what_failed() -> None:
    FLAKY.failures_left, FLAKY.sent = 1, []
    member = Member.objects.create(email="ada@example.com")
    arguments = (dump_model(member), dump_notification(WelcomeWithAlert(plan="pro")), str(uuid4()))

    with pytest.raises(ExceptionGroup):
        deliver_notification(*arguments)
    assert len(mail.outbox) == 1
    assert FLAKY.sent == []

    deliver_notification(*arguments)
    assert len(mail.outbox) == 1
    assert FLAKY.sent == [Alert("ada@example.com joined")]
