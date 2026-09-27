"""EmailTransport sending through the configured Django email backend."""

import email.policy
import smtplib
from email.message import EmailMessage as MimeMessage
from email.policy import Policy
from email.utils import make_msgid
from typing import override

from asgiref.sync import sync_to_async

from django.core.mail import EmailMultiAlternatives
from django.core.mail.handler import DEFAULT_MAILER_ALIAS
from goatnotify.core.errors import PermanentError
from goatnotify.core.mail.message import Address, Attachment, EmailMessage
from goatnotify.core.mail.smtp import classify_smtp_error


def _formatted(addresses: tuple[Address, ...]) -> list[str]:
    return [str(address) for address in addresses]


def _pop_message_id(headers: dict[str, str]) -> str | None:
    name = next((name for name in headers if name.lower() == "message-id"), None)
    return None if name is None else headers.pop(name)


class _EmailWithInlineImages(EmailMultiAlternatives):
    # Django has no inline-image API; message() is the public hook to wrap the HTML body.
    inline: tuple[Attachment, ...] = ()

    @override
    def message(self, *, policy: Policy | None = email.policy.default) -> MimeMessage:
        mime = super().message(policy=policy)
        html = mime.get_body(("html",))
        if html is None:
            return mime
        for attachment in self.inline:
            maintype, subtype = attachment.mimetype.split("/")
            html.add_related(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                cid=f"<{attachment.filename}>",
                filename=attachment.filename,
                disposition="inline",
            )
        return mime


class DjangoEmailTransport:
    def __init__(self, *, mailer: str = DEFAULT_MAILER_ALIAS) -> None:
        self._mailer = mailer

    async def send(self, message: EmailMessage) -> str | None:
        return await sync_to_async(self._send)(message)

    def _send(self, message: EmailMessage) -> str:
        headers = dict(message.headers)
        message_id = _pop_message_id(headers) or make_msgid(
            domain=message.sender.email.rpartition("@")[2]
        )
        outgoing = _EmailWithInlineImages(
            subject=message.subject,
            body=message.text if message.text is not None else message.html or "",
            from_email=str(message.sender),
            to=_formatted(message.to),
            cc=_formatted(message.cc),
            bcc=_formatted(message.bcc),
            reply_to=_formatted(message.reply_to),
            headers={**headers, "Message-ID": message_id},
        )
        if message.text is None:
            outgoing.content_subtype = "html"
        elif message.html is not None:
            outgoing.attach_alternative(message.html, "text/html")
        outgoing.inline = tuple(a for a in message.attachments if a.inline)
        for attachment in message.attachments:
            if not attachment.inline:
                outgoing.attach(attachment.filename, attachment.content, attachment.mimetype)
        try:
            sent = outgoing.send(using=self._mailer)
        except (smtplib.SMTPException, OSError) as error:
            raise classify_smtp_error(error) from error
        if sent == 0:
            raise PermanentError("The Django email backend accepted no message")
        return message_id
