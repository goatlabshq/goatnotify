from collections.abc import Iterable

import pytest
from core_support import User

from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.errors import RetryableError, SkipDelivery
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.testing import MemoryTransport, no_sleep


class Hello(Mailable):
    subject = "Hello"

    def text(self) -> str | None:
        return "Hello!"


class Greeting(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Hello()


def _channel() -> tuple[EmailChannel, MemoryTransport]:
    transport = MemoryTransport()
    return EmailChannel(Mailer(transport, sender="noreply@goat.dev")), transport


async def test_the_email_route_is_used_when_the_mailable_has_no_recipient() -> None:
    channel, transport = _channel()
    await channel.send(User(email="ada@example.com"), Hello())
    assert transport.outbox[0].to == (Address("ada@example.com"),)


async def test_explicit_mailable_recipients_win_over_the_route() -> None:
    class Direct(Hello):
        to = ("boss@example.com",)

    channel, transport = _channel()
    await channel.send(User(email="ada@example.com"), Direct())
    assert transport.outbox[0].to == (Address("boss@example.com"),)


async def test_a_recipient_without_email_route_is_skipped() -> None:
    channel, _ = _channel()
    with pytest.raises(SkipDelivery, match="no email route"):
        await channel.send(User(email=None), Hello())


async def test_end_to_end_with_retry() -> None:
    channel, transport = _channel()
    transport.fail_next(RetryableError("421 try later"))
    result = await Notifier([channel], sleep=no_sleep).notify(User(), Greeting())
    (delivery,) = result.deliveries
    assert (delivery.status, delivery.attempts, delivery.provider_id) == (
        DeliveryStatus.SENT,
        2,
        "memory-1",
    )
    assert len(transport.outbox) == 1
