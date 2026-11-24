from django.tasks import task
from goatnotify.core._json import JsonValue
from goatnotify.django.delivery import deliver


@task
async def deliver_notification(
    notifiable: dict[str, JsonValue],
    notification: dict[str, JsonValue],
    job_id: str | None = None,
) -> None:
    await deliver(notifiable, notification, job_id)
