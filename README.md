# GoatNotify

**A modern, type-safe, framework-agnostic notification system for Python.**

GoatNotify sends notifications by email, stores them in a database, posts them to webhooks, or
delivers them through any channel you write. A notification yields typed messages, and the type
of each message decides which channel delivers it, so Pyright checks the whole path.

- Async-first, with a synchronous `notify_sync()` for scripts and sync views
- Zero runtime dependencies in the core: SMTP and webhooks use the standard library
- Retries with exponential backoff, structured results and lightweight hooks
- Pluggable channels, transports, template renderers, stores and queues
- Optional Django (email backend, templates, ORM, Django Tasks), FastAPI and Jinja2 integrations

## Installation

```bash
pip install goatnotify              # the core
pip install "goatnotify[django]"    # or [fastapi], [jinja]
```

Python 3.14 or newer is required; the Django integration needs Django 6.1 or newer.

## Quickstart

```python
import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
    SmtpTransport,
)


@dataclass
class User:
    name: str
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None


class WelcomeMail(Mailable):
    subject = "Welcome to Goat"

    def __init__(self, user: User) -> None:
        self.user = user

    def text(self) -> str | None:
        return f"Welcome, {self.user.name}!"


class Welcome(Notification[User]):
    def messages(self, user: User) -> Iterable[Message]:
        yield WelcomeMail(user)


mailer = Mailer(SmtpTransport("smtp.example.com"), sender="noreply@example.com")
notifier = Notifier([EmailChannel(mailer)])

asyncio.run(notifier.notify(User("Ada", "ada@example.com"), Welcome()))
```

Add a `DatabaseMessage` or a `WebhookMessage` to `messages()` and register `DatabaseChannel` or
`WebhookChannel`: nothing else changes.

## Documentation

<https://goatlabshq.github.io/goatnotify/>

## Packages

| Package | Contents |
|---|---|
| `goatnotify` | Facade re-exporting the core, with the `django`, `fastapi` and `jinja` extras |
| `goatnotify-core` | Notifications, channels, SMTP and HTTP transports, retries, queues, testing fakes |
| `goatnotify-jinja` | `JinjaRenderer` |
| `goatnotify-django` | Django email transport, template renderer, ORM store, Django Tasks queue |
| `goatnotify-fastapi` | Lifespan and `NotifierDep` dependency |

## Development

```bash
uv sync --all-packages
uv run pytest
uv run pyright
uv run ruff check . && uv run ruff format --check .
```

## Licence

MIT
