import importlib

import pytest

PORTIONS = (
    "goatnotify",
    "goatnotify.core",
    "goatnotify.jinja",
    "goatnotify.django",
    "goatnotify.fastapi",
)


@pytest.mark.parametrize("module", PORTIONS)
def test_every_namespace_portion_is_importable(module: str) -> None:
    assert importlib.import_module(module).__doc__
