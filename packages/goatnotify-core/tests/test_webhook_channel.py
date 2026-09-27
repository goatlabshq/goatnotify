import hashlib
import hmac
import json
import logging
from collections.abc import Iterable

import pytest
from core_support import User

from goatnotify.core.channels.webhook import WebhookChannel, WebhookMessage
from goatnotify.core.errors import (
    DeliveryError,
    InvalidMessageError,
    PermanentError,
    RetryableError,
    SkipDelivery,
)
from goatnotify.core.http import HttpResponse
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.testing import MemoryHttpTransport, no_sleep

HOOK = "https://hooks.example.com/api/webhooks/123/SECRET-TOKEN?key=abc"


class Deployed(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield WebhookMessage(payload={"event": "deployed", "version": "1.2.0"})


async def test_the_payload_is_posted_as_compact_json() -> None:
    transport = MemoryHttpTransport()
    await WebhookChannel(transport).send(User(), WebhookMessage({"a": [1, "é"]}, url=HOOK))
    (request,) = transport.requests
    assert (request.method, request.url, request.timeout) == ("POST", HOOK, 10.0)
    assert request.body == '{"a":[1,"é"]}'.encode()
    assert request.headers["Content-Type"] == "application/json"


async def test_the_webhook_route_is_used_when_the_message_has_no_url() -> None:
    transport = MemoryHttpTransport()
    await WebhookChannel(transport).send(User(webhook=HOOK), WebhookMessage({}))
    assert transport.requests[0].url == HOOK


async def test_no_url_and_no_route_is_skipped() -> None:
    with pytest.raises(SkipDelivery, match="no webhook route"):
        await WebhookChannel(MemoryHttpTransport()).send(User(), WebhookMessage({}))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "not a url"])
async def test_non_http_urls_are_rejected(url: str) -> None:
    with pytest.raises(InvalidMessageError):
        await WebhookChannel(MemoryHttpTransport()).send(User(), WebhookMessage({}, url=url))


async def test_requests_are_signed_when_a_secret_is_configured() -> None:
    transport = MemoryHttpTransport()
    channel = WebhookChannel(transport, secret="s3cret", clock=lambda: 1_700_000_000.9)
    await channel.send(User(), WebhookMessage({"a": 1}, url=HOOK, headers={"X-Extra": "1"}))
    (request,) = transport.requests
    expected = hmac.new(b"s3cret", b"1700000000." + request.body, hashlib.sha256).hexdigest()
    assert request.headers["X-GoatNotify-Timestamp"] == "1700000000"
    assert request.headers["X-GoatNotify-Signature"] == f"sha256={expected}"
    assert request.headers["X-Extra"] == "1"


async def test_message_headers_cannot_forge_the_signature() -> None:
    transport = MemoryHttpTransport()
    message = WebhookMessage({}, url=HOOK, headers={"X-GoatNotify-Signature": "forged"})
    await WebhookChannel(transport, secret="s3cret").send(User(), message)
    assert transport.requests[0].headers["X-GoatNotify-Signature"] != "forged"


@pytest.mark.parametrize("status", [408, 429, 500, 503])
async def test_transient_statuses_are_retryable(status: int) -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(status, {}, b"busy"))
    with pytest.raises(RetryableError):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


async def test_retry_after_is_honoured() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(429, {"Retry-After": "7"}, b""))
    with pytest.raises(RetryableError) as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert caught.value.retry_after == 7.0


@pytest.mark.parametrize(
    ("header", "expected"),
    [("86400", 300.0), ("-5", None), ("soon", None), ("²", None), (" 7 ", 7.0)],
)
async def test_retry_after_is_capped(header: str, expected: float | None) -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(503, {"Retry-After": header}, b""))
    with pytest.raises(RetryableError) as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert caught.value.retry_after == expected


async def test_client_errors_are_permanent() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(404, {}, b"unknown webhook"))
    with pytest.raises(PermanentError, match="404"):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


async def test_network_errors_are_retryable() -> None:
    transport = MemoryHttpTransport()
    transport.respond(ConnectionResetError("reset"))
    with pytest.raises(RetryableError):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


@pytest.mark.parametrize(
    "outcome", [HttpResponse(404, {}, b""), HttpResponse(500, {}, b""), OSError("down")]
)
async def test_errors_do_not_leak_the_webhook_url(outcome: HttpResponse | Exception) -> None:
    transport = MemoryHttpTransport()
    transport.respond(outcome)
    with pytest.raises(DeliveryError, match=r"hooks\.example\.com") as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert "SECRET-TOKEN" not in str(caught.value)
    assert "key=abc" not in str(caught.value)
    assert "hooks.example.com" in str(caught.value)


async def test_end_to_end_retry_then_success() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(502, {}, b""), HttpResponse(204, {}, b""))
    notifier = Notifier([WebhookChannel(transport)], sleep=no_sleep)
    result = await notifier.notify(User(webhook=HOOK), Deployed())
    assert (result.deliveries[0].status, result.deliveries[0].attempts) == (DeliveryStatus.SENT, 2)
    assert json.loads(transport.requests[0].body) == {"event": "deployed", "version": "1.2.0"}


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.example.com/api/webhooks/123/SEC RET",
        "https://hooks.example.com/api/webhooks/123/SECRÉT",
        "https://hooks.example.com/api/webhooks/123/SEC\tRET",
    ],
)
async def test_malformed_urls_are_rejected_without_leaking_them(url: str) -> None:
    with pytest.raises(InvalidMessageError) as caught:
        await WebhookChannel(MemoryHttpTransport()).send(User(), WebhookMessage({}, url=url))
    assert "SEC" not in str(caught.value)


async def test_unexpected_transport_errors_do_not_leak_the_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = MemoryHttpTransport()
    transport.respond(ValueError(f"cannot send to {HOOK}"))
    notifier = Notifier([WebhookChannel(transport)])
    with caplog.at_level(logging.WARNING, logger="goatnotify"):
        result = await notifier.notify(User(webhook=HOOK), Deployed(), raise_on_failure=False)
    error = result.deliveries[0].error
    assert isinstance(error, PermanentError)
    assert error.__cause__ is None
    assert error.__suppress_context__
    assert "SECRET-TOKEN" not in str(error)
    assert "SECRET-TOKEN" not in caplog.text


async def test_redirects_are_permanent_failures() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(301, {"Location": "https://elsewhere.example.com/"}, b""))
    with pytest.raises(PermanentError, match="301"):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
