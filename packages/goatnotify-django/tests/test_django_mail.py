from collections.abc import Iterable, Mapping

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from goatnotify_testapp.models import Member

from goatnotify import (
    Address,
    Attachment,
    EmailChannel,
    EmailMessage,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
    RetryableError,
)
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.templates import DjangoTemplateRenderer

MESSAGE = EmailMessage(
    subject="Hello",
    sender=Address("noreply@goat.dev", "Goat"),
    to=(Address("ada@example.com", "Ada"),),
    cc=(Address("cc@example.com"),),
    bcc=(Address("audit@example.com"),),
    reply_to=(Address("support@goat.dev"),),
    text="Hi",
    html="<p>Hi</p>",
    attachments=(Attachment("a.txt", b"a", "text/plain"),),
    headers={"X-Campaign": "hello"},
)


async def test_the_message_goes_through_the_django_backend() -> None:
    message_id = await DjangoEmailTransport().send(MESSAGE)
    (sent,) = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.subject == "Hello"
    assert sent.from_email == "Goat <noreply@goat.dev>"
    assert (sent.to, sent.cc, sent.bcc, sent.reply_to) == (
        ["Ada <ada@example.com>"],
        ["cc@example.com"],
        ["audit@example.com"],
        ["support@goat.dev"],
    )
    assert sent.body == "Hi"
    assert sent.alternatives[0][0] == "<p>Hi</p>"
    assert sent.attachments[0].filename == "a.txt"
    assert sent.extra_headers["X-Campaign"] == "hello"
    assert sent.extra_headers["Message-ID"] == message_id


async def test_html_only_messages_use_an_html_body() -> None:
    await DjangoEmailTransport().send(
        EmailMessage(
            subject="x", sender=Address("a@goat.dev"), to=(Address("b@c.d"),), html="<b>x</b>"
        )
    )
    assert mail.outbox[0].content_subtype == "html"


async def test_backend_errors_are_classified() -> None:
    with pytest.raises(RetryableError):
        await DjangoEmailTransport(mailer="broken").send(MESSAGE)


async def test_django_templates_render_mailables() -> None:
    class Welcome(Mailable):
        subject = "Welcome"

        def template(self) -> str | None:
            return "emails/welcome.html"

        def text_template(self) -> str | None:
            return "emails/welcome.txt"

        def context(self) -> Mapping[str, object]:
            return {"name": "Zoé"}

    class Joined(Notification[Member]):
        def messages(self, notifiable: Member) -> Iterable[Message]:
            yield Welcome()

    member = await Member.objects.acreate(email="zoe@example.com")
    mailer = Mailer(
        DjangoEmailTransport(), sender="noreply@goat.dev", renderer=DjangoTemplateRenderer()
    )
    await Notifier([EmailChannel(mailer)]).notify(member, Joined())
    (sent,) = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert (sent.to, sent.body, sent.alternatives[0][0]) == (
        ["zoe@example.com"],
        "Welcome Zoé",
        "<p>Welcome Zoé</p>",
    )


async def test_inline_images_keep_their_content_id() -> None:
    await DjangoEmailTransport().send(
        EmailMessage(
            subject="x",
            sender=Address("a@goat.dev"),
            to=(Address("b@c.d"),),
            text="Hi",
            html='<img src="cid:logo.png">',
            attachments=(Attachment("logo.png", b"\x89PNG", "image/png", inline=True),),
        )
    )
    raw = mail.outbox[0].message().as_string()
    assert "multipart/related" in raw
    assert "Content-ID: <logo.png>" in raw
    assert 'Content-Disposition: inline; filename="logo.png"' in raw
