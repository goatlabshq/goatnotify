from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goatnotify.django.notifiable import NotifiableModel
    from goatnotify.django.notifier import enqueue_sync, get_notifier, notify_sync

__all__ = ["NotifiableModel", "enqueue_sync", "get_notifier", "notify_sync"]

_MODULES = {
    "NotifiableModel": "goatnotify.django.notifiable",
    "enqueue_sync": "goatnotify.django.notifier",
    "get_notifier": "goatnotify.django.notifier",
    "notify_sync": "goatnotify.django.notifier",
}


if not TYPE_CHECKING:
    # Django imports this package before the app registry is ready, and the notifier loads models.
    def __getattr__(name: str) -> object:
        module = _MODULES.get(name)
        if module is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        return getattr(import_module(module), name)
