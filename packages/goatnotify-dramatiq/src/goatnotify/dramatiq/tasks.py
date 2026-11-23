import dramatiq
from goatnotify.django.delivery import deliver_sync
from goatnotify.django.serialization import Payload
from goatnotify.dramatiq.queue import ACTOR_NAME


@dramatiq.actor(actor_name=ACTOR_NAME)
def deliver_notification(notifiable: Payload, notification: Payload, job_id: str) -> None:
    deliver_sync(notifiable, notification, job_id)
