# Queues

`notify()` delivers immediately. `enqueue()` hands the notification to a queue instead:

```python
notifier = Notifier(channels, queue=AsyncioQueue())
await notifier.enqueue(user, Welcome())
```

`enqueue()` without a configured queue raises `ConfigurationError`.

## The Queue protocol

```python
class Queue(Protocol):
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None: ...
```

A `NotificationJob` carries the notifier, the recipient and the notification; `await job.run()`
delivers it. In-process queues call `run()`. Out-of-process queues serialize the recipient and
the notification, and rebuild both, plus a notifier, in the worker.

## AsyncioQueue

The reference implementation runs jobs as asyncio tasks in the current process:

```python
queue = AsyncioQueue(concurrency=10)
notifier = Notifier(channels, queue=queue)

await notifier.enqueue(user, Welcome())
await queue.drain()  # wait for pending jobs
await queue.drain(timeout=30)  # then cancel and log whatever is still running
await queue.aclose()  # drain, then refuse new jobs (also takes timeout=)
```

It is also an async context manager. A job that fails is logged with its traceback on the
`goatnotify` logger. Jobs are lost if the process dies: use it for fire-and-forget work
in web applications (the [FastAPI integration](integrations/fastapi.md) drains it on
shutdown), and a durable queue for anything that must survive a restart.

## Django Tasks

`DjangoTasksQueue` enqueues a `django.tasks` task. See [Django](integrations/django.md) for its
serialization rules.

## Celery, Dramatiq and RQ

For Django projects that already run one of these task systems, `goatnotify-celery`,
`goatnotify-dramatiq` and `goatnotify-rq` each ship a queue and its worker task. They serialize
jobs like `DjangoTasksQueue` and share its delivery receipts (the `goatnotify_delivery_receipt`
table): when the task system runs a job again, after a retry or a redelivery, messages already
sent or skipped are not sent twice.

Hand the queue to `default_notifier()` from [your own notifier factory](integrations/django.md#the-notifier):

```python
# settings.py
GOATNOTIFY_NOTIFIER = "myproject.notifications.build_notifier"
```

### Celery

```bash
pip install "goatnotify[django,celery]"
```

```python
# settings.py
INSTALLED_APPS = [..., "goatnotify.django", "goatnotify.celery"]

# myproject/notifications.py
from goatnotify import Notifier
from goatnotify.celery import CeleryQueue
from goatnotify.django.notifier import default_notifier
from myproject.celery import app


def build_notifier() -> Notifier:
    return default_notifier(queue=CeleryQueue(app, queue="notifications", priority=None))
```

`app.autodiscover_tasks()` registers the `goatnotify.deliver` task through the
`goatnotify.celery` app. The task acknowledges late and is redelivered if its worker dies.
Celery does not retry a failed task on its own; a task that is re-sent, by hand or by a
monitoring tool, only delivers what failed. With `task_always_eager`, as in a test suite, the
task runs inline and nothing reaches the broker.

### Dramatiq

```bash
pip install "goatnotify[django,dramatiq]"
```

```python
# settings.py
INSTALLED_APPS = [..., "django_dramatiq", "goatnotify.django", "goatnotify.dramatiq"]

# myproject/notifications.py
from goatnotify import Notifier
from goatnotify.django.notifier import default_notifier
from goatnotify.dramatiq import DramatiqQueue


def build_notifier() -> Notifier:
    return default_notifier(queue=DramatiqQueue(queue_name="notifications", max_retries=5))
```

[django_dramatiq](https://pypi.org/project/django-dramatiq/) discovers the `goatnotify.deliver`
actor in `goatnotify.dramatiq.tasks`. Dramatiq retries a failed message with backoff (20 times
unless `max_retries` says otherwise), and every retry only delivers what failed. Enqueueing
before the actor is registered raises `ConfigurationError`.

### RQ

```bash
pip install "goatnotify[django,rq]"
```

```python
# myproject/notifications.py
from redis import Redis
from rq import Retry

from goatnotify import Notifier
from goatnotify.django.notifier import default_notifier
from goatnotify.rq import RQQueue


def build_notifier() -> Notifier:
    queue = RQQueue(Redis(), queue="notifications", retry=Retry(max=3, interval=[10, 60, 300]))
    return default_notifier(queue=queue)
```

The worker runs `goatnotify.rq.tasks.deliver_notification`, so it needs Django set up, as
[django-rq](https://pypi.org/project/django-rq/)'s `rqworker` command does. No app has to be
added to `INSTALLED_APPS`.

## Other task systems

Adapters for Arq or another task system follow the same shape: serialize at enqueue time,
rebuild and `notify()` in the worker.

```python
@arq_task
async def deliver(ctx: dict[str, object], user_id: int, plan: str) -> None:
    user = await load_user(user_id)
    await build_notifier().notify(user, Welcome(plan=plan))


class ArqQueue:
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        user, notification = job.notifiable, job.notification
        if not isinstance(user, User) or not isinstance(notification, Welcome):
            raise ConfigurationError("ArqQueue only knows how to send Welcome to users")
        await redis.enqueue_job("deliver", user.id, notification.plan)
```

To make your own worker's retries idempotent, persist which positions of `messages()` were
delivered and pass them back: `await notifier.notify(recipient, notification, skip={0, 2})`
reports those messages as skipped ("already delivered") without sending them again.

Validate everything at enqueue time: an error raised there reaches the caller, while an error in
the worker only reaches the logs.
