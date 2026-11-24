import logging
from typing import Final
from uuid import UUID

from asgiref.sync import async_to_sync, sync_to_async

from django.core.exceptions import ObjectDoesNotExist
from goatnotify.core.results import DeliveryStatus, NotificationResult
from goatnotify.django.models import DeliveryReceipt
from goatnotify.django.serialization import Payload, load_notifiable, load_notification

logger: Final = logging.getLogger("goatnotify")
DONE: Final = frozenset({DeliveryStatus.SENT, DeliveryStatus.SKIPPED})


async def deliver(notifiable: Payload, notification: Payload, job_id: str | None = None) -> None:
    # Imported here because the default notifier builds a DjangoTasksQueue that enqueues a task
    # importing this module.
    from goatnotify.django.notifier import get_notifier  # noqa: PLC0415

    try:
        recipient = await sync_to_async(load_notifiable)(notifiable)
    except ObjectDoesNotExist:
        logger.warning(
            "Skipped a queued notification: its recipient %s no longer exists", notifiable
        )
        return
    instance = await sync_to_async(load_notification)(notification)
    job = None if job_id is None else UUID(job_id)
    delivered: set[int] = set() if job is None else await sync_to_async(_delivered_positions)(job)
    result = await get_notifier().notify(
        recipient, instance, raise_on_failure=False, skip=delivered
    )
    if job is not None:
        await sync_to_async(_record)(job, delivered, result)
    result.raise_for_failures()


def deliver_sync(notifiable: Payload, notification: Payload, job_id: str | None = None) -> None:
    async_to_sync(deliver)(notifiable, notification, job_id)


def _delivered_positions(job: UUID) -> set[int]:
    return set(DeliveryReceipt.objects.filter(job_id=job).values_list("position", flat=True))


def _record(job: UUID, already: set[int], result: NotificationResult) -> None:
    DeliveryReceipt.objects.bulk_create(
        [
            DeliveryReceipt(job_id=job, position=position)
            for position, delivery in enumerate(result.deliveries)
            if delivery.status in DONE and position not in already
        ],
        ignore_conflicts=True,
    )
