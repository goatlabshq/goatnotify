import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from mailpit import SMTP_HOST, SMTP_PORT, fetch, raw_source, requires_mailpit

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
    PermanentError,
    SmtpTransport,
)
from goatnotify.jinja import JinjaRenderer

pytestmark = requires_mailpit


def _smtp() -> SmtpTransport:
    return SmtpTransport(SMTP_HOST, SMTP_PORT, security="none", timeout=10)


def _subject(label: str) -> str:
    return f"{label} {uuid.uuid4().hex}"


async def test_smtp_delivers_the_full_envelope_and_bodies() -> None:
    subject = _subject("Envelope")
    message_id = await _smtp().send(
        EmailMessage(
            subject=subject,
            sender=Address("noreply@goat.dev", "Équipe Goat"),
            to=(Address("ada@example.com", "Ada"),),
            cc=(Address("cc@example.com"),),
            bcc=(Address("audit@example.com"),),
            reply_to=(Address("support@goat.dev"),),
            text="Merci à vous",
            html="<p>Merci à vous</p>",
            headers={"X-Campaign": "welcome"},
        )
    )
    received = fetch(subject)
    assert received.addresses("To") == ["ada@example.com"]
    assert received.addresses("Cc") == ["cc@example.com"]
    assert received.addresses("Bcc") == ["audit@example.com"]
    assert received.addresses("ReplyTo") == ["support@goat.dev"]
    assert received.text("Text").strip() == "Merci à vous"
    assert received.text("HTML").strip() == "<p>Merci à vous</p>"
    assert f"<{received.text('MessageID')}>" == message_id
    assert "X-Campaign: welcome" in raw_source(received)


async def test_attachments_and_inline_images_arrive_intact() -> None:
    subject = _subject("Files")
    await _smtp().send(
        EmailMessage(
            subject=subject,
            sender=Address("noreply@goat.dev"),
            to=(Address("ada@example.com"),),
            text="See attached",
            html='<img src="cid:logo.png">',
            attachments=(
                Attachment("report.pdf", b"%PDF-1.7 report", "application/pdf"),
                Attachment("logo.png", b"\x89PNG logo", "image/png", inline=True),
            ),
        )
    )
    received = fetch(subject)
    assert [f["FileName"] for f in received.files("Attachments")] == ["report.pdf"]
    inline = received.files("Inline")
    assert [(f["FileName"], f["ContentID"]) for f in inline] == [("logo.png", "logo.png")]


@dataclass
class Member:
    name: str
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None


class WelcomeMail(Mailable):
    def __init__(self, member: Member, subject: str) -> None:
        self.member = member
        self.subject = subject

    def template(self) -> str | None:
        return "welcome.html"

    def text_template(self) -> str | None:
        return "welcome.txt"

    def context(self) -> Mapping[str, object]:
        return {"name": self.member.name}


@dataclass
class Welcome(Notification[Member]):
    subject: str

    def messages(self, member: Member) -> Iterable[Message]:
        yield WelcomeMail(member, self.subject)


async def test_a_notification_renders_jinja_templates_and_reaches_the_inbox(tmp_path: Path) -> None:
    (tmp_path / "welcome.html").write_text("<h1>Welcome {{ name }}</h1>", encoding="utf-8")
    (tmp_path / "welcome.txt").write_text("Welcome {{ name }}", encoding="utf-8")
    mailer = Mailer(
        _smtp(), sender="Goat <noreply@goat.dev>", renderer=JinjaRenderer.from_directory(tmp_path)
    )
    subject = _subject("Welcome")
    result = await Notifier([EmailChannel(mailer)]).notify(
        Member("<Zoé>", "zoe@example.com"), Welcome(subject)
    )
    assert result.ok
    received = fetch(subject)
    assert received.addresses("To") == ["zoe@example.com"]
    assert received.text("HTML").strip() == "<h1>Welcome &lt;Zoé&gt;</h1>"
    assert received.text("Text").strip() == "Welcome <Zoé>"


async def test_starttls_against_a_server_without_it_is_a_permanent_failure() -> None:
    transport = SmtpTransport(SMTP_HOST, SMTP_PORT, security="starttls", timeout=10)
    with pytest.raises(PermanentError, match="STARTTLS"):
        await transport.send(
            EmailMessage(
                subject=_subject("No STARTTLS"),
                sender=Address("noreply@goat.dev"),
                to=(Address("ada@example.com"),),
                text="x",
            )
        )
