# GoatNotify design

Status: approved in conversation on 2026-09-25, pending written review.

GoatNotify is a type-safe, async-first, framework-agnostic notification system for Python.
A notification describes *what* to say as typed messages; channels decide *where* each message
goes; transports do the low-level I/O. The core depends only on the standard library. Django,
FastAPI and Jinja are optional adapters.

It borrows ideas from Laravel Notifications and Mailables but not their API: there is no
`via()` + `to_<channel>()` pair resolved by name at runtime. A notification yields messages,
and the type of each message selects its channel, so pyright checks the whole path.

## 1. Goals and non-goals

Goals:

- Core with zero third-party runtime dependencies. A test enforces that it never imports
  `django`, `fastapi`, `starlette`, `jinja2`, `sqlalchemy`, `celery` or `httpx`.
- Pyright strict everywhere. `Any` only at the two documented boundaries (§4.4, §4.5).
- Async-first: every channel, transport, store, renderer and queue is `async`.
- No global mutable state in the core; everything is injected into `Notifier`.
- Failures are never swallowed: every delivery ends in a structured result, and failures raise
  unless the caller opts out.

Non-goals (v1):

- Provider integrations (Resend, SES, SendGrid, Mailgun). The HTTP transport abstraction and a
  documented example make them easy to add later.
- Flask and SQLAlchemy adapters. They are documented as custom implementations.
- Celery, RQ, Arq and Dramatiq queues. Only the `Queue` protocol, an in-process reference
  queue and a Django Tasks queue ship.
- Persisted retry schedules. Retries run in-process; durable retries belong to the queue.
- Bulk sending to many notifiables in one call.

## 2. Repository layout

A uv workspace modeled on GoatSEO. Every package is a portion of the `goatnotify` import
namespace; only the facade owns `goatnotify/__init__.py` and uses `pkgutil.extend_path`.
`.typecheck/goatnotify` is a symlink tree merging all portions so pyright resolves the namespace.

| Distribution | Import path | Contents | Runtime dependencies |
|---|---|---|---|
| `goatnotify-core` | `goatnotify.core` | notifications, notifier, mail, channels, transports, retry, events, queue, testing fakes | none |
| `goatnotify-jinja` | `goatnotify.jinja` | `JinjaRenderer` | `jinja2>=3.1` |
| `goatnotify-django` | `goatnotify.django` | email transport, template renderer, ORM store, model, migration, Tasks queue, default notifier | `django>=6.0` |
| `goatnotify-fastapi` | `goatnotify.fastapi` | lifespan, dependency | `fastapi>=0.115` |
| `goatnotify` | `goatnotify` | facade re-exporting the core public API | `goatnotify-core` |

Facade extras: `jinja`, `django`, `fastapi`. `pip install goatnotify` installs no framework.

Top-level folders: `packages/`, `tests/{integration,typing}/`, `examples/`, `docs/`,
`scripts/`, `release/`, `.github/`, `.typecheck/`. Per-package unit tests live in
`packages/<name>/tests/`.

Target: Python 3.14+ (PEP 695 generics, deferred annotations). Django 6.0+ for `django.tasks`.

## 3. Core concepts

```text
Notification ──yields──▶ Message ──routed by type──▶ Channel ──▶ Transport / Store
                                                         ▲
Notifier: owns channels, retry policy, hooks, queue ─────┘
```

| Concept | Role |
|---|---|
| `Notifiable` | Protocol: how a recipient is reached on a given channel. |
| `Notification[R]` | What to send to a recipient of type `R`, as a sequence of messages. |
| `Message` | Base class of everything a notification yields (`Mailable`, `DatabaseMessage`, `WebhookMessage`, custom). |
| `Channel[M]` | Delivers messages of type `M`. Owns its transport or store. |
| `Notifier` | Routes messages to channels, applies retries, fires hooks, returns results. |
| `NotificationResult` | One `DeliveryResult` per message. |

## 4. Public API

### 4.1 Notifiable

```python
class Notifiable(Protocol):
    def route_notification(self, channel: str) -> str | None: ...
```

`channel` is the channel's `name` (`"email"`, `"database"`, `"webhook"`, or a custom name).
Returning `None` means the recipient cannot be reached there, and the delivery is `skipped`.
Any object with this method works: dataclasses, Pydantic models, Django or SQLAlchemy models.

### 4.2 Notification and messages

```python
class Message:  # plain base class, no fields
    ...

class Notification[R: Notifiable](ABC):
    @abstractmethod
    def messages(self, notifiable: R) -> Iterable[Message]: ...
```

```python
class Welcome(Notification[User]):
    def __init__(self, plan: str) -> None:
        self.plan = plan

    def messages(self, user: User) -> Iterable[Message]:
        yield WelcomeMail(user)
        yield DatabaseMessage(kind="welcome", data={"plan": self.plan})
```

Yielding nothing sends nothing; that replaces Laravel's `shouldSend`.

### 4.3 Channels

```python
class Channel[M: Message](ABC):
    name: str
    message_type: type[M]
    retry: RetryPolicy | None = None  # overrides the notifier default

    @abstractmethod
    async def send(self, notifiable: Notifiable, message: M) -> str | None: ...
```

`send` returns an optional provider identifier (SMTP `Message-ID`, database row id) stored in
the result. It signals outcomes through exceptions (§5). A custom channel is a subclass:

```python
class DiscordChannel(Channel[DiscordMessage]):
    name = "discord"
    message_type = DiscordMessage
```

### 4.4 Notifier

```python
class Notifier:
    def __init__(
        self,
        channels: Iterable[Channel[Any]],
        *,
        retry: RetryPolicy | None = None,  # None: RetryPolicy()
        hooks: Iterable[Hook] = (),
        queue: Queue | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None: ...

    async def notify[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult: ...

    def notify_sync[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult: ...

    async def enqueue[R: Notifiable](self, notifiable: R, notification: Notification[R]) -> None: ...
```

- `channels` is typed `Channel[Any]` because `Channel[Mailable]` is not a `Channel[Message]`
  (the message parameter is contravariant). This is the first documented `Any` boundary; the
  second is `NotificationResult.notification`, for the same reason.
- Routing walks the message class MRO, so `WelcomeMail(Mailable)` reaches the channel
  registered for `Mailable`. Two channels for the same `message_type` raise
  `ConfigurationError` at construction.
- Before any delivery starts, every message must have a channel; otherwise
  `ConfigurationError` is raised and nothing is sent.
- Messages of one notification are delivered concurrently (`asyncio.gather` over coroutines
  that never raise); `results` keep the order of `messages()`.
- `notify_sync` runs `asyncio.run`. Called from a running event loop it raises
  `ConfigurationError` instead of deadlocking.
- `enqueue` without a configured queue raises `ConfigurationError`.
- `sleep` is injectable so retry tests run instantly.

### 4.5 Results

```python
class DeliveryStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass(frozen=True, slots=True)
class DeliveryResult:
    channel: str
    message: Message
    status: DeliveryStatus
    attempts: int
    provider_id: str | None = None
    error: Exception | None = None
    reason: str | None = None  # why it was skipped

@dataclass(frozen=True, slots=True)
class NotificationResult:
    id: UUID
    notification: Notification[Any]
    deliveries: tuple[DeliveryResult, ...]

    @property
    def ok(self) -> bool: ...
    @property
    def failed(self) -> tuple[DeliveryResult, ...]: ...
    def raise_for_failures(self) -> None: ...
```

## 5. Errors and retries

```text
NotificationError
├── ConfigurationError
└── DeliveryError
    ├── RetryableError(retry_after: float | None = None)
    ├── PermanentError
    │   └── InvalidMessageError
    └── SkipDelivery(reason: str)

DeliveryFailed(ExceptionGroup[Exception])   # .result: NotificationResult
```

- `RetryableError` is retried according to the policy; `retry_after` overrides the computed
  delay (for `Retry-After` headers).
- `PermanentError` and any unexpected exception fail immediately, without retry. The original
  exception is kept in `DeliveryResult.error`.
- `SkipDelivery` produces a `skipped` result. Built-in channels raise it when the route is
  `None`.
- After all deliveries finish, if any failed and `raise_on_failure` is true, `notify` raises
  `DeliveryFailed` carrying every failure and the full result. Callers can use `except*`.
- `asyncio.CancelledError` and other `BaseException`s propagate untouched.

```python
@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Backoff = ExponentialBackoff()

class Backoff(Protocol):
    def delay(self, attempt: int) -> float: ...

@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    initial: float = 1.0
    multiplier: float = 2.0
    maximum: float = 60.0
    jitter: bool = True  # full jitter: uniform(0, computed)
```

`NO_RETRY = RetryPolicy(max_attempts=1)`. Invalid values (`max_attempts < 1`, negative delays)
raise `ValueError` at construction.

## 6. Events and hooks

```python
type Hook = Callable[[Event], Awaitable[None] | None]
type Event = Sending | Retrying | Sent | Failed | Skipped
```

Each event is a frozen dataclass with `notification_id`, `notification`, `notifiable`,
`channel`, `message`, and, where relevant, `attempt`, `delay`, `error` or `provider_id`.
`Event.name` is a `Literal` such as `"notification.sending"`. Hooks run in registration order;
an exception raised by a hook is logged with `logger.exception` on the `goatnotify` logger and
does not change the delivery outcome. There is no event bus.

## 7. Email

### 7.1 Mailable

`Mailable(Message)` is subclassed. Envelope data are attributes with class-level defaults;
content comes from overridable methods.

| Member | Type | Default |
|---|---|---|
| `subject` | `str` | required, `InvalidMessageError` if empty |
| `sender` | `str \| Address \| None` | mailer default |
| `to`, `cc`, `bcc`, `reply_to` | `Sequence[str \| Address]` | `()`; empty `to` uses the `"email"` route |
| `headers` | `Mapping[str, str]` | `{}` |
| `metadata` | `Mapping[str, str]` | `{}` (tags for providers, never sent as headers) |
| `attachments()` | `Sequence[Attachment]` | `()` |
| `html()`, `text()` | `str \| None` | `None` |
| `template()`, `text_template()` | `str \| None` | `None` |
| `context()` | `Mapping[str, object]` | `{}` |

Precedence per body: raw `html()` wins over `template()`, raw `text()` over `text_template()`.
At least one body is required.

### 7.2 Rendered message and transport

```python
@dataclass(frozen=True, slots=True)
class Address:
    email: str
    name: str | None = None
    @classmethod
    def parse(cls, value: str | Address) -> Address: ...  # "Name <a@b.c>" or "a@b.c"

@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content: bytes
    mimetype: str = "application/octet-stream"
    inline: bool = False
    @classmethod
    def from_path(cls, path: Path, *, mimetype: str | None = None) -> Attachment: ...

@dataclass(frozen=True, slots=True)
class EmailMessage:  # fully rendered, transport input
    subject: str
    sender: Address
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    bcc: tuple[Address, ...]
    reply_to: tuple[Address, ...]
    html: str | None
    text: str | None
    attachments: tuple[Attachment, ...]
    headers: Mapping[str, str]
    metadata: Mapping[str, str]

class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> str | None: ...
```

`to_mime(message) -> email.message.EmailMessage` is public so HTTP providers that accept raw
MIME can reuse it. Subjects, names, header names and values containing CR or LF raise
`InvalidMessageError`, and so do custom headers that would override `Subject`, `From`, `To`,
`Cc`, `Bcc`, `Reply-To`, `Date`, `Content-Type` or `MIME-Version`.

### 7.3 Mailer and EmailChannel

```python
class Mailer:
    def __init__(self, transport: EmailTransport, *, sender: str | Address,
                 renderer: TemplateRenderer | None = None) -> None: ...
    async def render(self, mailable: Mailable, *, to: Sequence[str | Address] = ()) -> EmailMessage: ...
    async def send(self, mailable: Mailable, *, to: Sequence[str | Address] = ()) -> str | None: ...

class EmailChannel(Channel[Mailable]):
    name = "email"
    def __init__(self, mailer: Mailer, *, retry: RetryPolicy | None = None) -> None: ...
```

`Mailer` sends a mailable without any notification. A template without a renderer raises
`ConfigurationError`.

### 7.4 SMTP transport

`SmtpTransport(host, port=587, *, username=None, password=None,
security: Literal["starttls", "tls", "none"] = "starttls", timeout=30.0,
ssl_context=None)` uses `smtplib` inside `asyncio.to_thread`, one connection per send.
Error mapping: connection errors, `SMTPServerDisconnected` and 4xx replies become
`RetryableError`; 5xx replies, `SMTPAuthenticationError` and `SMTPRecipientsRefused` become
`PermanentError`. It returns the generated `Message-ID`. The mapping is exposed as
`classify_smtp_error(error)` so the Django transport reuses it.

### 7.5 Templates

```python
class TemplateRenderer(Protocol):
    async def render(self, template: str, context: Mapping[str, object]) -> str: ...
```

The core ships no renderer. `goatnotify.jinja.JinjaRenderer(environment)` uses `render_async`
when the environment is async and `asyncio.to_thread` otherwise;
`JinjaRenderer.from_directory(path)` builds an environment with HTML autoescaping on.
`goatnotify.django.DjangoTemplateRenderer` wraps `render_to_string`.

## 8. Database channel

```python
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]

@dataclass(frozen=True, slots=True)
class DatabaseMessage(Message):
    kind: str
    data: Mapping[str, JsonValue]

@dataclass(frozen=True, slots=True)
class StoredNotification:
    id: UUID
    kind: str
    data: Mapping[str, JsonValue]
    created_at: datetime  # aware, UTC

class NotificationStore(Protocol):
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None: ...

class DatabaseChannel(Channel[DatabaseMessage]):
    name = "database"
    def __init__(self, store: NotificationStore, *, retry: RetryPolicy | None = None,
                 clock: Callable[[], datetime] = utc_now) -> None: ...
```

The store decides how to identify the notifiable (Django uses content type and primary key).
The database channel does not consult `route_notification`. Reading, listing and
marking as read are store concerns, not core API.

## 9. Webhook channel and HTTP transport

```python
@dataclass(frozen=True, slots=True)
class WebhookMessage(Message):
    payload: JsonValue
    url: str | None = None  # None: the "webhook" route
    headers: Mapping[str, str] = field(default_factory=dict)
    method: Literal["POST", "PUT"] = "POST"

@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout: float

@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

class HttpTransport(Protocol):
    async def send(self, request: HttpRequest) -> HttpResponse: ...

class UrllibTransport: ...  # urllib.request in asyncio.to_thread, returns non-2xx as responses

class WebhookChannel(Channel[WebhookMessage]):
    name = "webhook"
    def __init__(self, transport: HttpTransport = UrllibTransport(), *,
                 secret: str | None = None, timeout: float = 10.0,
                 retry: RetryPolicy | None = None) -> None: ...
```

- Only `http` and `https` URLs are accepted (`InvalidMessageError` otherwise), since urllib
  would also open `file:` URLs.
- The body is compact JSON with `Content-Type: application/json`.
- With `secret`, the channel adds `X-GoatNotify-Timestamp` and
  `X-GoatNotify-Signature: sha256=<hex>`, an HMAC-SHA256 of `"{timestamp}.{body}"`.
- 2xx: sent. 408, 429 and 5xx, plus network errors: `RetryableError`, honoring `Retry-After`
  in seconds, capped at 300. Other statuses: `PermanentError` with the status and a truncated
  body. Error messages name the host only, never the full URL, because webhook URLs often
  embed credentials.
- `HttpTransport` is reused by HTTP-based email providers (see the Resend example).

## 10. Queues

```python
@dataclass(frozen=True, slots=True)
class NotificationJob[R: Notifiable]:
    notifier: Notifier
    notifiable: R
    notification: Notification[R]

    async def run(self) -> NotificationResult: ...

class Queue(Protocol):
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None: ...
```

- `AsyncioQueue(*, concurrency: int = 10)`: reference in-process queue. It schedules
  `job.run()` as tasks bounded by a semaphore and keeps strong references to them.
  Any exception from a background job is logged with `logger.exception` (hooks have already
  fired). `await queue.drain()` waits for pending jobs; `aclose()` drains then rejects new
  jobs. It is an async context manager and satisfies the runtime-checkable
  `ClosableQueue(Queue)` protocol, which adds `aclose()`.
- Out-of-process queues ignore `job.notifier` and rebuild their own notifier in the worker.
  They must serialize the notifiable and the notification; how is adapter-specific (§11).

## 11. Django integration

`goatnotify.django` is a Django app (`INSTALLED_APPS += ["goatnotify.django"]`, app label
`goatnotify`).

- `DjangoEmailTransport`: builds `EmailMultiAlternatives` and sends through the configured
  Django email backend via `asgiref.sync.sync_to_async`.
- `DjangoTemplateRenderer`: `render_to_string` via `sync_to_async`.
- Model `NotificationRecord` (table `goatnotify_notification`): `id` UUID, `recipient` generic
  foreign key (`content_type`, `object_id` as text), `kind`, `data` JSON, `created_at`,
  `read_at`. QuerySet: `for_recipient(obj)`, `unread()`, `mark_as_read()`. Migration `0001`.
- `DjangoNotificationStore`: implements `NotificationStore`; the notifiable must be a model
  instance, otherwise `ConfigurationError`.
- `NotifiableModel` mixin: `route_notification("email")` returns `self.email` when present.
- `DjangoTasksQueue(task_options=...)`: enqueues a `django.tasks` task. The notifiable must be
  a saved model instance (serialized as `app_label.model_name` and primary key); the
  notification must be a dataclass whose fields are JSON values or saved model instances
  (serialized as import path plus fields). Anything else raises `ConfigurationError` at
  enqueue time, not in the worker.
- `get_notifier()`: returns a per-process cached notifier. If the setting
  `GOATNOTIFY_NOTIFIER` names a factory (`"myproject.notifications.build_notifier"`), it is
  used; otherwise the default wires email (Django backend and templates,
  `DEFAULT_FROM_EMAIL`), database, webhook and `DjangoTasksQueue`. This is the global
  convenience, built on the injectable core.

## 12. FastAPI integration

- `attach(app, notifier)`: async context manager storing the notifier on `app.state` and closing
  its queue on shutdown when it is a `ClosableQueue`. `lifespan(notifier)` wraps it for
  `FastAPI(lifespan=...)`.
- `get_notifier(request) -> Notifier` and `NotifierDep = Annotated[Notifier, Depends(get_notifier)]`.

## 13. Testing support

`goatnotify.core.testing` ships fakes users can rely on in their own tests:
`MemoryTransport` (records `EmailMessage`s, can be scripted to raise), `MemoryStore`,
`MemoryHttpTransport` (records requests, returns scripted responses), and `no_sleep` for
instant retries.

## 14. Test suite

- Unit tests per package: dispatch, routing by MRO, multiple channels, concurrency and result
  order, skipped routes, retries and backoff, permanent and unexpected errors,
  `DeliveryFailed`, hooks (including failing hooks), `notify_sync` inside and outside a loop,
  mailable rendering and precedence, CC/BCC/reply-to, attachments, header injection, MIME
  output, SMTP error mapping against an in-process fake SMTP server built on `asyncio` streams,
  webhook statuses, signature and scheme checks, custom channel and transport,
  custom renderer, Jinja renderer, `AsyncioQueue` drain and close.
- Django tests with `pytest-django` on SQLite: transport through `locmem` backend, templates,
  store and queryset, migration check, Tasks queue with the immediate backend, serialization
  errors.
- FastAPI tests with `fastapi.testclient.TestClient`, which runs the lifespan.
- Isolation test: import `goatnotify` and `goatnotify.core` in a subprocess and assert that no
  framework module appears in `sys.modules`.
- Typing tests (`tests/typing`): fixtures that must pass and fixtures that must fail pyright,
  such as a `Channel[Mailable]` whose `send` takes a `WebhookMessage`, or
  `notify(user, Notification[Admin])`.
- No test touches the network or a real service.

## 15. Tooling and CI

Copied from GoatSEO and adapted:

- uv workspace, `uv_build` backend, `UV_LOCKED` in CI.
- Ruff with the GoatSEO rule set, line length 100; `ruff format`.
- Pyright strict with `extraPaths = [".typecheck"]`.
- pytest with `filterwarnings = ["error"]`, `asyncio_mode = "auto"` via `pytest-asyncio`.
- lefthook: ruff and actionlint on pre-commit, conventional commit check on commit-msg,
  pyright and pytest on pre-push.
- Workflows: `ci.yml` (lint, type-check, tests on Linux and macOS, build, twine check, clean
  install smoke test, strict consumer type-check), `security.yml` (CodeQL for Python and
  Actions, pip-audit, dependency review), `release-please.yml` calling reusable `release.yml`
  (PyPI trusted publishing), `docs.yml` (mkdocs-material to GitHub Pages).
- `release/config.json` and `release/.manifest.json`; internal pins carry
  `# x-release-please-version`.
- Dependabot for uv and GitHub Actions. All actions pinned by commit hash.
- MIT licence, repository `goatlabshq/goatnotify`.

## 16. Documentation and examples

`README.md` opens with "A modern, type-safe, framework-agnostic notification system for
Python." Docs (mkdocs-material): `index.md`, `getting-started.md`, `notifications.md`,
`mailables.md`, `channels.md`, `transports.md`, `notifiable.md`, `queues.md`, `retries.md`,
`templates.md`, `custom-channels.md`, `custom-transports.md`, `integrations/django.md`,
`integrations/fastapi.md`. Each package has a short `README.md`.

`examples/`: `app.py` (a plain asyncio application sending email, database and webhook
notifications with in-memory fakes), `discord_channel.py` (custom channel over
`HttpTransport`), `resend_transport.py` (custom `EmailTransport` over `HttpTransport`). They
are type-checked and executed by the test suite.

## 17. Delivery phases

1. Workspace, tooling, CI, facade and empty packages.
2. Core: errors, results, notification, channel, notifier, retry, hooks.
3. Email: mailable, rendering, mailer, MIME, SMTP transport, email channel.
4. Database and webhook channels, HTTP transport, testing fakes.
5. Queue protocol and `AsyncioQueue`.
6. Jinja renderer.
7. Django integration.
8. FastAPI integration.
9. Examples, documentation, typing tests, isolation test.
