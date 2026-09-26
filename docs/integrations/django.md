# Django

```bash
pip install "goatnotify[django]"
```

The integration requires Django 6.1 or newer.

## Setup

```python
INSTALLED_APPS = ["django.contrib.contenttypes", "goatnotify.django", ...]

MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend", "OPTIONS": {...}},
}
DEFAULT_FROM_EMAIL = "Goat <noreply@example.com>"

TASKS = {
    "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
}
```

Then create the notification table:

```bash
python manage.py migrate goatnotify
```

## The notifier

`get_notifier()` returns a notifier built once per process:

| Channel | Backed by |
|---|---|
| `EmailChannel` | `DjangoEmailTransport` (your `MAILERS`), `DjangoTemplateRenderer`, `DEFAULT_FROM_EMAIL` |
| `DatabaseChannel` | `DjangoNotificationStore` |
| `WebhookChannel` | `UrllibTransport` |
| queue | `DjangoTasksQueue` |

```python
from goatnotify.django.notifier import get_notifier


async def signup(request: HttpRequest) -> HttpResponse:
    member = await Member.objects.acreate(email=request.POST["email"])
    await get_notifier().notify(member, Welcome(plan="free"))
    ...
```

## Synchronous code

In synchronous views, signal handlers and management commands, use the helpers of
`goatnotify.django.notifier` instead of `Notifier.notify_sync()`:

```python
from goatnotify.django.notifier import enqueue_sync, notify_sync


def signup_sync(request: HttpRequest) -> HttpResponse:
    member = Member.objects.create(email=request.POST["email"])
    notify_sync(member, Welcome(plan="free"))
    enqueue_sync(member, Digest(period="weekly"))
    ...
```

Under ASGI, Django runs synchronous views in a thread-sensitive executor. `Notifier.notify_sync()`
starts its own event loop there, and the Django adapters (ORM store, email, templates) then wait
for that same thread, which never frees up. The helpers go through `async_to_sync`, which runs
those adapter calls in the view's own thread.

To build it yourself, point `GOATNOTIFY_NOTIFIER` at a factory:

```python
GOATNOTIFY_NOTIFIER = "myproject.notifications.build_notifier"
```

```python
def build_notifier() -> Notifier:
    mailer = Mailer(
        DjangoEmailTransport(mailer="transactional"),
        sender=settings.DEFAULT_FROM_EMAIL,
        renderer=DjangoTemplateRenderer(),
    )
    return Notifier(
        [EmailChannel(mailer), DatabaseChannel(DjangoNotificationStore()), DiscordChannel()],
        retry=RetryPolicy(max_attempts=5),
        queue=DjangoTasksQueue(queue_name="notifications"),
    )
```

The cached notifier is rebuilt when a test overrides `GOATNOTIFY_NOTIFIER`,
`DEFAULT_FROM_EMAIL`, `MAILERS`, `TASKS` or `TEMPLATES`.

## Recipients

Mix `NotifiableModel` into your models (see [Notifiables](../notifiable.md)).

## Stored notifications

`DjangoNotificationStore` writes `NotificationRecord` rows (table `goatnotify_notification`):
`id`, a generic relation to the recipient, `kind`, `data`, `created_at` and `read_at`.

```python
from goatnotify.django.models import NotificationRecord

unread = NotificationRecord.objects.for_recipient(member).unread()
count = unread.count()
unread.mark_as_read()
```

## Django Tasks

`await notifier.enqueue(member, notification)` with `DjangoTasksQueue` enqueues the
`goatnotify.django.tasks.deliver_notification` task. Task arguments must be JSON, so:

- the recipient must be a **saved model instance** (it is sent as its model label and primary
  key and reloaded in the worker);
- the notification must be a **module-level dataclass** whose fields are JSON values or saved
  model instances.

```python
@dataclass
class Welcome(Notification[Member]):
    plan: str
    referrer: Member | None = None

    def messages(self, member: Member) -> Iterable[Message]:
        yield WelcomeMail(member, self.plan)
```

Anything else raises `ConfigurationError` when you call `enqueue()`, not later in the worker.
`DjangoTasksQueue(queue_name=..., priority=..., backend=...)` forwards those options to the task.
