from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.mail import mailers
from django.core.mail.handler import DEFAULT_MAILER_ALIAS
from django.utils.module_loading import import_string
from goatnotify.core.errors import InvalidMessageError
from goatnotify.core.mail.message import Address

HINT_FACTORY = "Set GOATNOTIFY_NOTIFIER to the dotted path of a function returning a Notifier."


def check_settings(**_: object) -> list[CheckMessage]:
    path: object = getattr(settings, "GOATNOTIFY_NOTIFIER", None)
    if path is None:
        return _default_notifier_errors()
    if not isinstance(path, str):
        return [
            Error("GOATNOTIFY_NOTIFIER must be a string.", hint=HINT_FACTORY, id="goatnotify.E001")
        ]
    try:
        factory: object = import_string(path)
    except ImportError as error:
        return [
            Error(
                f"GOATNOTIFY_NOTIFIER cannot be imported: {error}",
                hint=HINT_FACTORY,
                id="goatnotify.E002",
            )
        ]
    if not callable(factory):
        return [
            Error(
                f"GOATNOTIFY_NOTIFIER {path!r} is not callable.",
                hint=HINT_FACTORY,
                id="goatnotify.E003",
            )
        ]
    return []


def _default_notifier_errors() -> list[CheckMessage]:
    errors: list[CheckMessage] = []
    try:
        Address.parse(settings.DEFAULT_FROM_EMAIL)
    except InvalidMessageError:
        errors.append(
            Error(
                f"DEFAULT_FROM_EMAIL {settings.DEFAULT_FROM_EMAIL!r} is not an email address.",
                hint='Use "noreply@example.com" or "Name <noreply@example.com>".',
                id="goatnotify.E004",
            )
        )
    if hasattr(settings, "MAILERS") and DEFAULT_MAILER_ALIAS not in mailers:
        errors.append(
            Error(
                "MAILERS has no 'default' mailer, which the default notifier sends email through.",
                hint="Add a 'default' entry to MAILERS or set GOATNOTIFY_NOTIFIER.",
                id="goatnotify.E005",
            )
        )
    return errors
