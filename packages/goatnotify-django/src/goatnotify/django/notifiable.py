"""Notifiable mixin for Django models."""


class NotifiableModel:
    """Routes the email channel to the model's `email` attribute; override for other channels."""

    def route_notification(self, channel: str) -> str | None:
        if channel != "email":
            return None
        email = getattr(self, "email", None)
        return email if isinstance(email, str) and email else None
