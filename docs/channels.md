# Channels

A channel delivers one type of message. GoatNotify ships three; you can add your own
([custom channels](custom-channels.md)).

| Channel | Message | Name |
|---|---|---|
| `EmailChannel(mailer)` | `Mailable` | `"email"` |
| `DatabaseChannel(store)` | `DatabaseMessage` | `"database"` |
| `WebhookChannel(transport)` | `WebhookMessage` | `"webhook"` |

Every built-in channel accepts `retry=` to override the notifier's
[retry policy](retries.md).

## Email

```python
EmailChannel(Mailer(SmtpTransport("smtp.example.com"), sender="noreply@example.com"))
```

The recipient's `"email"` route is used when the mailable has no `to`. A recipient without an
email route is skipped.

## Database

```python
@dataclass(frozen=True, slots=True)
class DatabaseMessage(Message):
    kind: str
    data: Mapping[str, JsonValue]
```

The channel turns the message into a `StoredNotification` (a UUID, `kind`, `data` and an aware
UTC `created_at`) and hands it to a `NotificationStore`:

```python
class NotificationStore(Protocol):
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None: ...
```

The core never talks to a database. Use the [Django store](integrations/django.md), or write one:

```python
class SqlAlchemyStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        async with self._sessions.begin() as session:
            session.add(
                NotificationRow(
                    id=record.id,
                    user_id=cast(Account, notifiable).id,
                    kind=record.kind,
                    data=dict(record.data),
                    created_at=record.created_at,
                )
            )
```

## Webhook

```python
@dataclass(frozen=True, slots=True)
class WebhookMessage(Message):
    payload: JsonValue
    url: str | None = None  # None: the recipient's "webhook" route
    headers: Mapping[str, str] = {}
    method: Literal["POST", "PUT"] = "POST"
```

The payload is sent as compact JSON. Only absolute `http` and `https` URLs are accepted.

| Response | Outcome |
|---|---|
| 2xx | sent |
| 408, 429, 5xx, network error | retried; `Retry-After` (seconds) is honoured and capped at 300 |
| other statuses | permanent failure |

Webhook URLs often carry credentials (Discord and Slack URLs do), so error messages and logs
only name the host, never the full URL.

### Signed requests

With `WebhookChannel(secret="...")`, every request carries:

- `X-GoatNotify-Timestamp`: Unix time in seconds;
- `X-GoatNotify-Signature`: `sha256=` followed by the hex HMAC-SHA256 of
  `"{timestamp}." + body`, keyed with the secret.

Receivers verify it like this:

```python
import hashlib
import hmac
import time


def verify(secret: bytes, body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp)) > 300:
        return False
    expected = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```
