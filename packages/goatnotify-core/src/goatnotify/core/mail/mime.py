from email.message import EmailMessage as MimeMessage
from email.message import MIMEPart
from email.utils import formatdate, make_msgid

from goatnotify.core.mail.message import Address, Attachment, EmailMessage


def to_mime(message: EmailMessage) -> MimeMessage:
    mime = MimeMessage()
    mime["Subject"] = message.subject
    mime["From"] = str(message.sender)
    _set_addresses(mime, "To", message.to)
    _set_addresses(mime, "Cc", message.cc)
    _set_addresses(mime, "Reply-To", message.reply_to)
    mime["Date"] = formatdate(usegmt=True)
    for name, value in message.headers.items():
        mime[name] = value
    if "Message-ID" not in mime:
        mime["Message-ID"] = make_msgid(domain=message.sender.email.rpartition("@")[2])
    _set_body(mime, message)
    # Fetched once: each add_related() on a fresh lookup would nest another related part.
    html = mime.get_body(("html",))
    for attachment in message.attachments:
        if attachment.inline and html is not None:
            _embed(html, attachment)
        else:
            _attach(mime, attachment)
    return mime


def _set_addresses(mime: MimeMessage, header: str, addresses: tuple[Address, ...]) -> None:
    if addresses:
        mime[header] = ", ".join(str(address) for address in addresses)


def _set_body(mime: MimeMessage, message: EmailMessage) -> None:
    if message.text is not None:
        mime.set_content(message.text)
        if message.html is not None:
            mime.add_alternative(message.html, subtype="html")
    elif message.html is not None:
        mime.set_content(message.html, subtype="html")


def _attach(mime: MimeMessage, attachment: Attachment) -> None:
    maintype, subtype = attachment.mimetype.split("/")
    mime.add_attachment(
        attachment.content, maintype=maintype, subtype=subtype, filename=attachment.filename
    )


def _embed(html: MIMEPart, attachment: Attachment) -> None:
    maintype, subtype = attachment.mimetype.split("/")
    html.add_related(
        attachment.content,
        maintype=maintype,
        subtype=subtype,
        cid=f"<{attachment.filename}>",
        filename=attachment.filename,
        disposition="inline",
    )
