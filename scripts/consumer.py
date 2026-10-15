from collections.abc import Iterable

from fastapi import FastAPI

from goatnotify import (
    AsyncioQueue,
    DatabaseChannel,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notifiable,
    Notification,
    Notifier,
    RetryPolicy,
    SmtpTransport,
    WebhookChannel,
)
from goatnotify.core.testing import MemoryStore
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.notifiable import NotifiableModel
from goatnotify.django.notifier import get_notifier
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify.django.templates import DjangoTemplateRenderer
from goatnotify.fastapi import NotifierDep, lifespan
from goatnotify.jinja import JinjaRenderer


class Hello(Mailable):
    subject = "Hello"

    def template(self) -> str | None:
        return "hello.html"


class Greeting(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield Hello()


notifier = Notifier(
    [
        EmailChannel(
            Mailer(
                SmtpTransport("smtp.example.com", username="u", password="p"),
                sender="noreply@example.com",
                renderer=JinjaRenderer.from_directory("templates"),
            )
        ),
        DatabaseChannel(MemoryStore()),
        WebhookChannel(secret="s"),
    ],
    retry=RetryPolicy(max_attempts=4),
    queue=AsyncioQueue(),
)
app = FastAPI(lifespan=lifespan(notifier))


@app.post("/hello")
async def hello(injected: NotifierDep) -> None:
    await injected.enqueue(NotifiableModel(), Greeting())


django_parts = (DjangoEmailTransport(), DjangoTemplateRenderer(), DjangoTasksQueue(), get_notifier)
