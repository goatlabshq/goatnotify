import pytest
from django.core import checks
from django.test import override_settings

WORKER_TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
DUMMY_TASKS = {"default": {"BACKEND": "django.tasks.backends.dummy.DummyBackend"}}


def _goatnotify_errors() -> list[str]:
    return sorted(
        message.id or ""
        for message in checks.run_checks()
        if (message.id or "").startswith("goatnotify.")
    )


def test_a_worker_task_backend_is_valid() -> None:
    with override_settings(TASKS=WORKER_TASKS):
        assert _goatnotify_errors() == []


def test_an_immediate_task_backend_is_reported() -> None:
    assert _goatnotify_errors() == ["goatnotify.W001"]


def test_a_dummy_task_backend_is_not_reported() -> None:
    with override_settings(TASKS=DUMMY_TASKS):
        assert _goatnotify_errors() == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"GOATNOTIFY_NOTIFIER": 123}, "goatnotify.E001"),
        ({"GOATNOTIFY_NOTIFIER": "does.not.exist.build"}, "goatnotify.E002"),
        ({"GOATNOTIFY_NOTIFIER": "goatnotify_testapp.notifications.MEMORY"}, "goatnotify.E003"),
        ({"DEFAULT_FROM_EMAIL": "not an address"}, "goatnotify.E004"),
        (
            {"MAILERS": {"other": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}},
            "goatnotify.E005",
        ),
    ],
    ids=[
        "notifier-not-a-path",
        "notifier-not-importable",
        "notifier-not-callable",
        "bad-sender",
        "no-default-mailer",
    ],
)
def test_invalid_settings_are_reported_by_manage_check(
    overrides: dict[str, object], expected: str
) -> None:
    with override_settings(**{"TASKS": WORKER_TASKS, **overrides}):
        assert _goatnotify_errors() == [expected]


def test_a_custom_factory_skips_the_default_notifier_checks() -> None:
    with override_settings(
        GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_notifier",
        DEFAULT_FROM_EMAIL="not an address",
        MAILERS={"other": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    ):
        assert _goatnotify_errors() == []
