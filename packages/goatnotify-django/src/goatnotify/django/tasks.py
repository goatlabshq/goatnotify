from asgiref.sync import sync_to_async

from django.tasks import task
from goatnotify.core._json import JsonValue
from goatnotify.django.serialization import load_notifiable, load_notification


@task
async def deliver_notification(
    notifiable: dict[str, JsonValue], notification: dict[str, JsonValue]
) -> None:
    # Imported here because the default notifier builds a DjangoTasksQueue that enqueues this task.
    from goatnotify.django.notifier import get_notifier  # noqa: PLC0415

    recipient = await sync_to_async(load_notifiable)(notifiable)
    instance = await sync_to_async(load_notification)(notification)
    await get_notifier().notify(recipient, instance)
