"""SMTP transport built on smtplib, run in a worker thread."""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage as MimeMessage
from typing import Final, Literal

from goatnotify.core.errors import DeliveryError, PermanentError, RetryableError
from goatnotify.core.mail.message import EmailMessage
from goatnotify.core.mail.mime import to_mime

logger: Final = logging.getLogger("goatnotify")

type SmtpSecurity = Literal["starttls", "tls", "none"]


PERMANENT_SMTP_ERRORS: Final = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPNotSupportedError,
)


def classify_smtp_error(error: Exception) -> DeliveryError:
    if isinstance(error, PERMANENT_SMTP_ERRORS):
        return PermanentError(f"SMTP delivery refused: {error}")
    if isinstance(error, smtplib.SMTPResponseException):
        kind = RetryableError if 400 <= error.smtp_code < 500 else PermanentError
        return kind(f"SMTP server answered {error.smtp_code}: {error}")
    # SMTPException subclasses OSError, so only disconnections count as network failures.
    if isinstance(error, smtplib.SMTPServerDisconnected) or (
        isinstance(error, OSError) and not isinstance(error, smtplib.SMTPException)
    ):
        return RetryableError(f"SMTP connection failed: {error}")
    return PermanentError(f"SMTP delivery failed: {error!r}")


class SmtpTransport:
    def __init__(
        self,
        host: str,
        port: int = 587,
        *,
        username: str | None = None,
        password: str | None = None,
        security: SmtpSecurity = "starttls",
        timeout: float = 30.0,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._security = security
        self._timeout = timeout
        self._ssl_context = ssl_context

    async def send(self, message: EmailMessage) -> str | None:
        mime = to_mime(message)
        await asyncio.to_thread(self._deliver, mime, message)
        return str(mime["Message-ID"])

    def _deliver(self, mime: MimeMessage, message: EmailMessage) -> None:
        try:
            with self._connect() as smtp:
                if self._username is not None:
                    smtp.login(self._username, self._password or "")
                refused = smtp.send_message(
                    mime,
                    from_addr=message.sender.email,
                    to_addrs=[address.email for address in message.recipients],
                )
        except (smtplib.SMTPException, OSError) as error:
            raise classify_smtp_error(error) from error
        if refused:
            logger.warning("SMTP server refused some recipients: %s", sorted(refused))

    def _connect(self) -> smtplib.SMTP:
        context = self._ssl_context or ssl.create_default_context()
        if self._security == "tls":
            return smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout, context=context)
        smtp = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        if self._security == "starttls":
            try:
                smtp.starttls(context=context)
            except BaseException:
                smtp.close()
                raise
        return smtp
