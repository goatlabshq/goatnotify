"""NotificationStore persisting to the NotificationRecord model."""

from asgiref.sync import sync_to_async

from django.contrib.contenttypes.models import ContentType
from django.db import models
from goatnotify.core.channels.database import StoredNotification
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable
from goatnotify.django.models import NotificationRecord


class DjangoNotificationStore:
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        if not isinstance(notifiable, models.Model) or notifiable.pk is None:
            kind = type(notifiable).__qualname__
            raise ConfigurationError(
                f"DjangoNotificationStore needs a saved model instance, not {kind}"
            )
        await sync_to_async(self._store)(notifiable, record)

    def _store(self, recipient: models.Model, record: StoredNotification) -> None:
        NotificationRecord.objects.create(
            id=record.id,
            content_type=ContentType.objects.get_for_model(recipient),
            object_id=str(recipient.pk),
            kind=record.kind,
            data=dict(record.data),
            created_at=record.created_at,
        )
