"""Framework-agnostic core of GoatNotify."""

from goatnotify.core import events
from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.channels.database import (
    DatabaseChannel,
    DatabaseMessage,
    NotificationStore,
    StoredNotification,
)
from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.channels.webhook import WebhookChannel, WebhookMessage
from goatnotify.core.errors import (
    ConfigurationError,
    DeliveryError,
    DeliveryFailed,
    InvalidMessageError,
    NotificationError,
    PermanentError,
    RetryableError,
    SkipDelivery,
)
from goatnotify.core.events import Event, Hook
from goatnotify.core.http import HttpRequest, HttpResponse, HttpTransport, UrllibTransport
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address, Attachment, EmailMessage
from goatnotify.core.mail.mime import to_mime
from goatnotify.core.mail.smtp import SmtpTransport
from goatnotify.core.mail.transport import EmailTransport
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import AsyncioQueue, ClosableQueue, NotificationJob, Queue
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult
from goatnotify.core.retry import NO_RETRY, Backoff, ExponentialBackoff, RetryPolicy
from goatnotify.core.templates import TemplateRenderer

__all__ = [
    "NO_RETRY",
    "Address",
    "AsyncioQueue",
    "Attachment",
    "Backoff",
    "Channel",
    "ClosableQueue",
    "ConfigurationError",
    "DatabaseChannel",
    "DatabaseMessage",
    "DeliveryError",
    "DeliveryFailed",
    "DeliveryResult",
    "DeliveryStatus",
    "EmailChannel",
    "EmailMessage",
    "EmailTransport",
    "Event",
    "ExponentialBackoff",
    "Hook",
    "HttpRequest",
    "HttpResponse",
    "HttpTransport",
    "InvalidMessageError",
    "JsonValue",
    "Mailable",
    "Mailer",
    "Message",
    "Notifiable",
    "Notification",
    "NotificationError",
    "NotificationJob",
    "NotificationResult",
    "NotificationStore",
    "Notifier",
    "PermanentError",
    "Queue",
    "RetryPolicy",
    "RetryableError",
    "SkipDelivery",
    "SmtpTransport",
    "StoredNotification",
    "TemplateRenderer",
    "UrllibTransport",
    "WebhookChannel",
    "WebhookMessage",
    "events",
    "to_mime",
]
