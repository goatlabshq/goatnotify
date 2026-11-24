from celery import shared_task
from goatnotify.celery.queue import TASK_NAME
from goatnotify.django.delivery import deliver_sync
from goatnotify.django.serialization import Payload


# Late acknowledgement redelivers a job whose worker died; the receipts make that harmless.
@shared_task(name=TASK_NAME, acks_late=True, reject_on_worker_lost=True)
def deliver_notification(notifiable: Payload, notification: Payload, job_id: str) -> None:
    deliver_sync(notifiable, notification, job_id)
