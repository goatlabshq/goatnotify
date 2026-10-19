import logging
from typing import Final

from asgiref.sync import sync_to_async

from django.core.exceptions import ObjectDoesNotExist
from django.tasks import task
from goatnotify.core._json import JsonValue
from goatnotify.django.serialization import load_notifiable, load_notification

logger: Final = logging.getLogger("goatnotify")


@task
async def deliver_notification(
    notifiable: dict[str, JsonValue], notification: dict[str, JsonValue]
) -> None:
    # Imported here because the default notifier builds a DjangoTasksQueue that enqueues this task.
    from goatnotify.django.notifier import get_notifier  # noqa: PLC0415

    try:
        recipient = await sync_to_async(load_notifiable)(notifiable)
    except ObjectDoesNotExist:
        logger.warning(
            "Skipped a queued notification: its recipient %s no longer exists", notifiable
        )
        return
    instance = await sync_to_async(load_notification)(notification)
    await get_notifier().notify(recipient, instance)
