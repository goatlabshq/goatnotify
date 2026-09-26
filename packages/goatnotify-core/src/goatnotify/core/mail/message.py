"""Rendered email value objects, the input of every EmailTransport."""

import mimetypes
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from email import headerregistry
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Final

from goatnotify.core.errors import InvalidMessageError

DEFAULT_MIMETYPE: Final = "application/octet-stream"
MAILBOX_SPECIALS: Final = frozenset('<>()[],;:\\"')
INLINE_NAME: Final = re.compile(r"[A-Za-z0-9._-]+")
RESERVED_HEADERS: Final = frozenset(
    {"subject", "from", "to", "cc", "bcc", "reply-to", "date", "content-type", "mime-version"}
)


def _reject_line_breaks(value: str, what: str) -> None:
    if "\r" in value or "\n" in value:
        raise InvalidMessageError(f"{what} must not contain line breaks")


def _is_single_mailbox(email: str) -> bool:
    # Providers re-parse formatted addresses, so "a@b.com,c@d.com" would reach two mailboxes.
    local, _, domain = email.rpartition("@")
    if not local or not domain or any(c in MAILBOX_SPECIALS or c.isspace() for c in email):
        return False
    try:
        return headerregistry.Address(addr_spec=email).addr_spec == email
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class Address:
    email: str
    name: str | None = None

    def __post_init__(self) -> None:
        _reject_line_breaks(self.email, "An email address")
        if self.name is not None:
            _reject_line_breaks(self.name, "An address name")
        if not _is_single_mailbox(self.email):
            raise InvalidMessageError(f"{self.email!r} is not an email address")

    @classmethod
    def parse(cls, value: str | Address) -> Address:
        if isinstance(value, Address):
            return value
        _reject_line_breaks(value, "An email address")
        name, email = parseaddr(value)
        if not email:
            raise InvalidMessageError(f"{value!r} is not an email address")
        return cls(email=email, name=name or None)

    def __str__(self) -> str:
        return formataddr((self.name, self.email)) if self.name else self.email


type AddressLike = str | Address


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content: bytes
    mimetype: str = DEFAULT_MIMETYPE
    inline: bool = False

    def __post_init__(self) -> None:
        _reject_line_breaks(self.filename, "An attachment filename")
        if self.mimetype.count("/") != 1:
            raise InvalidMessageError(f"{self.mimetype!r} is not a MIME type")
        if self.inline and not INLINE_NAME.fullmatch(self.filename):
            raise InvalidMessageError(
                f"Inline attachment {self.filename!r} is referenced as cid:<filename>, so its "
                "name may only use letters, digits, dots, dashes and underscores"
            )

    @classmethod
    def from_path(
        cls, path: str | Path, *, mimetype: str | None = None, inline: bool = False
    ) -> Attachment:
        path = Path(path)
        guessed, _ = mimetypes.guess_file_type(path)
        return cls(
            filename=path.name,
            content=path.read_bytes(),
            mimetype=mimetype or guessed or DEFAULT_MIMETYPE,
            inline=inline,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailMessage:
    subject: str
    sender: Address
    to: tuple[Address, ...] = ()
    cc: tuple[Address, ...] = ()
    bcc: tuple[Address, ...] = ()
    reply_to: tuple[Address, ...] = ()
    html: str | None = None
    text: str | None = None
    attachments: tuple[Attachment, ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    metadata: Mapping[str, str] = field(default_factory=dict[str, str])

    def __post_init__(self) -> None:
        _reject_line_breaks(self.subject, "A subject")
        for name, value in self.headers.items():
            _reject_line_breaks(name, "A header name")
            _reject_line_breaks(value, f"Header {name!r}")
            if name.lower() in RESERVED_HEADERS:
                raise InvalidMessageError(f"{name} is reserved: set it through the message fields")
        inline_names = [a.filename for a in self.attachments if a.inline]
        if duplicates := sorted({name for name in inline_names if inline_names.count(name) > 1}):
            raise InvalidMessageError(f"Inline attachment names must be unique: {duplicates}")
        if not self.recipients:
            raise InvalidMessageError("An email needs at least one recipient")
        if self.html is None and self.text is None:
            raise InvalidMessageError("An email needs an HTML or a text body")

    @property
    def recipients(self) -> tuple[Address, ...]:
        return self.to + self.cc + self.bcc
