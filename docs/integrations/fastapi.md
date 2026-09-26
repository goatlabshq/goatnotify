# FastAPI

```bash
pip install "goatnotify[fastapi]"
```

## Setup

Build the notifier once and attach it with the lifespan:

```python
from fastapi import FastAPI

from goatnotify import AsyncioQueue, EmailChannel, Mailer, Notifier, SmtpTransport
from goatnotify.fastapi import NotifierDep, lifespan

notifier = Notifier(
    [EmailChannel(Mailer(SmtpTransport("smtp.example.com"), sender="noreply@example.com"))],
    queue=AsyncioQueue(),
)
app = FastAPI(lifespan=lifespan(notifier))


@app.post("/signup")
async def signup(payload: SignupForm, notifier: NotifierDep) -> dict[str, str]:
    user = await create_user(payload)
    await notifier.enqueue(user, Welcome())
    return {"status": "ok"}
```

`NotifierDep` is `Annotated[Notifier, Depends(get_notifier)]`. Using it without the lifespan
raises `ConfigurationError`.

## Background delivery

With an `AsyncioQueue`, `enqueue()` returns immediately and the notification is delivered in the
background. On shutdown, the lifespan closes the queue, which waits for pending notifications.

## Composing with your own lifespan

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from goatnotify.fastapi import attach


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    async with database.connect(), attach(app, notifier):
        yield


app = FastAPI(lifespan=app_lifespan)
```
