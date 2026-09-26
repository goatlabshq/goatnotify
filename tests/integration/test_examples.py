import runpy
from pathlib import Path
from typing import Final

import pytest

EXAMPLES: Final = Path(__file__).parents[2] / "examples"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("app.py", "ok=True email='Welcome to Goat' stored='welcome' webhooks=1"),
        ("discord_channel.py", "discord requests=1"),
        ("resend_transport.py", "resend id=re_123"),
    ],
)
def test_examples_run(name: str, expected: str, capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(EXAMPLES / name), run_name="__main__")
    assert expected in capsys.readouterr().out
