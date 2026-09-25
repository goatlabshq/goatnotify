from django.db import models

from goatnotify.django.notifiable import NotifiableModel


class Member(NotifiableModel, models.Model):
    email: models.EmailField[str, str] = models.EmailField(blank=True)
    webhook_url: models.URLField[str, str] = models.URLField(blank=True)

    def route_notification(self, channel: str) -> str | None:
        if channel == "webhook":
            return self.webhook_url or None
        return super().route_notification(channel)
