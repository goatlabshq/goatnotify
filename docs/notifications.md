# Notifications

A notification is a class deriving from `Notification[R]`, where `R` is the recipient type. Its
single method, `messages()`, yields the messages to deliver.

```python
from collections.abc import Iterable

from goatnotify import DatabaseMessage, Message, Notification, WebhookMessage


class InvoicePaid(Notification[User]):
    def __init__(self, invoice: Invoice) -> None:
        self.invoice = invoice

    def messages(self, user: User) -> Iterable[Message]:
        yield InvoicePaidMail(user, self.invoice)
        yield DatabaseMessage(kind="invoice.paid", data={"invoice": self.invoice.number})
        if user.wants_slack_alerts:
            yield WebhookMessage(payload={"text": f"Invoice {self.invoice.number} paid"})
```

Yielding nothing sends nothing, which replaces Laravel's `shouldSend()`.

## Routing by message type

The `Notifier` delivers each message through the channel registered for its type, walking the
class hierarchy: a `WelcomeMail(Mailable)` goes to the channel registered for `Mailable`.

- Two channels for the same message type are rejected when the notifier is built.
- A message no channel handles raises `ConfigurationError` **before anything is sent**, so a
  misconfiguration never results in half a notification.

## Concurrency and order

The messages of one notification are delivered concurrently. `result.deliveries` keeps the order
in which `messages()` yielded them, and a failing delivery never prevents the others.

## Generic notifications

`Notification` is contravariant in its recipient type. A `Notification[Notifiable]` accepts any
recipient, while a `Notification[Admin]` sent to a plain `User` is a type error:

```python
from goatnotify import Notifiable


class Maintenance(Notification[Notifiable]):
    def messages(self, recipient: Notifiable) -> Iterable[Message]:
        yield MaintenanceMail()


await notifier.notify(user, Maintenance())  # fine
await notifier.notify(user, AdminOnly())  # rejected by Pyright
```

## Sending

| Method | Use |
|---|---|
| `await notifier.notify(recipient, notification)` | Deliver now and return a `NotificationResult` |
| `notifier.notify_sync(recipient, notification)` | Same, from synchronous code without framework-managed threads |
| `await notifier.enqueue(recipient, notification)` | Hand over to the configured [queue](queues.md) |

`notify()` and `notify_sync()` accept `raise_on_failure=False` to get the result instead of a
`DeliveryFailed` exception.
