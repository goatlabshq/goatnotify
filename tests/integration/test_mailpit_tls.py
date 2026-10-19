import ssl
import uuid
from pathlib import Path

import pytest
from mailpit import (
    PASSWORD,
    STARTTLS_API_URL,
    STARTTLS_PORT,
    TLS_API_URL,
    TLS_DIR,
    TLS_PORT,
    USERNAME,
    fetch,
    requires_mailpit_tls,
)

from goatnotify import Address, EmailMessage, PermanentError, SmtpTransport
from goatnotify.core.mail.smtp import SmtpSecurity

pytestmark = requires_mailpit_tls


def _trusted() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=Path(TLS_DIR) / "cert.pem")


def _message(subject: str) -> EmailMessage:
    return EmailMessage(
        subject=subject,
        sender=Address("noreply@goat.dev"),
        to=(Address("ada@example.com"),),
        text="Hi",
    )


@pytest.mark.parametrize(
    ("security", "port", "api_url"),
    [("starttls", STARTTLS_PORT, STARTTLS_API_URL), ("tls", TLS_PORT, TLS_API_URL)],
)
async def test_authenticated_encrypted_delivery(
    security: SmtpSecurity, port: int, api_url: str
) -> None:
    subject = f"Secure {security} {uuid.uuid4().hex}"
    transport = SmtpTransport(
        "127.0.0.1",
        port,
        username=USERNAME,
        password=PASSWORD,
        security=security,
        ssl_context=_trusted(),
        timeout=10,
    )
    await transport.send(_message(subject))
    assert fetch(subject, api_url).addresses("To") == ["ada@example.com"]


async def test_a_wrong_password_is_a_permanent_failure() -> None:
    transport = SmtpTransport(
        "127.0.0.1",
        STARTTLS_PORT,
        username=USERNAME,
        password="wrong",
        ssl_context=_trusted(),
        timeout=10,
    )
    with pytest.raises(PermanentError, match="refused"):
        await transport.send(_message("Wrong password"))


async def test_an_untrusted_certificate_is_a_permanent_failure() -> None:
    transport = SmtpTransport(
        "127.0.0.1", TLS_PORT, username=USERNAME, password=PASSWORD, security="tls", timeout=10
    )
    with pytest.raises(PermanentError, match="certificate"):
        await transport.send(_message("Untrusted"))


async def test_a_server_requiring_starttls_rejects_plain_text() -> None:
    transport = SmtpTransport("127.0.0.1", STARTTLS_PORT, security="none", timeout=10)
    with pytest.raises(PermanentError, match="530"):
        await transport.send(_message("Plain"))
