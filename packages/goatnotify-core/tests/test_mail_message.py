from pathlib import Path

import pytest

from goatnotify.core.errors import InvalidMessageError
from goatnotify.core.mail.message import Address, Attachment, EmailMessage

SENDER = Address("noreply@goat.dev", "Goat")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ada@example.com", Address("ada@example.com")),
        ("Ada Lovelace <ada@example.com>", Address("ada@example.com", "Ada Lovelace")),
        (Address("x@y.z"), Address("x@y.z")),
    ],
)
def test_addresses_are_parsed(raw: str | Address, expected: Address) -> None:
    assert Address.parse(raw) == expected


@pytest.mark.parametrize("raw", ["", "not-an-email", "@example.com", "ada@"])
def test_invalid_addresses_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidMessageError):
        Address.parse(raw)


def test_addresses_format_with_their_display_name() -> None:
    assert str(Address("ada@example.com", "Ada")) == "Ada <ada@example.com>"
    assert str(Address("ada@example.com")) == "ada@example.com"


def test_attachment_from_path_guesses_the_mimetype(tmp_path: Path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-1.7")
    attachment = Attachment.from_path(path)
    assert (attachment.filename, attachment.content, attachment.mimetype) == (
        "report.pdf",
        b"%PDF-1.7",
        "application/pdf",
    )


def test_an_email_needs_a_recipient_and_a_body() -> None:
    with pytest.raises(InvalidMessageError, match="recipient"):
        EmailMessage(subject="Hi", sender=SENDER, text="Hello")
    with pytest.raises(InvalidMessageError, match="body"):
        EmailMessage(subject="Hi", sender=SENDER, to=(Address("a@b.c"),))


def test_recipients_include_cc_and_bcc() -> None:
    message = EmailMessage(
        subject="Hi",
        sender=SENDER,
        to=(Address("a@b.c"),),
        cc=(Address("c@b.c"),),
        bcc=(Address("d@b.c"),),
        text="Hello",
    )
    assert [a.email for a in message.recipients] == ["a@b.c", "c@b.c", "d@b.c"]


@pytest.mark.parametrize(
    "build",
    [
        lambda: Address.parse("Ada\r\nBcc: evil@x.y <ada@example.com>"),
        lambda: Address("ada@example.com", "Ada\nBcc: evil@x.y"),
        lambda: EmailMessage(subject="Hi\r\nBcc: evil@x.y", sender=SENDER, to=(SENDER,), text="x"),
        lambda: EmailMessage(
            subject="Hi", sender=SENDER, to=(SENDER,), text="x", headers={"X-Tag": "a\nb"}
        ),
        lambda: Attachment(filename="a\r\n.txt", content=b""),
    ],
)
def test_line_breaks_are_rejected_everywhere(build: object) -> None:
    assert callable(build)
    with pytest.raises(InvalidMessageError, match="line breaks"):
        build()


@pytest.mark.parametrize(
    "header",
    ["Subject", "bcc", "Content-Type", "Sender", "Content-Transfer-Encoding", "Return-Path"],
)
def test_reserved_headers_cannot_be_overridden(header: str) -> None:
    with pytest.raises(InvalidMessageError, match="reserved"):
        EmailMessage(subject="Hi", sender=SENDER, to=(SENDER,), text="x", headers={header: "v"})


@pytest.mark.parametrize("filename", ["logo 1.png", "<logo>.png", "logo@2x.png"])
def test_inline_attachment_names_must_be_valid_content_ids(filename: str) -> None:
    with pytest.raises(InvalidMessageError, match="Inline attachment"):
        Attachment(filename, b"x", "image/png", inline=True)


def test_inline_attachment_names_must_be_unique() -> None:
    logo = Attachment("logo.png", b"x", "image/png", inline=True)
    with pytest.raises(InvalidMessageError, match=r"logo\.png"):
        EmailMessage(subject="x", sender=SENDER, to=(SENDER,), html="x", attachments=(logo, logo))


@pytest.mark.parametrize(
    "email",
    ["a@b.com,victim@evil.com", "a@b.com;victim@evil.com", "<a@b.com>", 'a"@b.com', "a@b.com)"],
)
def test_an_address_holds_exactly_one_mailbox(email: str) -> None:
    with pytest.raises(InvalidMessageError, match="not an email address"):
        Address(email)


def test_parse_rejects_several_mailboxes() -> None:
    with pytest.raises(InvalidMessageError):
        Address.parse("Ada <a@b.com>, Eve <victim@evil.com>")


@pytest.mark.parametrize("name", ["X Y", "X:Y", "", "X-Tàg"])
def test_header_names_must_be_rfc_5322_field_names(name: str) -> None:
    with pytest.raises(InvalidMessageError, match="header name"):
        EmailMessage(subject="Hi", sender=SENDER, to=(SENDER,), text="x", headers={name: "v"})
