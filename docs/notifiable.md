# Notifiables

GoatNotify never assumes an ORM or a framework. A recipient is any object satisfying the
`Notifiable` protocol:

```python
class Notifiable(Protocol):
    def route_notification(self, channel: str) -> str | None: ...
```

`channel` is the channel name (`"email"`, `"webhook"`, or the name of a custom channel). Return
the address to use, or `None` when the recipient cannot be reached there: the delivery is then
reported as `skipped`, not failed.

The database channel does not call `route_notification()`: the store decides how to identify
the recipient.

## Dataclasses

```python
@dataclass
class User:
    email: str
    slack_webhook: str | None = None

    def route_notification(self, channel: str) -> str | None:
        match channel:
            case "email":
                return self.email
            case "webhook":
                return self.slack_webhook
            case _:
                return None
```

## Pydantic models

```python
from pydantic import BaseModel, EmailStr


class Customer(BaseModel):
    email: EmailStr

    def route_notification(self, channel: str) -> str | None:
        return str(self.email) if channel == "email" else None
```

## Django models

Mix in `NotifiableModel`: it routes the email channel to the model's `email` field and returns
`None` for the other channels. Override it to add routes.

```python
from django.db import models

from goatnotify.django import NotifiableModel


class Member(NotifiableModel, models.Model):
    email = models.EmailField()
    discord_webhook = models.URLField(blank=True)

    def route_notification(self, channel: str) -> str | None:
        if channel == "discord":
            return self.discord_webhook or None
        return super().route_notification(channel)
```

## SQLAlchemy models

```python
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None
```

## Objects you do not own

Wrap them in a small adapter instead of subclassing:

```python
@dataclass
class ContactRecipient:
    contact: CrmContact

    def route_notification(self, channel: str) -> str | None:
        return self.contact.primary_email if channel == "email" else None
```
