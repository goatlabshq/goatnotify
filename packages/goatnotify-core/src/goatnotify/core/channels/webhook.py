import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final, Literal
from urllib.parse import urlsplit

from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.errors import DeliveryError, PermanentError, RetryableError, SkipDelivery
from goatnotify.core.http import (
    HttpRequest,
    HttpResponse,
    HttpTransport,
    UrllibTransport,
    require_http_url,
)
from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy

SIGNATURE_HEADER: Final = "X-GoatNotify-Signature"
TIMESTAMP_HEADER: Final = "X-GoatNotify-Timestamp"
MAX_RETRY_AFTER: Final = 300.0
RETRYABLE_STATUSES: Final = frozenset({408, 429})
ERROR_BODY_LIMIT: Final = 200


@dataclass(frozen=True, slots=True)
class WebhookMessage(Message):
    payload: JsonValue
    url: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    method: Literal["POST", "PUT"] = "POST"


class WebhookChannel(Channel[WebhookMessage]):
    name = "webhook"
    message_type = WebhookMessage

    def __init__(
        self,
        transport: HttpTransport | None = None,
        *,
        secret: str | None = None,
        timeout: float = 10.0,
        retry: RetryPolicy | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._secret = secret
        self._timeout = timeout
        self._clock = clock
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: WebhookMessage) -> str | None:
        url = message.url or notifiable.route_notification(self.name)
        if url is None:
            raise SkipDelivery(f"{type(notifiable).__qualname__} has no webhook route")
        require_http_url(url)
        body = json.dumps(message.payload, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json", **message.headers, **self._sign(body)}
        host = urlsplit(url).netloc
        try:
            response = await self._transport.send(
                HttpRequest(message.method, url, headers, body, self._timeout)
            )
        except DeliveryError:
            raise
        # "from None": transport errors often quote the full URL, which may embed a token.
        except OSError as error:
            detail = f"Webhook request to {host} failed: {type(error).__name__}"
            raise RetryableError(detail) from None
        except Exception as error:
            detail = f"Webhook request to {host} failed: {type(error).__name__}"
            raise PermanentError(detail) from None
        _raise_for_status(response, host)
        return None

    def _sign(self, body: bytes) -> dict[str, str]:
        if self._secret is None:
            return {}
        timestamp = str(int(self._clock()))
        digest = hmac.new(
            self._secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return {TIMESTAMP_HEADER: timestamp, SIGNATURE_HEADER: f"sha256={digest}"}


def _raise_for_status(response: HttpResponse, host: str) -> None:
    if 200 <= response.status < 300:
        return
    detail = f"Webhook {host} answered {response.status}: {response.body[:ERROR_BODY_LIMIT]!r}"
    if response.status in RETRYABLE_STATUSES or response.status >= 500:
        raise RetryableError(detail, retry_after=_retry_after(response))
    raise PermanentError(detail)


def _retry_after(response: HttpResponse) -> float | None:
    value = (response.header("Retry-After") or "").strip()
    if not (value.isascii() and value.isdecimal()):
        return None
    return min(float(value), MAX_RETRY_AFTER)
