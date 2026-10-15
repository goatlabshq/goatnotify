from functools import cache
from typing import Final

from asgiref.sync import async_to_sync

from django.conf import settings
from django.utils.module_loading import import_string
from goatnotify.core.channels.database import DatabaseChannel
from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.channels.webhook import WebhookChannel
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.notification import Notifiable, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import NotificationResult
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify.django.store import DjangoNotificationStore
from goatnotify.django.templates import DjangoTemplateRenderer

WATCHED_SETTINGS: Final = frozenset(
    {"GOATNOTIFY_NOTIFIER", "DEFAULT_FROM_EMAIL", "MAILERS", "TASKS", "TEMPLATES"}
)


def default_notifier() -> Notifier:
    mailer = Mailer(
        DjangoEmailTransport(),
        sender=settings.DEFAULT_FROM_EMAIL,
        renderer=DjangoTemplateRenderer(),
    )
    return Notifier(
        [EmailChannel(mailer), DatabaseChannel(DjangoNotificationStore()), WebhookChannel()],
        queue=DjangoTasksQueue(),
    )


@cache
def get_notifier() -> Notifier:
    path: object = getattr(settings, "GOATNOTIFY_NOTIFIER", None)
    if path is None:
        return default_notifier()
    if not isinstance(path, str):
        raise ConfigurationError("GOATNOTIFY_NOTIFIER must be a dotted path to a factory")
    notifier: object = import_string(path)()
    if not isinstance(notifier, Notifier):
        raise ConfigurationError(f"{path} must return a Notifier")
    return notifier


def reset_notifier_on_setting_change(*, setting: str, **_: object) -> None:
    if setting in WATCHED_SETTINGS:
        get_notifier.cache_clear()


# Notifier.notify_sync() uses asyncio.run(), which deadlocks inside Django's thread-sensitive
# sync views (ASGI); async_to_sync lets the adapters' sync_to_async calls run inline instead.
def notify_sync[R: Notifiable](
    notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
) -> NotificationResult:
    return async_to_sync(get_notifier().notify)(
        notifiable, notification, raise_on_failure=raise_on_failure
    )


def enqueue_sync[R: Notifiable](notifiable: R, notification: Notification[R]) -> None:
    async_to_sync(get_notifier().enqueue)(notifiable, notification)
