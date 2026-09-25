from collections.abc import Mapping, Sequence
from types import MappingProxyType

import pytest

from goatnotify.core.errors import ConfigurationError, InvalidMessageError
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address, Attachment
from goatnotify.core.testing import MemoryTransport


class RecordingRenderer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        self.calls.append((template, dict(context)))
        return f"rendered:{template}:{context['name']}"


class Welcome(Mailable):
    subject = "Welcome"

    def __init__(self, name: str = "Ada") -> None:
        self.name = name

    def template(self) -> str | None:
        return "welcome.html"

    def text_template(self) -> str | None:
        return "welcome.txt"

    def context(self) -> Mapping[str, object]:
        return {"name": self.name}


class Raw(Mailable):
    subject = "Raw"
    to = ("ada@example.com",)
    cc = ("Boss <boss@example.com>",)
    bcc = (Address("audit@example.com"),)
    reply_to = ("support@goat.dev",)
    headers = MappingProxyType({"X-Campaign": "raw"})
    metadata = MappingProxyType({"tag": "raw"})

    def html(self) -> str | None:
        return "<p>raw</p>"

    def attachments(self) -> Sequence[Attachment]:
        return [Attachment("a.txt", b"a", "text/plain")]


async def test_raw_content_and_envelope() -> None:
    message = await Mailer(MemoryTransport(), sender="Goat <noreply@goat.dev>").render(Raw())
    assert message.subject == "Raw"
    assert message.sender == Address("noreply@goat.dev", "Goat")
    assert message.to == (Address("ada@example.com"),)
    assert message.cc == (Address("boss@example.com", "Boss"),)
    assert message.bcc == (Address("audit@example.com"),)
    assert message.reply_to == (Address("support@goat.dev"),)
    assert (message.html, message.text) == ("<p>raw</p>", None)
    assert message.attachments == (Attachment("a.txt", b"a", "text/plain"),)
    assert dict(message.headers) == {"X-Campaign": "raw"}
    assert dict(message.metadata) == {"tag": "raw"}


async def test_templates_are_rendered_with_the_context() -> None:
    renderer = RecordingRenderer()
    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev", renderer=renderer)
    message = await mailer.render(Welcome("Zoé"), to=["zoe@example.com"])
    assert message.html == "rendered:welcome.html:Zoé"
    assert message.text == "rendered:welcome.txt:Zoé"
    assert renderer.calls == [("welcome.html", {"name": "Zoé"}), ("welcome.txt", {"name": "Zoé"})]


async def test_raw_content_wins_over_templates() -> None:
    class Both(Welcome):
        def html(self) -> str | None:
            return "<p>raw</p>"

    renderer = RecordingRenderer()
    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev", renderer=renderer)
    message = await mailer.render(Both(), to=["a@b.c"])
    assert message.html == "<p>raw</p>"
    assert [template for template, _ in renderer.calls] == ["welcome.txt"]


async def test_a_template_without_renderer_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="TemplateRenderer"):
        await Mailer(MemoryTransport(), sender="noreply@goat.dev").render(Welcome(), to=["a@b.c"])


async def test_a_mailable_needs_a_subject_and_a_body() -> None:
    class NoSubject(Raw):
        subject = ""

    class NoBody(Mailable):
        subject = "Empty"

    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev")
    with pytest.raises(InvalidMessageError, match="subject"):
        await mailer.render(NoSubject())
    with pytest.raises(InvalidMessageError, match="body"):
        await mailer.render(NoBody(), to=["a@b.c"])


async def test_explicit_recipients_and_sender_override_defaults() -> None:
    class Custom(Raw):
        sender = "Billing <billing@goat.dev>"

    message = await Mailer(MemoryTransport(), sender="noreply@goat.dev").render(
        Custom(), to=["other@example.com"]
    )
    assert message.sender == Address("billing@goat.dev", "Billing")
    assert message.to == (Address("other@example.com"),)


async def test_send_hands_the_rendered_message_to_the_transport() -> None:
    transport = MemoryTransport()
    provider_id = await Mailer(transport, sender="noreply@goat.dev").send(Raw())
    assert provider_id == "memory-1"
    assert [m.subject for m in transport.outbox] == ["Raw"]
