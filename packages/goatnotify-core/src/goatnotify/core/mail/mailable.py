from collections.abc import Mapping, Sequence
from types import MappingProxyType

from goatnotify.core.mail.message import AddressLike, Attachment
from goatnotify.core.notification import Message

_EMPTY: MappingProxyType[str, str] = MappingProxyType({})


class Mailable(Message):
    subject: str = ""
    sender: AddressLike | None = None
    to: Sequence[AddressLike] = ()
    cc: Sequence[AddressLike] = ()
    bcc: Sequence[AddressLike] = ()
    reply_to: Sequence[AddressLike] = ()
    headers: Mapping[str, str] = _EMPTY
    metadata: Mapping[str, str] = _EMPTY

    def attachments(self) -> Sequence[Attachment]:
        return ()

    def html(self) -> str | None:
        return None

    def text(self) -> str | None:
        return None

    def template(self) -> str | None:
        return None

    def text_template(self) -> str | None:
        return None

    def context(self) -> Mapping[str, object]:
        return _EMPTY
