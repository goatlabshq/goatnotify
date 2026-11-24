from goatnotify.django.delivery import deliver_sync
from goatnotify.django.serialization import Payload


def deliver_notification(notifiable: Payload, notification: Payload, job_id: str) -> None:
    deliver_sync(notifiable, notification, job_id)
