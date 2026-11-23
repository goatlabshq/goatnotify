from collections.abc import Iterator
from uuid import uuid4

import dramatiq
import pytest
from asgiref.sync import async_to_sync
from django.core import mail
from django.db import connections
from django.test import override_settings
from dramatiq import Worker
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import Middleware
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import FLAKY, Alert, Welcome, WelcomeWithAlert

from goatnotify import ConfigurationError, Notifiable, Notification
from goatnotify.core.queue import NotificationJob
from goatnotify.django.notifier import get_notifier
from goatnotify.django.serialization import dump_model, dump_notification
from goatnotify.dramatiq import DramatiqQueue


# Stands in for django_dramatiq's DbConnectionsMiddleware, which real workers run.
class CloseConnections(Middleware):
    def after_process_message(self, broker: object, message: object, **_: object) -> None:
        connections.close_all()


@pytest.fixture
def broker() -> Iterator[StubBroker]:
    broker = StubBroker(middleware=[CloseConnections()])
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)
    from goatnotify.dramatiq import tasks

    broker.declare_actor(tasks.deliver_notification)  # pyright: ignore[reportUnknownMemberType]
    yield broker
    broker.flush_all()
    broker.close()


def enqueue[R: Notifiable](
    queue: DramatiqQueue, recipient: R, notification: Notification[R]
) -> None:
    async_to_sync(queue.enqueue)(NotificationJob(get_notifier(), recipient, notification))


def test_the_worker_delivers_queued_notifications(broker: StubBroker) -> None:
    member = Member.objects.create(email="ada@example.com")
    enqueue(DramatiqQueue(queue_name="mail"), member, Welcome(plan="pro"))
    assert "mail" in broker.get_declared_queues()
    worker = Worker(broker, worker_timeout=100)
    worker.start()
    broker.join("mail", fail_fast=True)
    worker.join()
    worker.stop()
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]


def test_the_message_id_is_the_job_id(broker: StubBroker) -> None:
    member = Member.objects.create(email="ada@example.com")
    enqueue(DramatiqQueue(max_retries=2), member, Welcome(plan="pro"))
    [message] = broker.queues["default"].queue
    decoded = dramatiq.Message.decode(message)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert decoded.message_id == decoded.args[2]
    assert decoded.options["max_retries"] == 2


def test_an_unregistered_actor_is_a_configuration_error() -> None:
    dramatiq.set_broker(StubBroker())
    member = Member.objects.create(email="ada@example.com")
    with pytest.raises(ConfigurationError, match="INSTALLED_APPS"):
        enqueue(DramatiqQueue(), member, Welcome(plan="pro"))


@override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_flaky_notifier")
def test_a_retried_message_only_redelivers_what_failed(broker: StubBroker) -> None:
    from goatnotify.dramatiq.tasks import deliver_notification

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
