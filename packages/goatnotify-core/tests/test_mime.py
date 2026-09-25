from email import message_from_bytes, policy
from email.message import EmailMessage as MimeMessage

from goatnotify.core.mail.message import Address, Attachment, EmailMessage
from goatnotify.core.mail.mime import to_mime

SENDER = Address("noreply@goat.dev", "Goat")
ADA = Address("ada@example.com", "Ada")


def _parse(message: EmailMessage) -> MimeMessage:
    parsed = message_from_bytes(to_mime(message).as_bytes(), policy=policy.default)
    assert isinstance(parsed, MimeMessage)
    return parsed


def test_envelope_headers() -> None:
    mime = _parse(
        EmailMessage(
            subject="Welcome",
            sender=SENDER,
            to=(ADA,),
            cc=(Address("cc@example.com"),),
            bcc=(Address("hidden@example.com"),),
            reply_to=(Address("support@goat.dev"),),
            text="Hello",
            headers={"X-Campaign": "welcome"},
        )
    )
    assert mime["Subject"] == "Welcome"
    assert mime["From"] == "Goat <noreply@goat.dev>"
    assert mime["To"] == "Ada <ada@example.com>"
    assert mime["Cc"] == "cc@example.com"
    assert mime["Reply-To"] == "support@goat.dev"
    assert mime["X-Campaign"] == "welcome"
    assert mime["Bcc"] is None
    assert str(mime["Message-ID"]).endswith("@goat.dev>")
    assert mime["Date"] is not None


def test_an_explicit_message_id_is_kept() -> None:
    mime = _parse(
        EmailMessage(
            subject="x", sender=SENDER, to=(ADA,), text="x", headers={"Message-ID": "<id@goat.dev>"}
        )
    )
    assert mime.get_all("Message-ID") == ["<id@goat.dev>"]


def test_text_and_html_become_alternatives() -> None:
    mime = _parse(EmailMessage(subject="x", sender=SENDER, to=(ADA,), text="Hi", html="<p>Hi</p>"))
    assert mime.get_content_type() == "multipart/alternative"
    text, html = mime.get_body(("plain",)), mime.get_body(("html",))
    assert text is not None
    assert text.get_content().strip() == "Hi"
    assert html is not None
    assert html.get_content().strip() == "<p>Hi</p>"


def test_html_only() -> None:
    mime = _parse(EmailMessage(subject="x", sender=SENDER, to=(ADA,), html="<p>Hi</p>"))
    assert mime.get_content_type() == "text/html"


def test_attachments_and_inline_images() -> None:
    mime = _parse(
        EmailMessage(
            subject="x",
            sender=SENDER,
            to=(ADA,),
            text="Hi",
            html='<img src="cid:logo.png">',
            attachments=(
                Attachment("report.pdf", b"%PDF", "application/pdf"),
                Attachment("logo.png", b"\x89PNG", "image/png", inline=True),
            ),
        )
    )
    assert mime.get_content_type() == "multipart/mixed"
    files = {part.get_filename(): part for part in mime.walk() if part.get_filename()}
    assert files["report.pdf"].get_content() == b"%PDF"
    assert files["report.pdf"].get_content_disposition() == "attachment"
    assert files["logo.png"]["Content-ID"] == "<logo.png>"
    assert files["logo.png"].get_content_disposition() == "inline"


def test_non_ascii_content_survives() -> None:
    mime = _parse(
        EmailMessage(
            subject="Bienvenue, Zoé",
            sender=Address("noreply@goat.dev", "Équipe Goat"),
            to=(ADA,),
            text="Merci à vous",
        )
    )
    assert mime["Subject"] == "Bienvenue, Zoé"
    assert mime["From"] == "Équipe Goat <noreply@goat.dev>"
    body = mime.get_body(("plain",))
    assert body is not None
    assert body.get_content().strip() == "Merci à vous"
