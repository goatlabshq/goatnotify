from django.apps import AppConfig
from django.core.signals import setting_changed


class GoatNotifyConfig(AppConfig):
    name = "goatnotify.django"
    label = "goatnotify"
    verbose_name = "GoatNotify"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Imported late: the notifier module loads models, which requires a ready app registry.
        from goatnotify.django.notifier import reset_notifier_on_setting_change  # noqa: PLC0415

        setting_changed.connect(reset_notifier_on_setting_change)
