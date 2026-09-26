# Getting started

## Installation

```bash
pip install goatnotify
```

GoatNotify requires Python 3.14 or newer. The core has no third-party dependency.

## 1. Describe the recipient

Any object with a `route_notification(channel)` method is a recipient. It returns the address
to use on a channel, or `None` when the recipient cannot be reached there.

```python
from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None
```

## 2. Write a mailable

```python
from goatnotify import Mailable


class WelcomeMail(Mailable):
    subject = "Welcome to Goat"

    def __init__(self, user: User) -> None:
        self.user = user

    def text(self) -> str | None:
        return f"Welcome, {self.user.name}!"

    def html(self) -> str | None:
        return f"<h1>Welcome, {self.user.name}!</h1>"
```

## 3. Write the notification

A notification yields the messages to deliver. Each message type is delivered by the channel
registered for it.

```python
from collections.abc import Iterable

from goatnotify import Message, Notification


class Welcome(Notification[User]):
    def messages(self, user: User) -> Iterable[Message]:
        yield WelcomeMail(user)
```

## 4. Build a notifier and send

```python
import asyncio

from goatnotify import EmailChannel, Mailer, Notifier, SmtpTransport

mailer = Mailer(
    SmtpTransport("smtp.example.com", username="apikey", password="secret"),
    sender="Goat <noreply@example.com>",
)
notifier = Notifier([EmailChannel(mailer)])


async def main() -> None:
    result = await notifier.notify(User("Ada", "ada@example.com"), Welcome())
    print(result.ok, result.deliveries[0].provider_id)


asyncio.run(main())
```

From synchronous code with no framework-managed threads (a script, a CLI command, a worker),
use `notify_sync()` with the same arguments. It refuses to run inside an event loop: there,
`await notify()` instead. In synchronous Django views, use the
[Django helpers](integrations/django.md#synchronous-code), which are safe under ASGI.

```python
result = notifier.notify_sync(User("Ada", "ada@example.com"), Welcome())
```

## 5. Read the result

`notify()` returns a `NotificationResult` with one `DeliveryResult` per message:

| Field | Meaning |
|---|---|
| `status` | `DeliveryStatus.SENT`, `FAILED` or `SKIPPED` |
| `attempts` | Number of attempts, retries included |
| `provider_id` | Identifier returned by the channel (SMTP `Message-ID`, database row id) |
| `error` | The exception of a failed delivery |
| `reason` | Why a delivery was skipped |

If any delivery failed, `notify()` raises `DeliveryFailed` once every delivery has finished.
See [Retries and failures](retries.md).

## Next steps

- Store notifications and call webhooks: [Channels](channels.md)
- Render emails from templates: [Templates](templates.md)
- Deliver in the background: [Queues](queues.md)
- Use Django or FastAPI: [Integrations](integrations/django.md)
