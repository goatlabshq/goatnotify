import asyncio
import smtplib
import socket
from collections.abc import AsyncIterator

import pytest
from fake_smtp import FakeSmtpServer

from goatnotify.core.errors import PermanentError, RetryableError
from goatnotify.core.mail.message import Address, EmailMessage
from goatnotify.core.mail.smtp import SmtpTransport, classify_smtp_error

MESSAGE = EmailMessage(
    subject="Hello",
    sender=Address("noreply@goat.dev"),
    to=(Address("ada@example.com"),),
    bcc=(Address("audit@example.com"),),
    text="Hi",
)


@pytest.fixture
async def smtp_server() -> AsyncIterator[FakeSmtpServer]:
    fake = FakeSmtpServer()
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    fake.port = server.sockets[0].getsockname()[1]
    async with server:
        yield fake


def _transport(server: FakeSmtpServer) -> SmtpTransport:
    return SmtpTransport("127.0.0.1", server.port, security="none", timeout=5)


async def test_a_message_is_sent_to_every_recipient(smtp_server: FakeSmtpServer) -> None:
    message_id = await _transport(smtp_server).send(MESSAGE)
    assert message_id is not None
    assert message_id.endswith("@goat.dev>")
    commands = {command.lower() for command in smtp_server.commands}
    assert "mail from:<noreply@goat.dev>" in commands
    assert {"rcpt to:<ada@example.com>", "rcpt to:<audit@example.com>"} <= commands
    (data,) = smtp_server.messages
    assert b"Subject: Hello" in data
    assert b"audit@example.com" not in data


async def test_a_temporary_refusal_is_retryable(smtp_server: FakeSmtpServer) -> None:
    smtp_server.replies["MAIL"] = "451 try again later"
    with pytest.raises(RetryableError, match="451"):
        await _transport(smtp_server).send(MESSAGE)


async def test_a_permanent_refusal_is_permanent(smtp_server: FakeSmtpServer) -> None:
    smtp_server.replies["MAIL"] = "550 mailbox unavailable"
    with pytest.raises(PermanentError, match="550"):
        await _transport(smtp_server).send(MESSAGE)


async def test_an_unreachable_server_is_retryable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(RetryableError, match="connection"):
        await SmtpTransport("127.0.0.1", port, security="none", timeout=2).send(MESSAGE)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (smtplib.SMTPAuthenticationError(535, b"bad credentials"), PermanentError),
        (smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no")}), PermanentError),
        (smtplib.SMTPNotSupportedError("no STARTTLS"), PermanentError),
        (smtplib.SMTPDataError(452, b"insufficient storage"), RetryableError),
        (smtplib.SMTPDataError(554, b"rejected"), PermanentError),
        (smtplib.SMTPServerDisconnected("gone"), RetryableError),
        (ConnectionRefusedError("refused"), RetryableError),
        (TimeoutError("slow"), RetryableError),
    ],
)
def test_smtp_errors_are_classified(error: Exception, expected: type[Exception]) -> None:
    assert type(classify_smtp_error(error)) is expected
