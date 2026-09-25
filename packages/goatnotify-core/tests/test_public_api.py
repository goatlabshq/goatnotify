import goatnotify
import goatnotify.core

PUBLIC = {
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
}


def test_the_core_exports_the_public_api() -> None:
    assert set(goatnotify.core.__all__) == PUBLIC
    assert all(hasattr(goatnotify.core, name) for name in PUBLIC)


def test_the_facade_re_exports_the_core() -> None:
    assert set(goatnotify.__all__) == PUBLIC
    assert all(getattr(goatnotify, name) is getattr(goatnotify.core, name) for name in PUBLIC)
