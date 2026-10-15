import uuid
from datetime import datetime
from typing import Self

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class NotificationRecordQuerySet(models.QuerySet["NotificationRecord"]):
    def for_recipient(self, recipient: models.Model) -> Self:
        return self.filter(
            content_type=ContentType.objects.get_for_model(recipient),
            object_id=str(recipient.pk),
        )

    def unread(self) -> Self:
        return self.filter(read_at__isnull=True)

    def mark_as_read(self) -> int:
        return self.unread().update(read_at=timezone.now())


class NotificationRecordManager(models.Manager["NotificationRecord"]):
    def get_queryset(self) -> NotificationRecordQuerySet:
        return NotificationRecordQuerySet(self.model, using=self._db)

    def for_recipient(self, recipient: models.Model) -> NotificationRecordQuerySet:
        return self.get_queryset().for_recipient(recipient)


class NotificationRecord(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    content_type: models.ForeignKey[ContentType, ContentType] = models.ForeignKey(
        ContentType, on_delete=models.CASCADE
    )
    content_type_id: int
    object_id: models.CharField[str, str] = models.CharField(max_length=255)
    recipient = GenericForeignKey("content_type", "object_id")
    kind: models.CharField[str, str] = models.CharField(max_length=255)
    data = models.JSONField(default=dict)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(
        default=timezone.now
    )
    read_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )

    objects = NotificationRecordManager()

    class Meta:
        db_table = "goatnotify_notification"
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("content_type", "object_id", "-created_at"),
                name="goatnotify_recipient_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.kind} for {self.content_type_id}:{self.object_id}"
