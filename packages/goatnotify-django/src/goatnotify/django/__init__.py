from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goatnotify.django.notifiable import NotifiableModel
    from goatnotify.django.notifier import enqueue_sync, get_notifier, notify_sync

__all__ = ["NotifiableModel", "enqueue_sync", "get_notifier", "notify_sync"]

_NOTIFIER_HELPERS = frozenset({"enqueue_sync", "get_notifier", "notify_sync"})


if not TYPE_CHECKING:
    # Django imports this package before the app registry is ready, and the notifier loads models.
    def __getattr__(name: str) -> object:
        if name == "NotifiableModel":
            from goatnotify.django.notifiable import NotifiableModel  # noqa: PLC0415

            return NotifiableModel
        if name in _NOTIFIER_HELPERS:
            from goatnotify.django import notifier  # noqa: PLC0415

            return getattr(notifier, name)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
