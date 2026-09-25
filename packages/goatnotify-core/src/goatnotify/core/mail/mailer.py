"""Mailer: renders mailables and hands them to a transport."""

from collections.abc import Iterable, Mapping, Sequence

from goatnotify.core.errors import ConfigurationError, InvalidMessageError
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.message import Address, AddressLike, EmailMessage
from goatnotify.core.mail.transport import EmailTransport
from goatnotify.core.templates import TemplateRenderer


class Mailer:
    def __init__(
        self,
        transport: EmailTransport,
        *,
        sender: AddressLike,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._transport = transport
        self._sender = Address.parse(sender)
        self._renderer = renderer

    async def render(self, mailable: Mailable, *, to: Sequence[AddressLike] = ()) -> EmailMessage:
        if not mailable.subject:
            raise InvalidMessageError(f"{type(mailable).__qualname__} has no subject")
        context = mailable.context()
        html = mailable.html()
        if html is None:
            html = await self._render(mailable.template(), context)
        text = mailable.text()
        if text is None:
            text = await self._render(mailable.text_template(), context)
        return EmailMessage(
            subject=mailable.subject,
            sender=self._sender if mailable.sender is None else Address.parse(mailable.sender),
            to=_addresses(to or mailable.to),
            cc=_addresses(mailable.cc),
            bcc=_addresses(mailable.bcc),
            reply_to=_addresses(mailable.reply_to),
            html=html,
            text=text,
            attachments=tuple(mailable.attachments()),
            headers=dict(mailable.headers),
            metadata=dict(mailable.metadata),
        )

    async def send(self, mailable: Mailable, *, to: Sequence[AddressLike] = ()) -> str | None:
        return await self._transport.send(await self.render(mailable, to=to))

    async def _render(self, template: str | None, context: Mapping[str, object]) -> str | None:
        if template is None:
            return None
        if self._renderer is None:
            raise ConfigurationError(
                f"Template {template!r} needs a TemplateRenderer: pass renderer= to Mailer"
            )
        return await self._renderer.render(template, context)


def _addresses(values: Iterable[AddressLike]) -> tuple[Address, ...]:
    return tuple(Address.parse(value) for value in values)
