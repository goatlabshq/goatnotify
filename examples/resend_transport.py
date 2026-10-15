import asyncio
import base64
import json
from typing import Final, cast

from goatnotify import (
    EmailMessage,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    JsonValue,
    Mailable,
    Mailer,
    PermanentError,
    RetryableError,
    UrllibTransport,
)
from goatnotify.core.testing import MemoryHttpTransport

ENDPOINT: Final = "https://api.resend.com/emails"


class ResendTransport:
    def __init__(self, api_key: str, *, http: HttpTransport | None = None) -> None:
        self._api_key = api_key
        self._http = http or UrllibTransport()

    async def send(self, message: EmailMessage) -> str | None:
        request = HttpRequest(
            "POST",
            ENDPOINT,
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json.dumps(_payload(message)).encode(),
            30.0,
        )
        try:
            response = await self._http.send(request)
        except OSError as error:
            raise RetryableError(f"Resend is unreachable: {type(error).__name__}") from error
        return _message_id(response)


def _payload(message: EmailMessage) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "from": str(message.sender),
        "to": [str(address) for address in message.to],
        "subject": message.subject,
        "cc": [str(address) for address in message.cc],
        "bcc": [str(address) for address in message.bcc],
        "reply_to": [str(address) for address in message.reply_to],
        "headers": dict(message.headers),
        "attachments": [
            {"filename": a.filename, "content": base64.b64encode(a.content).decode()}
            for a in message.attachments
        ],
        "tags": [{"name": name, "value": value} for name, value in message.metadata.items()],
    }
    if message.html is not None:
        payload["html"] = message.html
    if message.text is not None:
        payload["text"] = message.text
    return payload


def _message_id(response: HttpResponse) -> str | None:
    if response.status == 429 or response.status >= 500:
        raise RetryableError(f"Resend answered {response.status}")
    if response.status >= 400:
        raise PermanentError(f"Resend answered {response.status}: {response.body[:200]!r}")
    data: object = json.loads(response.body)
    if isinstance(data, dict):
        identifier = cast("dict[str, object]", data).get("id")
        return identifier if isinstance(identifier, str) else None
    return None


class Receipt(Mailable):
    subject = "Your receipt"

    def text(self) -> str | None:
        return "Thanks for your order."


async def main() -> None:
    http = MemoryHttpTransport()
    http.respond(HttpResponse(200, {}, b'{"id": "re_123"}'))
    mailer = Mailer(ResendTransport("re_test_key", http=http), sender="shop@goat.dev")
    print(f"resend id={await mailer.send(Receipt(), to=['ada@example.com'])}")


if __name__ == "__main__":
    asyncio.run(main())
