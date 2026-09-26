# Transports

Channels decide *what* a delivery means; transports do the I/O. Keeping them apart lets you swap
SMTP for an HTTP provider without touching a single notification.

## Email transports

```python
class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> str | None: ...
```

`EmailMessage` is the fully rendered email: `subject`, `sender`, `to`, `cc`, `bcc`, `reply_to`,
`html`, `text`, `attachments`, `headers` and `metadata`. The transport returns a provider
identifier (or `None`).

### SMTP

```python
SmtpTransport(
    "smtp.example.com",
    587,
    username="apikey",
    password="secret",
    security="starttls",  # "starttls", "tls" (implicit TLS, port 465) or "none"
    timeout=30.0,
    ssl_context=None,  # defaults to ssl.create_default_context()
)
```

It uses `smtplib` in a worker thread, opens one connection per message, and returns the
`Message-ID`. Errors are classified for the [retry policy](retries.md):

| Error | Outcome |
|---|---|
| Connection refused, timeout, `SMTPServerDisconnected` | retryable |
| 4xx reply | retryable |
| 5xx reply | permanent |
| `SMTPAuthenticationError`, `SMTPRecipientsRefused`, `SMTPNotSupportedError` | permanent |

The mapping is exposed as `goatnotify.core.mail.smtp.classify_smtp_error()` for transports
that wrap `smtplib` themselves.

### Django

`goatnotify.django.mail.DjangoEmailTransport` sends through a Django mailer; see
[Django](integrations/django.md).

## HTTP transports

```python
class HttpTransport(Protocol):
    async def send(self, request: HttpRequest) -> HttpResponse: ...
```

`UrllibTransport` is the standard-library implementation used by default. It returns every HTTP
status as a response (it never raises for 4xx or 5xx), raises `OSError` for network failures,
and refuses anything but `http` and `https` URLs.

An `HttpTransport` backed by `httpx` or `aiohttp` is a few lines:

```python
class HttpxTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def send(self, request: HttpRequest) -> HttpResponse:
        try:
            response = await self._client.request(
                request.method,
                request.url,
                headers=dict(request.headers),
                content=request.body,
                timeout=request.timeout,
            )
        except httpx.TransportError as error:
            raise OSError(str(error)) from error
        return HttpResponse(response.status_code, dict(response.headers), response.content)
```

## Testing fakes

`goatnotify.core.testing` provides in-memory transports for your tests:

| Fake | Records | Scripting |
|---|---|---|
| `MemoryTransport` | `outbox: list[EmailMessage]` | `fail_next(*errors)` |
| `MemoryHttpTransport` | `requests: list[HttpRequest]` | `respond(*responses_or_errors)` |
| `MemoryStore` | `records`, `for_notifiable(recipient)` | |

```python
transport = MemoryTransport()
transport.fail_next(RetryableError("421 try later"))
notifier = Notifier([EmailChannel(Mailer(transport, sender="a@b.c"))], sleep=no_sleep)
```

`no_sleep` replaces `asyncio.sleep` so retries run instantly.
