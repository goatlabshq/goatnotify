import tempfile
from collections.abc import Iterator
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from mailpit import SMTP_HOST, SMTP_PORT

TEMPLATES = {
    "emails/welcome.html": "<p>Welcome {{ name }}</p>",
    "emails/welcome.txt": "Welcome {{ name }}",
}

if not settings.configured:
    # A file database, because sync_to_async threads would each see their own :memory: one.
    settings.configure(
        SECRET_KEY="goatnotify-tests",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django_tasks_db",
            "goatnotify.django",
            "goatnotify_testapp",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(Path(tempfile.mkdtemp()) / "db.sqlite3"),
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        MAILERS={
            "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
            "broken": {"BACKEND": "goatnotify_testapp.mail.BrokenBackend"},
            "handshake": {"BACKEND": "goatnotify_testapp.mail.HandshakeBackend"},
            "mailpit": {
                "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "OPTIONS": {"host": SMTP_HOST, "port": SMTP_PORT, "timeout": 10},
            },
        },
        DEFAULT_FROM_EMAIL="Goat <noreply@goat.dev>",
        TASKS={
            "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
            "database": {"BACKEND": "django_tasks_db.DatabaseBackend"},
        },
        USE_TZ=True,
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {"loaders": [("django.template.loaders.locmem.Loader", TEMPLATES)]},
            }
        ],
    )
    django.setup()
    call_command("migrate", run_syncdb=True, verbosity=0)


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    from goatnotify_testapp.models import Member

    from goatnotify.django.models import NotificationRecord
    from goatnotify.django.notifier import get_notifier

    get_notifier.cache_clear()
    mail.outbox = []
    yield
    NotificationRecord.objects.all().delete()
    Member.objects.all().delete()
