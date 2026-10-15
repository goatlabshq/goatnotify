import uuid
from collections.abc import Iterable, Mapping

from goatnotify_testapp.models import Member
from mailpit import fetch, requires_mailpit

from goatnotify import Attachment, EmailChannel, Mailable, Mailer, Message, Notification, Notifier
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.templates import DjangoTemplateRenderer

pytestmark = requires_mailpit


class WelcomeMail(Mailable):
    def __init__(self, subject: str) -> None:
        self.subject = subject

    def template(self) -> str | None:
        return "emails/welcome.html"

    def text_template(self) -> str | None:
        return "emails/welcome.txt"

    def context(self) -> Mapping[str, object]:
        return {"name": "Zoé"}

    def attachments(self) -> list[Attachment]:
        return [Attachment("logo.png", b"\x89PNG logo", "image/png", inline=True)]


class Joined(Notification[Member]):
    def __init__(self, subject: str) -> None:
        self.subject = subject

    def messages(self, notifiable: Member) -> Iterable[Message]:
        yield WelcomeMail(self.subject)


async def test_the_django_smtp_backend_delivers_to_mailpit() -> None:
    member = await Member.objects.acreate(email="zoe@example.com")
    mailer = Mailer(
        DjangoEmailTransport(mailer="mailpit"),
        sender="Goat <noreply@goat.dev>",
        renderer=DjangoTemplateRenderer(),
    )
    subject = f"Django {uuid.uuid4().hex}"
    result = await Notifier([EmailChannel(mailer)]).notify(member, Joined(subject))
    received = fetch(subject)
    assert received.addresses("To") == ["zoe@example.com"]
    assert received.text("Text").strip() == "Welcome Zoé"
    assert received.text("HTML").strip() == "<p>Welcome Zoé</p>"
    assert [(f["FileName"], f["ContentID"]) for f in received.files("Inline")] == [
        ("logo.png", "logo.png")
    ]
    assert result.deliveries[0].provider_id == f"<{received.text('MessageID')}>"
