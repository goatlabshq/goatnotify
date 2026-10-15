class NotifiableModel:
    def route_notification(self, channel: str) -> str | None:
        if channel != "email":
            return None
        email = getattr(self, "email", None)
        return email if isinstance(email, str) and email else None
