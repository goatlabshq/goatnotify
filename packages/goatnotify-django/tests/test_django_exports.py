import subprocess
import sys

import pytest

import goatnotify.django
from goatnotify.django import notifiable, notifier


def test_the_package_reexports_the_common_helpers() -> None:
    assert goatnotify.django.NotifiableModel is notifiable.NotifiableModel
    assert goatnotify.django.get_notifier is notifier.get_notifier
    assert goatnotify.django.notify_sync is notifier.notify_sync
    assert goatnotify.django.enqueue_sync is notifier.enqueue_sync


@pytest.mark.parametrize("name", ["missing", "DjangoTasksQueue"])
def test_other_names_raise_attribute_error(name: str) -> None:
    with pytest.raises(AttributeError, match=name):
        getattr(goatnotify.django, name)


def test_the_package_imports_without_configured_settings() -> None:
    subprocess.run([sys.executable, "-c", "import goatnotify.django"], check=True)
