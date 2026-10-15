import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final, cast

import pytest

API_URL: Final = os.environ.get("MAILPIT_API_URL", "")
SMTP_HOST: Final = os.environ.get("MAILPIT_SMTP_HOST", "127.0.0.1")
SMTP_PORT: Final = int(os.environ.get("MAILPIT_SMTP_PORT", "1025"))
POLL_SECONDS: Final = 5.0

requires_mailpit: Final = pytest.mark.skipif(
    not API_URL, reason="set MAILPIT_API_URL to run the Mailpit integration tests"
)


@dataclass(frozen=True, slots=True)
class Received:
    raw: dict[str, object]

    def addresses(self, field: str) -> list[str]:
        entries = cast("list[dict[str, str]] | None", self.raw[field]) or []
        return [entry["Address"] for entry in entries]

    def text(self, field: str) -> str:
        return cast("str", self.raw[field])

    def files(self, field: str) -> list[dict[str, object]]:
        return cast("list[dict[str, object]]", self.raw[field])


def _get(path: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{API_URL}{path}", timeout=5) as response:  # noqa: S310
        return cast("dict[str, object]", json.load(response))


def fetch(subject: str) -> Received:
    query = urllib.parse.quote(f'subject:"{subject}"')
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        found = cast("list[dict[str, str]]", _get(f"/api/v1/search?query={query}")["messages"])
        if found:
            return Received(_get(f"/api/v1/message/{found[0]['ID']}"))
        time.sleep(0.1)
    raise AssertionError(f"Mailpit never received {subject!r}")


def raw_source(received: Received) -> str:
    url = f"{API_URL}/api/v1/message/{received.raw['ID']}/raw"
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        return cast("bytes", response.read()).decode()
