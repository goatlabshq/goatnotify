# Django

```bash
pip install "goatnotify[django]"
```

The integration requires Django 6.1 or newer.

## Setup

```python
INSTALLED_APPS = ["django.contrib.contenttypes", "django_tasks_db", "goatnotify.django", ...]

MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend", "OPTIONS": {...}},
}
DEFAULT_FROM_EMAIL = "Goat <noreply@example.com>"

TASKS = {
    "default": {"BACKEND": "django_tasks_db.DatabaseBackend"},
}
```

`enqueue()` needs a `TASKS` backend with a worker, such as
[django-tasks-db](https://pypi.org/project/django-tasks-db/). Django itself only
ships `ImmediateBackend`, which runs the task inline, and `DummyBackend`, which never runs it.
With Celery, RQ or another task system, write a small queue instead (see
[Other task systems](../queues.md#other-task-systems)) and return it from
[your own notifier](#the-notifier).

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
from goatnotify.django import get_notifier


async def signup(request: HttpRequest) -> HttpResponse:
    member = await Member.objects.acreate(email=request.POST["email"])
    await get_notifier().notify(member, Welcome(plan="free"))
    ...
```

## Synchronous code

In synchronous views, signal handlers and management commands, use the helpers of
`goatnotify.django` instead of `Notifier.notify_sync()`:

```python
from goatnotify.django import enqueue_sync, notify_sync


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

## System checks

`manage.py check` (and every management command) validates the configuration, so mistakes
surface at startup instead of at the first send:

| Id | Problem |
|---|---|
| `goatnotify.E001` | `GOATNOTIFY_NOTIFIER` is not a string |
| `goatnotify.E002` | `GOATNOTIFY_NOTIFIER` cannot be imported |
| `goatnotify.E003` | `GOATNOTIFY_NOTIFIER` is not callable |
| `goatnotify.E004` | `DEFAULT_FROM_EMAIL` is not an email address (default notifier only) |
| `goatnotify.E005` | `MAILERS` has no `default` mailer (default notifier only) |
| `goatnotify.W001` | the default `TASKS` backend is `ImmediateBackend`, so `enqueue()` sends inline (default notifier only) |

Silence `goatnotify.W001` with `SILENCED_SYSTEM_CHECKS` when sending inline is intended, for
example in tests.

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
- the notification must be a **module-level dataclass**, defined in an installed app, whose
  fields are saved model instances or plain JSON: `str`, `int`, `float`, `bool`, `None`, `list`
  and `dict` with string keys. Tuples, enums and other subclasses are refused because they would
  come back as different types in the worker.

```python
@dataclass
class Welcome(Notification[Member]):
    plan: str
    referrer: Member | None = None

    def messages(self, member: Member) -> Iterable[Message]:
        yield WelcomeMail(member, self.plan)
```

Anything else raises `ConfigurationError` when you call `enqueue()`, not later in the worker.

### Retries and deleted recipients

Each queued notification carries a job id. When the worker delivers it, every message that was
sent (or had nothing to send) gets a `DeliveryReceipt` row. If the task is run again with the
same arguments, after a failure or by a backend that retries, messages with a receipt are
reported as `skipped` ("already delivered") and only the failed ones are retried. A process that
dies between sending and writing the receipt can still deliver a message twice: delivery is at
least once, never silently lost.

Receipts are never deleted by GoatNotify; prune old rows from `goatnotify_delivery_receipt` with
your task results. A recipient deleted before the worker runs is logged on the `goatnotify`
logger and the task ends successfully, without sending anything.
`DjangoTasksQueue(queue_name=..., priority=..., backend=...)` forwards those options to the task.

Inside a transaction, a worker may run the task before the transaction commits and not find the
recipient yet. Enqueue after the commit:

```python
from django.db import transaction

with transaction.atomic():
    member = Member.objects.create(email=email)
    transaction.on_commit(lambda: enqueue_sync(member, Welcome(plan="free")))
```
