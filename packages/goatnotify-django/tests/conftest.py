from collections.abc import Iterator

import pytest
from goatnotify_testapp.bootstrap import configure, reset_state

configure()


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    reset_state()
    yield
    reset_state()
