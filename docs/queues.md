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
await queue.aclose()  # drain, then refuse new jobs
```

It is also an async context manager. A job that fails is logged with its traceback on the
`goatnotify` logger. Jobs are lost if the process dies: use it for fire-and-forget work
in web applications (the [FastAPI integration](integrations/fastapi.md) closes it on
shutdown), and a durable queue for anything that must survive a restart.

## Django Tasks

`DjangoTasksQueue` enqueues a `django.tasks` task. See [Django](integrations/django.md) for its
serialization rules.

## Other task systems

Adapters for Celery, RQ, Arq or Dramatiq follow the same shape: serialize at enqueue time,
rebuild and `notify()` in the worker.

```python
@celery_app.task
def deliver(user_id: int, plan: str) -> None:
    user = load_user(user_id)
    build_notifier().notify_sync(user, Welcome(plan=plan))


class CeleryQueue:
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        user, notification = job.notifiable, job.notification
        if not isinstance(user, User) or not isinstance(notification, Welcome):
            raise ConfigurationError("CeleryQueue only knows how to send Welcome to users")
        deliver.delay(user.id, notification.plan)
```

Validate everything at enqueue time: an error raised there reaches the caller, while an error in
the worker only reaches the logs.
