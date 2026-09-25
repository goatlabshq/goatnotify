# GoatNotify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build GoatNotify, a type-safe, async-first, framework-agnostic notification system for Python, as a uv workspace of five published packages.

**Architecture:** A notification yields typed `Message` objects; the `Notifier` routes each message to the `Channel` registered for its type (walking the MRO), applies the retry policy, fires hooks and returns a `NotificationResult`. Channels own their transports or stores. The core uses only the standard library; Jinja, Django and FastAPI adapters live in separate packages sharing the `goatnotify` namespace.

**Tech Stack:** Python 3.14, uv workspace with `uv_build`, pytest + pytest-asyncio, pyright strict, ruff, lefthook, Django 6.x (`django.tasks`), FastAPI, Jinja2, mkdocs-material, GitHub Actions with release-please.

**Spec:** `docs/superpowers/specs/2026-09-25-goatnotify-design.md`

## Global Constraints

- Python `>=3.14` everywhere (`requires-python = ">=3.14"`, ruff `target-version = "py314"`, pyright `pythonVersion = "3.14"`).
- `goatnotify-core` has **no** runtime dependencies and never imports `django`, `fastapi`, `starlette`, `jinja2`, `sqlalchemy`, `celery` or `httpx`.
- Pyright strict must pass on `packages`, `tests`, `scripts`, `examples`. `Any` only in `Channel[Any]` (notifier routing table) and `Notification[Any]` (results, events, jobs), plus Django serialization boundaries.
- Everything in the repository is written in English. Never use the em dash character anywhere (code, docs, commits).
- Comments explain a non-obvious *why* only, two lines maximum. No per-field docstrings. One-line docstrings on public classes and modules are allowed.
- Commits: atomic, conventional (`type: description`), single subject line, no body, **no `Co-Authored-By` trailer and no mention of Claude or Anthropic**.
- Authors metadata: `{ name = "Louis Midson LAJEANTY", email = "midsonlajeanty@proton.me" }` (same as GoatSEO). Licence MIT. Repository `https://github.com/goatlabshq/goatnotify`, docs `https://goatlabshq.github.io/goatnotify/`.
- Every package version is `0.1.0` followed by `# x-release-please-version`; internal pins are `==0.1.0 # x-release-please-version`.
- GitHub Actions pinned by commit hash with the version in a trailing comment (use the hashes listed in Task 17).
- No test touches the network beyond `127.0.0.1` servers started by the test itself.
- After each implementation step, `uv run ruff check --fix . && uv run ruff format .` must leave no errors, and `uv run pyright` must report `0 errors` before committing.

## Review Focus

1. A webhook URL carrying a secret token (Discord or Slack style `https://host/api/webhooks/123/SECRET`) must never appear in error messages or logs: only the host is reported. Pinned in Task 9 (`test_errors_do_not_leak_the_webhook_url`).
2. A user-controlled subject, display name or header containing `\r` or `\n` must raise `InvalidMessageError` before any MIME is built. Pinned in Task 5 (`test_line_breaks_are_rejected_everywhere`).
3. `notify_sync()` called inside a running event loop (async view, notebook) must raise `ConfigurationError` without leaking a "coroutine was never awaited" warning. Pinned in Task 4 (`test_notify_sync_inside_a_loop_is_refused`).
4. A webhook answering `Retry-After: 86400` must not park a coroutine for a day: the delay is capped at 300 seconds. Pinned in Task 9 (`test_retry_after_is_capped`).
5. A queued notification that fails in the background must be logged by GoatNotify and never surface as asyncio's "Task exception was never retrieved". Pinned in Task 10 (`test_background_failures_are_logged`).

---

## File Structure

```text
pyproject.toml                         workspace, ruff, pyright, pytest config
lefthook.yml
scripts/check_commit_message.py        commit-msg hook
scripts/smoke_test.py                  runs against built wheels in CI
scripts/consumer.py                    strict pyright against installed wheels in CI
.typecheck/goatnotify/                 symlink tree merging namespace portions for pyright
packages/goatnotify/                   facade: goatnotify/__init__.py (extend_path + re-exports)
packages/goatnotify-core/src/goatnotify/core/
    __init__.py        public API
    _json.py           JsonValue
    errors.py          exception hierarchy, DeliveryFailed
    retry.py           Backoff, ExponentialBackoff, RetryPolicy, NO_RETRY
    notification.py    Notifiable, Message, Notification
    channel.py         Channel
    results.py         DeliveryStatus, DeliveryResult, NotificationResult
    events.py          Sending, Retrying, Sent, Failed, Skipped, Event, Hook
    notifier.py        Notifier
    queue.py           Queue, ClosableQueue, NotificationJob, AsyncioQueue
    templates.py       TemplateRenderer
    http.py            HttpRequest, HttpResponse, HttpTransport, UrllibTransport, require_http_url
    mail/message.py    Address, Attachment, EmailMessage
    mail/mime.py       to_mime
    mail/mailable.py   Mailable
    mail/transport.py  EmailTransport
    mail/mailer.py     Mailer
    mail/smtp.py       SmtpTransport, classify_smtp_error
    channels/email.py      EmailChannel
    channels/database.py   DatabaseMessage, StoredNotification, NotificationStore, DatabaseChannel
    channels/webhook.py    WebhookMessage, WebhookChannel
    testing.py         MemoryTransport, MemoryStore, MemoryHttpTransport, no_sleep
packages/goatnotify-core/tests/        unit tests + core_support.py + fake_smtp.py
packages/goatnotify-jinja/src/goatnotify/jinja/__init__.py      JinjaRenderer
packages/goatnotify-django/src/goatnotify/django/
    apps.py, mail.py, templates.py, models.py, notifiable.py, store.py,
    serialization.py, tasks.py, notifier.py, migrations/0001_initial.py
packages/goatnotify-django/tests/      conftest.py, goatnotify_testapp/, tests
packages/goatnotify-fastapi/src/goatnotify/fastapi/__init__.py  lifespan, attach, get_notifier, NotifierDep
tests/integration/                     workspace, isolation, examples
tests/typing/                          pyright contract tests + fixtures
examples/                              app.py, discord_channel.py, resend_transport.py
docs/                                  mkdocs site
.github/                               workflows, dependabot
release/                               release-please config and manifest
```

---

### Task 1: Workspace scaffolding

**Files:**
- Delete: `src/` (the `uv init` scaffold: `src/goatnotify/__init__.py` only prints a greeting)
- Replace: `pyproject.toml`, `.python-version`, `.gitignore`, `README.md`
- Create: `LICENSE`, `lefthook.yml`, `scripts/check_commit_message.py`, `.typecheck/README.md`, `.typecheck/goatnotify/*` symlinks
- Create for each of `goatnotify`, `goatnotify-core`, `goatnotify-jinja`, `goatnotify-django`, `goatnotify-fastapi`: `packages/<dist>/pyproject.toml`, `README.md`, `LICENSE`, `src/goatnotify/<portion>/__init__.py`, `src/goatnotify/<portion>/py.typed`
- Test: `tests/integration/test_workspace.py`

**Interfaces:**
- Produces: importable namespaces `goatnotify`, `goatnotify.core`, `goatnotify.jinja`, `goatnotify.django`, `goatnotify.fastapi`; pytest `pythonpath` entries `packages/goatnotify-core/tests` and `packages/goatnotify-django/tests`.

- [ ] **Step 1: Remove the scaffold and write the root configuration**

```bash
rm -rf src
echo "3.14" > .python-version
```

`pyproject.toml`:

```toml
[project]
name = "goatnotify-workspace"
version = "0.1.0"
description = "Development workspace for the GoatNotify packages."
readme = "README.md"
license = "MIT"
authors = [{ name = "Louis Midson LAJEANTY", email = "midsonlajeanty@proton.me" }]
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = [
    "goatnotify",
    "goatnotify-core",
    "goatnotify-jinja",
    "goatnotify-django",
    "goatnotify-fastapi",
    "django-stubs>=6.0",
    "httpx>=0.28",
    "lefthook>=1.11",
    "pyright[nodejs]>=1.1.405",
    "pytest>=8.4",
    "pytest-asyncio>=1.2",
    "ruff>=0.13",
    "twine>=6.2",
]
docs = ["mkdocs-material>=9.6"]

[tool.uv]
package = false
default-groups = ["dev"]

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
goatnotify = { workspace = true }
goatnotify-core = { workspace = true }
goatnotify-jinja = { workspace = true }
goatnotify-django = { workspace = true }
goatnotify-fastapi = { workspace = true }

[tool.ruff]
target-version = "py314"
line-length = 100
extend-exclude = [".typecheck", "tests/typing/fixtures"]

[tool.ruff.lint]
select = [
    "A", "ARG", "B", "C4", "DTZ", "E", "F", "FA", "FBT", "I", "ISC", "N", "PGH", "PIE",
    "PL", "PT", "PTH", "PYI", "RET", "RUF", "S", "SIM", "T20", "TC", "TID", "UP", "W",
]
# FastAPI and Django resolve annotations at runtime, so typing-only imports stay real imports.
ignore = ["PLR0913", "PLR2004", "TC001", "TC002", "TC003"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101", "S105", "S106", "PLC0415", "FBT003", "ARG001", "ARG002"]
"**/migrations/**" = ["RUF012", "E501"]
"scripts/**" = ["S101", "T201"]
"examples/**" = ["T201"]

[tool.ruff.lint.isort]
known-first-party = ["goatnotify"]

[tool.ruff.format]
docstring-code-format = true

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
venvPath = "."
venv = ".venv"
extraPaths = [".typecheck", "packages/goatnotify-core/tests", "packages/goatnotify-django/tests"]
include = ["packages", "tests", "scripts", "examples"]
exclude = ["**/__pycache__", "tests/typing/fixtures", "**/.venv", "**/migrations"]
reportMissingModuleSource = "error"
reportUnnecessaryTypeIgnoreComment = "error"

[tool.pytest.ini_options]
addopts = ["--import-mode=importlib", "-ra", "--strict-markers", "--strict-config"]
testpaths = ["packages", "tests"]
pythonpath = ["packages/goatnotify-core/tests", "packages/goatnotify-django/tests"]
filterwarnings = ["error"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

`.gitignore`:

```gitignore
# Python-generated files
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv

# Tooling caches and build output
.pytest_cache/
.ruff_cache/
site/
```

`LICENSE`: the MIT licence text, `Copyright (c) 2026 Louis Midson LAJEANTY`. Copy the same file into every `packages/<dist>/LICENSE`.

`README.md` (temporary, replaced in Task 18):

```markdown
# GoatNotify

A modern, type-safe, framework-agnostic notification system for Python.
```

- [ ] **Step 2: Create the five packages**

`packages/goatnotify-core/pyproject.toml`:

```toml
[project]
name = "goatnotify-core"
version = "0.1.0" # x-release-please-version
description = "Framework-agnostic core of GoatNotify: notifications, channels, transports and retries."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "Louis Midson LAJEANTY", email = "midsonlajeanty@proton.me" }]
requires-python = ">=3.14"
keywords = ["notifications", "email", "smtp", "webhooks", "asyncio", "typed"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Framework :: AsyncIO",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.14",
    "Topic :: Communications :: Email",
    "Typing :: Typed",
]
dependencies = []

[project.urls]
Homepage = "https://github.com/goatlabshq/goatnotify"
Documentation = "https://goatlabshq.github.io/goatnotify/"
Issues = "https://github.com/goatlabshq/goatnotify/issues"

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "goatnotify.core"
```

The other packages copy this file with these differences:

| Dist | `description` | `dependencies` | `module-name` | extra classifier | `[tool.uv.sources]` |
|---|---|---|---|---|---|
| `goatnotify-jinja` | `Jinja2 template renderer for GoatNotify.` | `"goatnotify-core==0.1.0", # x-release-please-version` and `"jinja2>=3.1"` | `goatnotify.jinja` | none | `goatnotify-core = { workspace = true }` |
| `goatnotify-django` | `Django integration for GoatNotify: email backend, templates, ORM store and Django Tasks.` | `"goatnotify-core==0.1.0", # x-release-please-version` and `"django>=6.0"` | `goatnotify.django` | `"Framework :: Django"` | `goatnotify-core = { workspace = true }` |
| `goatnotify-fastapi` | `FastAPI integration for GoatNotify.` | `"goatnotify-core==0.1.0", # x-release-please-version` and `"fastapi>=0.115"` | `goatnotify.fastapi` | `"Framework :: FastAPI"` | `goatnotify-core = { workspace = true }` |
| `goatnotify` | `A modern, type-safe, framework-agnostic notification system for Python.` | `"goatnotify-core==0.1.0", # x-release-please-version` | `goatnotify` | none | core, jinja, django, fastapi all `{ workspace = true }` |

The facade also declares:

```toml
[project.optional-dependencies]
jinja = ["goatnotify-jinja==0.1.0"] # x-release-please-version
django = ["goatnotify-django==0.1.0"] # x-release-please-version
fastapi = ["goatnotify-fastapi==0.1.0"] # x-release-please-version
```

Portion `__init__.py` files contain one docstring each:

- `packages/goatnotify-core/src/goatnotify/core/__init__.py`: `"""Framework-agnostic core of GoatNotify."""`
- `packages/goatnotify-jinja/src/goatnotify/jinja/__init__.py`: `"""Jinja2 template renderer for GoatNotify."""`
- `packages/goatnotify-django/src/goatnotify/django/__init__.py`: `"""Django integration for GoatNotify."""`
- `packages/goatnotify-fastapi/src/goatnotify/fastapi/__init__.py`: `"""FastAPI integration for GoatNotify."""`

`packages/goatnotify/src/goatnotify/__init__.py`:

```python
"""GoatNotify: a modern, type-safe, framework-agnostic notification system for Python."""

from pkgutil import extend_path

# Editable installs give each workspace package its own sys.path entry; extending __path__
# lets goatnotify.core, goatnotify.django, ... resolve as portions of this regular package.
__path__ = extend_path(__path__, __name__)
```

Create an empty `py.typed` next to every `__init__.py` above (including the facade). Each `packages/<dist>/README.md` is two lines: `# <dist>` and the description.

- [ ] **Step 3: Pyright symlink tree**

```bash
mkdir -p .typecheck/goatnotify
ln -s ../../packages/goatnotify/src/goatnotify/__init__.py .typecheck/goatnotify/__init__.py
ln -s ../../packages/goatnotify/src/goatnotify/py.typed .typecheck/goatnotify/py.typed
for portion in core jinja django fastapi; do
  ln -s "../../packages/goatnotify-$portion/src/goatnotify/$portion" ".typecheck/goatnotify/$portion"
done
```

`.typecheck/README.md`:

````markdown
# .typecheck

Symlinks exposing one merged `goatnotify` package, used only by Pyright through
`extraPaths = [".typecheck"]` in the root `pyproject.toml`.

In the workspace, `goatnotify/__init__.py` (facade) and its subpackages (`goatnotify.core`,
`goatnotify.django`, ...) live in separate editable roots. Python merges them at runtime through
`pkgutil.extend_path`, but Pyright stops at the first regular `goatnotify` package it finds and
cannot resolve the others. Installed wheels share one `site-packages/goatnotify/` directory, so
end users never need this.

When adding a package, add its symlink:

```bash
ln -s ../../packages/goatnotify-<name>/src/goatnotify/<name> .typecheck/goatnotify/<name>
```
````

- [ ] **Step 4: Git hooks**

`scripts/check_commit_message.py`:

```python
"""commit-msg hook: a single-line conventional commit subject."""

import re
import sys
from pathlib import Path
from typing import Final

TYPES: Final = "build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test"
SUBJECT: Final = re.compile(rf"^(?:{TYPES})(?:\([a-z0-9-]+\))?!?: \S.*$")
EXEMPT: Final = re.compile(r"^(?:Merge |Revert \"|fixup! |squash! )")


def check(message: str) -> str | None:
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return "the commit message is empty"
    if EXEMPT.match(lines[0]):
        return None
    if not SUBJECT.match(lines[0]):
        return f"{lines[0]!r} is not a conventional commit subject ({TYPES})"
    if len(lines) > 1:
        return "use a single subject line, without a body"
    return None


def main() -> int:
    error = check(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if error is not None:
        print(f"commit-msg: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`lefthook.yml`:

```yaml
pre-commit:
  parallel: true
  commands:
    ruff-format:
      glob: "*.py"
      run: uv run --no-sync ruff format {staged_files}
      stage_fixed: true
    ruff-check:
      glob: "*.py"
      run: uv run --no-sync ruff check --fix {staged_files}
      stage_fixed: true
    actionlint:
      glob: ".github/workflows/*.yml"
      run: uvx --from actionlint-py==1.7.12.25 actionlint {staged_files}

commit-msg:
  commands:
    conventional-commit:
      run: uv run --no-sync python scripts/check_commit_message.py {1}

pre-push:
  parallel: true
  commands:
    pyright:
      run: uv run --no-sync pyright
    pytest:
      run: uv run --no-sync pytest -q
```

- [ ] **Step 5: Write the workspace test**

`tests/integration/test_workspace.py`:

```python
import importlib

import pytest

PORTIONS = ("goatnotify", "goatnotify.core", "goatnotify.jinja", "goatnotify.django", "goatnotify.fastapi")


@pytest.mark.parametrize("module", PORTIONS)
def test_every_namespace_portion_is_importable(module: str) -> None:
    assert importlib.import_module(module).__doc__
```

- [ ] **Step 6: Sync and verify**

Run: `uv sync --all-packages && uv run lefthook install && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright`
Expected: `5 passed`, ruff clean, `0 errors`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "build: scaffold the uv workspace and packages"
```

---

### Task 2: Errors and retry policy

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/_json.py`, `errors.py`, `retry.py`
- Test: `packages/goatnotify-core/tests/test_retry.py`

**Interfaces:**
- Produces:
  - `type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]`
  - `NotificationError(Exception)`, `ConfigurationError`, `DeliveryError`, `RetryableError(message: str, *, retry_after: float | None = None)` with `.retry_after`, `PermanentError`, `InvalidMessageError(PermanentError)`, `SkipDelivery(reason: str)` with `.reason`
  - `DeliveryFailed(ExceptionGroup[Exception])` with `.result: NotificationResult` and `DeliveryFailed.from_result(result) -> Self` (tested in Task 3 once results exist)
  - `Backoff` protocol `delay(attempt: int) -> float` (attempt is 1-based: the attempt that just failed)
  - `ExponentialBackoff(initial=1.0, multiplier=2.0, maximum=60.0, jitter=True)`
  - `RetryPolicy(max_attempts: int = 3, backoff: Backoff = ExponentialBackoff())`, `NO_RETRY`

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_retry.py`:

```python
import pytest

from goatnotify.core.retry import NO_RETRY, ExponentialBackoff, RetryPolicy


def test_exponential_backoff_without_jitter_doubles_up_to_the_maximum() -> None:
    backoff = ExponentialBackoff(initial=1.0, multiplier=2.0, maximum=5.0, jitter=False)
    assert [backoff.delay(attempt) for attempt in range(1, 6)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_jitter_stays_between_zero_and_the_computed_delay() -> None:
    backoff = ExponentialBackoff(initial=2.0, multiplier=3.0, maximum=100.0)
    delays = [backoff.delay(3) for _ in range(200)]
    assert all(0.0 <= delay <= 18.0 for delay in delays)
    assert len(set(delays)) > 1


def test_huge_attempt_numbers_do_not_overflow() -> None:
    assert ExponentialBackoff(maximum=30.0, jitter=False).delay(5000) == 30.0


@pytest.mark.parametrize(
    "arguments",
    [{"initial": -1.0}, {"multiplier": 0.5}, {"initial": 10.0, "maximum": 1.0}],
)
def test_invalid_backoff_is_rejected(arguments: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="ExponentialBackoff"):
        ExponentialBackoff(**arguments)


def test_retry_policy_defaults_and_validation() -> None:
    assert RetryPolicy().max_attempts == 3
    assert NO_RETRY.max_attempts == 1
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_retry.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.retry'`

- [ ] **Step 3: Implement**

`_json.py`:

```python
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
```

`errors.py`:

```python
"""Exception hierarchy shared by every GoatNotify component."""

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from goatnotify.core.results import NotificationResult


class NotificationError(Exception):
    """Base class of every GoatNotify error."""


class ConfigurationError(NotificationError):
    """GoatNotify is wired incorrectly: retrying cannot help."""


class DeliveryError(NotificationError):
    """Raised by channels and transports to describe a delivery outcome."""


class RetryableError(DeliveryError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(DeliveryError):
    pass


class InvalidMessageError(PermanentError):
    pass


class SkipDelivery(DeliveryError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DeliveryFailed(ExceptionGroup[Exception]):
    """Raised once every delivery of a notification has finished and at least one failed."""

    result: NotificationResult

    @classmethod
    def from_result(cls, result: NotificationResult) -> Self:
        errors = [delivery.error for delivery in result.deliveries if delivery.error is not None]
        group = cls(f"{len(errors)} of {len(result.deliveries)} deliveries failed", errors)
        group.result = result
        return group
```

`retry.py`:

```python
"""Retry policies applied by the notifier to RetryableError."""

import random
from dataclasses import dataclass, field
from typing import Final, Protocol

_random: Final = random.SystemRandom()


class Backoff(Protocol):
    def delay(self, attempt: int) -> float: ...


@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    initial: float = 1.0
    multiplier: float = 2.0
    maximum: float = 60.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.initial < 0 or self.maximum < self.initial:
            raise ValueError("ExponentialBackoff needs 0 <= initial <= maximum")
        if self.multiplier < 1:
            raise ValueError("ExponentialBackoff.multiplier must be at least 1")

    def delay(self, attempt: int) -> float:
        try:
            computed = min(self.maximum, self.initial * self.multiplier ** (attempt - 1))
        except OverflowError:
            computed = self.maximum
        return _random.uniform(0, computed) if self.jitter else computed


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Backoff = field(default_factory=ExponentialBackoff)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("RetryPolicy.max_attempts must be at least 1")


NO_RETRY: Final = RetryPolicy(max_attempts=1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core/tests/test_retry.py -q && uv run pyright`
Expected: `8 passed`, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the error hierarchy and retry policies"
```

---

### Task 3: Notification model, channels, results and events

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/notification.py`, `channel.py`, `results.py`, `events.py`
- Create: `packages/goatnotify-core/tests/core_support.py` (shared test doubles, importable thanks to pytest `pythonpath`)
- Test: `packages/goatnotify-core/tests/test_results.py`

**Interfaces:**
- Consumes: `errors.DeliveryFailed`, `retry.RetryPolicy` (Task 2).
- Produces:
  - `Notifiable` protocol: `route_notification(self, channel: str) -> str | None`
  - `Message` (empty `__slots__`), `Notification[R: Notifiable]` with abstract `messages(self, notifiable: R) -> Iterable[Message]`
  - `Channel[M: Message]`: attributes `name: str`, `message_type: type[M]`, `retry: RetryPolicy | None = None`; abstract `async send(self, notifiable: Notifiable, message: M) -> str | None`
  - `DeliveryStatus` (`SENT`, `FAILED`, `SKIPPED`), `DeliveryResult(*, channel, message, status, attempts, provider_id=None, error=None, reason=None)`, `NotificationResult(*, id, notification, deliveries)` with `.ok`, `.failed`, `.raise_for_failures()`
  - Events (keyword-only frozen dataclasses sharing `notification_id: UUID`, `notification: Notification[Any]`, `notifiable: Notifiable`, `channel: str`, `message: Message`, `attempt: int`, and a `name` class variable): `Sending`, `Retrying(delay: float, error: RetryableError)`, `Sent(provider_id: str | None)`, `Failed(error: Exception)`, `Skipped(reason: str)`; `type Event`, `type Hook = Callable[[Event], Awaitable[None] | None]`
  - Test doubles in `core_support.py`: `User`, `Ping`, `LoudPing`, `PingChannel`, `Pings`, `SleepRecorder`

- [ ] **Step 1: Write the shared test doubles**

`packages/goatnotify-core/tests/core_support.py`:

```python
"""Test doubles shared by the core test modules."""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify.core.channel import Channel
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.retry import RetryPolicy


@dataclass
class User:
    email: str | None = "ada@example.com"
    webhook: str | None = None

    def route_notification(self, channel: str) -> str | None:
        match channel:
            case "email":
                return self.email
            case "webhook":
                return self.webhook
            case _:
                return None


@dataclass(frozen=True, slots=True)
class Ping(Message):
    text: str


@dataclass(frozen=True, slots=True)
class LoudPing(Ping):
    pass


class PingChannel(Channel[Ping]):
    """Records pings; each scripted outcome is consumed by one send() call."""

    name = "ping"
    message_type = Ping

    def __init__(self, *outcomes: Exception, retry: RetryPolicy | None = None) -> None:
        self.sent: list[Ping] = []
        self.retry = retry
        self._outcomes = deque(outcomes)

    async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
        if self._outcomes:
            raise self._outcomes.popleft()
        self.sent.append(message)
        return f"ping-{len(self.sent)}"


class Pings(Notification[User]):
    def __init__(self, *texts: str) -> None:
        self.texts = texts

    def messages(self, notifiable: User) -> Iterable[Message]:
        return [Ping(text) for text in self.texts]


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
```

- [ ] **Step 2: Write the failing tests**

`packages/goatnotify-core/tests/test_results.py`:

```python
from uuid import uuid4

import pytest
from core_support import Ping, Pings

from goatnotify.core.errors import DeliveryFailed, PermanentError, RetryableError
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult


def _result(*deliveries: DeliveryResult) -> NotificationResult:
    return NotificationResult(id=uuid4(), notification=Pings(), deliveries=deliveries)


def _delivery(status: DeliveryStatus, error: Exception | None = None) -> DeliveryResult:
    return DeliveryResult(channel="ping", message=Ping("x"), status=status, attempts=1, error=error)


def test_a_result_without_failures_is_ok() -> None:
    result = _result(_delivery(DeliveryStatus.SENT), _delivery(DeliveryStatus.SKIPPED))
    assert result.ok
    assert result.failed == ()
    result.raise_for_failures()


def test_raise_for_failures_groups_every_error() -> None:
    retryable, permanent = RetryableError("later"), PermanentError("never")
    result = _result(
        _delivery(DeliveryStatus.FAILED, retryable),
        _delivery(DeliveryStatus.SENT),
        _delivery(DeliveryStatus.FAILED, permanent),
    )
    with pytest.raises(DeliveryFailed) as caught:
        result.raise_for_failures()
    assert caught.value.result is result
    assert list(caught.value.exceptions) == [retryable, permanent]
    assert str(caught.value).startswith("2 of 3 deliveries failed")


def test_delivery_failed_supports_except_star() -> None:
    result = _result(_delivery(DeliveryStatus.FAILED, PermanentError("never")))
    handled: list[Exception] = []
    try:
        result.raise_for_failures()
    except* PermanentError as group:
        handled.extend(group.exceptions)
    assert len(handled) == 1


def test_messages_are_slotted_value_objects() -> None:
    assert Ping("a") == Ping("a")
    assert not hasattr(Ping("a"), "__dict__")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_results.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.channel'`

- [ ] **Step 4: Implement**

`notification.py`:

```python
"""Recipients, messages and notifications."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Protocol


class Notifiable(Protocol):
    def route_notification(self, channel: str) -> str | None: ...


class Message:
    """Base class of everything a notification yields; its type selects the channel."""

    __slots__ = ()


class Notification[R: Notifiable](ABC):
    @abstractmethod
    def messages(self, notifiable: R) -> Iterable[Message]: ...
```

`channel.py`:

```python
"""Base class of delivery channels."""

from abc import ABC, abstractmethod

from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy


class Channel[M: Message](ABC):
    name: str
    message_type: type[M]
    retry: RetryPolicy | None = None

    @abstractmethod
    async def send(self, notifiable: Notifiable, message: M) -> str | None: ...
```

`results.py`:

```python
"""Structured outcome of a notification."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from goatnotify.core.errors import DeliveryFailed
from goatnotify.core.notification import Message, Notification


class DeliveryStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryResult:
    channel: str
    message: Message
    status: DeliveryStatus
    attempts: int
    provider_id: str | None = None
    error: Exception | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationResult:
    id: UUID
    notification: Notification[Any]
    deliveries: tuple[DeliveryResult, ...]

    @property
    def ok(self) -> bool:
        return not self.failed

    @property
    def failed(self) -> tuple[DeliveryResult, ...]:
        return tuple(d for d in self.deliveries if d.status is DeliveryStatus.FAILED)

    def raise_for_failures(self) -> None:
        if self.failed:
            raise DeliveryFailed.from_result(self)
```

`events.py`:

```python
"""Events passed to notifier hooks."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Literal
from uuid import UUID

from goatnotify.core.errors import RetryableError
from goatnotify.core.notification import Message, Notifiable, Notification


@dataclass(frozen=True, slots=True, kw_only=True)
class _DeliveryEvent:
    notification_id: UUID
    notification: Notification[Any]
    notifiable: Notifiable
    channel: str
    message: Message
    attempt: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Sending(_DeliveryEvent):
    name: ClassVar[Literal["notification.sending"]] = "notification.sending"


@dataclass(frozen=True, slots=True, kw_only=True)
class Retrying(_DeliveryEvent):
    name: ClassVar[Literal["notification.retrying"]] = "notification.retrying"
    delay: float
    error: RetryableError


@dataclass(frozen=True, slots=True, kw_only=True)
class Sent(_DeliveryEvent):
    name: ClassVar[Literal["notification.sent"]] = "notification.sent"
    provider_id: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed(_DeliveryEvent):
    name: ClassVar[Literal["notification.failed"]] = "notification.failed"
    error: Exception


@dataclass(frozen=True, slots=True, kw_only=True)
class Skipped(_DeliveryEvent):
    name: ClassVar[Literal["notification.skipped"]] = "notification.skipped"
    reason: str


type Event = Sending | Retrying | Sent | Failed | Skipped
type Hook = Callable[[Event], Awaitable[None] | None]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 6: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add notifications, channels, results and events"
```

---

### Task 4: Notifier

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/notifier.py`, `packages/goatnotify-core/src/goatnotify/core/testing.py`
- Test: `packages/goatnotify-core/tests/test_notifier.py`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces:
  - `Notifier(channels: Iterable[Channel[Any]], *, retry: RetryPolicy | None = None, hooks: Iterable[Hook] = (), sleep: Callable[[float], Awaitable[None]] = asyncio.sleep)`
  - `async Notifier.notify[R: Notifiable](notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True) -> NotificationResult`
  - `Notifier.notify_sync[R: Notifiable](...)` with the same parameters and return type
  - module logger `logging.getLogger("goatnotify")`
  - `goatnotify.core.testing.no_sleep(delay: float) -> Awaitable[None]`
  - (Task 10 adds `queue=` and `enqueue()`.)

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_notifier.py`:

```python
import asyncio
import logging
import warnings
from collections.abc import Iterable

import pytest
from core_support import LoudPing, Ping, PingChannel, Pings, SleepRecorder, User

from goatnotify.core import events
from goatnotify.core.channel import Channel
from goatnotify.core.errors import (
    ConfigurationError,
    DeliveryFailed,
    PermanentError,
    RetryableError,
    SkipDelivery,
)
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.retry import NO_RETRY, ExponentialBackoff, RetryPolicy
from goatnotify.core.testing import no_sleep

FAST = RetryPolicy(max_attempts=3, backoff=ExponentialBackoff(jitter=False))


class Other(Message):
    __slots__ = ()


class Mixed(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        return [Ping("a"), Other()]


class Loud(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield LoudPing("hey")


async def test_a_message_is_delivered_through_its_channel() -> None:
    channel = PingChannel()
    result = await Notifier([channel]).notify(User(), Pings("hello"))
    assert channel.sent == [Ping("hello")]
    assert result.ok
    (delivery,) = result.deliveries
    assert delivery.status is DeliveryStatus.SENT
    assert (delivery.channel, delivery.attempts, delivery.provider_id) == ("ping", 1, "ping-1")


async def test_routing_follows_the_message_class_hierarchy() -> None:
    channel = PingChannel()
    await Notifier([channel]).notify(User(), Loud())
    assert channel.sent == [LoudPing("hey")]


def test_two_channels_for_one_message_type_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="both handle Ping"):
        Notifier([PingChannel(), PingChannel()])


async def test_an_unroutable_message_aborts_before_anything_is_sent() -> None:
    channel = PingChannel()
    with pytest.raises(ConfigurationError, match="No channel handles Other"):
        await Notifier([channel]).notify(User(), Mixed())
    assert channel.sent == []


async def test_results_keep_message_order() -> None:
    result = await Notifier([PingChannel()]).notify(User(), Pings("a", "b", "c"))
    assert [d.message for d in result.deliveries] == [Ping("a"), Ping("b"), Ping("c")]


async def test_messages_are_delivered_concurrently() -> None:
    second_started = asyncio.Event()

    class Waiting(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            # Sequential delivery would time out here: "second" only starts after "first".
            if message.text == "first":
                await asyncio.wait_for(second_started.wait(), timeout=1)
            else:
                second_started.set()
            return await super().send(notifiable, message)

    result = await Notifier([Waiting()]).notify(User(), Pings("first", "second"))
    assert result.ok


async def test_skip_delivery_is_reported_without_failing() -> None:
    channel = PingChannel(SkipDelivery("muted"))
    result = await Notifier([channel]).notify(User(), Pings("x"))
    assert result.ok
    assert result.deliveries[0].status is DeliveryStatus.SKIPPED
    assert result.deliveries[0].reason == "muted"


async def test_retryable_errors_are_retried_with_backoff() -> None:
    sleep = SleepRecorder()
    channel = PingChannel(RetryableError("busy"), RetryableError("busy"))
    result = await Notifier([channel], retry=FAST, sleep=sleep).notify(User(), Pings("x"))
    assert result.deliveries[0].status is DeliveryStatus.SENT
    assert result.deliveries[0].attempts == 3
    assert sleep.delays == [1.0, 2.0]


async def test_retry_after_overrides_the_backoff() -> None:
    sleep = SleepRecorder()
    channel = PingChannel(RetryableError("slow down", retry_after=7.5))
    await Notifier([channel], retry=FAST, sleep=sleep).notify(User(), Pings("x"))
    assert sleep.delays == [7.5]


async def test_exhausted_retries_raise_delivery_failed() -> None:
    errors = [RetryableError("busy") for _ in range(3)]
    notifier = Notifier([PingChannel(*errors)], retry=FAST, sleep=no_sleep)
    with pytest.raises(DeliveryFailed) as caught:
        await notifier.notify(User(), Pings("x"))
    (delivery,) = caught.value.result.deliveries
    assert (delivery.status, delivery.attempts, delivery.error) == (
        DeliveryStatus.FAILED,
        3,
        errors[2],
    )


@pytest.mark.parametrize("error", [PermanentError("gone"), ValueError("bug")])
async def test_permanent_and_unexpected_errors_are_not_retried(error: Exception) -> None:
    sleep = SleepRecorder()
    notifier = Notifier([PingChannel(error)], retry=FAST, sleep=sleep)
    result = await notifier.notify(User(), Pings("x"), raise_on_failure=False)
    assert not result.ok
    assert (result.deliveries[0].attempts, result.deliveries[0].error) == (1, error)
    assert sleep.delays == []


async def test_other_deliveries_complete_when_one_fails() -> None:
    class Flaky(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            if message.text == "bad":
                raise PermanentError("rejected")
            return await super().send(notifiable, message)

    channel = Flaky()
    result = await Notifier([channel]).notify(User(), Pings("bad", "good"), raise_on_failure=False)
    assert [d.status for d in result.deliveries] == [DeliveryStatus.FAILED, DeliveryStatus.SENT]
    assert channel.sent == [Ping("good")]


async def test_a_channel_retry_policy_overrides_the_notifier_default() -> None:
    channel = PingChannel(RetryableError("busy"), retry=NO_RETRY)
    result = await Notifier([channel], retry=FAST, sleep=no_sleep).notify(
        User(), Pings("x"), raise_on_failure=False
    )
    assert result.deliveries[0].attempts == 1


async def test_hooks_receive_every_event_in_order() -> None:
    received: list[events.Event] = []

    async def async_hook(event: events.Event) -> None:
        await asyncio.sleep(0)

    channel = PingChannel(RetryableError("busy"))
    notifier = Notifier(
        [channel], retry=FAST, sleep=no_sleep, hooks=[received.append, async_hook]
    )
    result = await notifier.notify(User(), Pings("x"))
    assert [event.name for event in received] == [
        "notification.sending",
        "notification.retrying",
        "notification.sending",
        "notification.sent",
    ]
    assert all(event.notification_id == result.id for event in received)
    sent = received[-1]
    assert isinstance(sent, events.Sent)
    assert (sent.attempt, sent.provider_id, sent.channel) == (2, "ping-1", "ping")


async def test_failed_and_skipped_events_are_emitted() -> None:
    received: list[events.Event] = []
    channel = PingChannel(PermanentError("no"), SkipDelivery("muted"))
    await Notifier([channel], hooks=[received.append]).notify(
        User(), Pings("a", "b"), raise_on_failure=False
    )
    names = {event.name for event in received}
    assert {"notification.failed", "notification.skipped"} <= names


async def test_a_failing_hook_is_logged_and_does_not_change_the_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(event: events.Event) -> None:
        raise RuntimeError("hook bug")

    with caplog.at_level(logging.ERROR, logger="goatnotify"):
        result = await Notifier([PingChannel()], hooks=[broken]).notify(User(), Pings("x"))
    assert result.ok
    assert "hook bug" in caplog.text


async def test_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="goatnotify"):
        await Notifier([PingChannel(PermanentError("no"))]).notify(
            User(), Pings("x"), raise_on_failure=False
        )
    assert "failed after 1 attempt" in caplog.text


async def test_a_notification_without_messages_sends_nothing() -> None:
    result = await Notifier([PingChannel()]).notify(User(), Pings())
    assert result.ok
    assert result.deliveries == ()


def test_notify_sync_outside_a_loop() -> None:
    channel = PingChannel()
    result = Notifier([channel]).notify_sync(User(), Pings("sync"))
    assert result.ok
    assert channel.sent == [Ping("sync")]


async def test_notify_sync_inside_a_loop_is_refused() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ConfigurationError, match="await notify"):
            Notifier([PingChannel()]).notify_sync(User(), Pings("x"))


def test_channels_keep_their_declared_name() -> None:
    channel: Channel[Ping] = PingChannel()
    assert channel.name == "ping"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_notifier.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.notifier'`

- [ ] **Step 3: Implement**

`testing.py`:

```python
"""In-memory fakes for testing code that sends notifications."""


async def no_sleep(delay: float) -> None:
    """Drop-in for asyncio.sleep that makes retries instantaneous."""
```

`notifier.py`:

```python
"""The notifier routes messages to channels, retries, fires hooks and reports results."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final, TypedDict
from uuid import UUID, uuid4

from goatnotify.core import events
from goatnotify.core.channel import Channel
from goatnotify.core.errors import ConfigurationError, RetryableError, SkipDelivery
from goatnotify.core.events import Event, Hook
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult
from goatnotify.core.retry import RetryPolicy

logger: Final = logging.getLogger("goatnotify")

type Sleep = Callable[[float], Awaitable[None]]


class _Scope(TypedDict):
    notification_id: UUID
    notification: Notification[Any]
    notifiable: Notifiable
    channel: str
    message: Message


class Notifier:
    def __init__(
        self,
        channels: Iterable[Channel[Any]],
        *,
        retry: RetryPolicy | None = None,
        hooks: Iterable[Hook] = (),
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._routes: dict[type[Message], Channel[Any]] = {}
        for channel in channels:
            existing = self._routes.get(channel.message_type)
            if existing is not None:
                raise ConfigurationError(
                    f"Channels {existing.name!r} and {channel.name!r} both handle "
                    f"{channel.message_type.__qualname__}"
                )
            self._routes[channel.message_type] = channel
        self._retry = retry or RetryPolicy()
        self._hooks = tuple(hooks)
        self._sleep = sleep

    async def notify[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult:
        routed = [(self._channel_for(message), message) for message in notification.messages(notifiable)]
        notification_id = uuid4()
        deliveries = await asyncio.gather(
            *(
                self._deliver(
                    _Scope(
                        notification_id=notification_id,
                        notification=notification,
                        notifiable=notifiable,
                        channel=channel.name,
                        message=message,
                    ),
                    channel,
                )
                for channel, message in routed
            )
        )
        result = NotificationResult(
            id=notification_id, notification=notification, deliveries=tuple(deliveries)
        )
        if raise_on_failure:
            result.raise_for_failures()
        return result

    def notify_sync[R: Notifiable](
        self, notifiable: R, notification: Notification[R], *, raise_on_failure: bool = True
    ) -> NotificationResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.notify(notifiable, notification, raise_on_failure=raise_on_failure)
            )
        raise ConfigurationError("notify_sync() cannot run inside an event loop: await notify()")

    def _channel_for(self, message: Message) -> Channel[Any]:
        for cls in type(message).__mro__:
            channel = self._routes.get(cls)
            if channel is not None:
                return channel
        raise ConfigurationError(f"No channel handles {type(message).__qualname__}")

    async def _deliver(self, scope: _Scope, channel: Channel[Any]) -> DeliveryResult:
        policy = channel.retry or self._retry
        message = scope["message"]
        attempt = 1
        while True:
            await self._emit(events.Sending(**scope, attempt=attempt))
            try:
                provider_id = await channel.send(scope["notifiable"], message)
            except SkipDelivery as skip:
                await self._emit(events.Skipped(**scope, attempt=attempt, reason=skip.reason))
                return DeliveryResult(
                    channel=channel.name,
                    message=message,
                    status=DeliveryStatus.SKIPPED,
                    attempts=attempt,
                    reason=skip.reason,
                )
            except RetryableError as error:
                if attempt >= policy.max_attempts:
                    return await self._failed(scope, attempt, error)
                delay = error.retry_after if error.retry_after is not None else policy.backoff.delay(attempt)
                await self._emit(events.Retrying(**scope, attempt=attempt, delay=delay, error=error))
                await self._sleep(delay)
                attempt += 1
            except Exception as error:  # noqa: BLE001
                return await self._failed(scope, attempt, error)
            else:
                await self._emit(events.Sent(**scope, attempt=attempt, provider_id=provider_id))
                return DeliveryResult(
                    channel=channel.name,
                    message=message,
                    status=DeliveryStatus.SENT,
                    attempts=attempt,
                    provider_id=provider_id,
                )

    async def _failed(self, scope: _Scope, attempt: int, error: Exception) -> DeliveryResult:
        logger.warning(
            "Delivery of %s through %r failed after %d attempt(s): %r",
            type(scope["message"]).__qualname__,
            scope["channel"],
            attempt,
            error,
        )
        await self._emit(events.Failed(**scope, attempt=attempt, error=error))
        return DeliveryResult(
            channel=scope["channel"],
            message=scope["message"],
            status=DeliveryStatus.FAILED,
            attempts=attempt,
            error=error,
        )

    async def _emit(self, event: Event) -> None:
        for hook in self._hooks:
            try:
                outcome = hook(event)
                if outcome is not None:
                    await outcome
            except Exception:
                logger.exception("Hook %r failed while handling %s", hook, event.name)
```

Notes for the implementer:
- `BLE` is not in the ruff selection, so drop the `# noqa: BLE001` if ruff reports it as unused (`RUF100`).
- `ruff format` will rewrap the long lines above; that is expected.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the notifier with retries, hooks and results"
```

---

### Task 5: Email message model and MIME rendering

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/mail/__init__.py` (docstring only: `"""Email: mailables, rendering and transports."""`), `mail/message.py`, `mail/mime.py`
- Test: `packages/goatnotify-core/tests/test_mail_message.py`, `packages/goatnotify-core/tests/test_mime.py`

**Interfaces:**
- Consumes: `InvalidMessageError` (Task 2).
- Produces:
  - `Address(email: str, name: str | None = None)`, `Address.parse(value: str | Address) -> Address`, `str(address)` gives `"Name <email>"` or `"email"`
  - `type AddressLike = str | Address`
  - `Attachment(filename: str, content: bytes, mimetype: str = "application/octet-stream", inline: bool = False)`, `Attachment.from_path(path: str | Path, *, mimetype: str | None = None, inline: bool = False)`
  - `EmailMessage(*, subject, sender, to=(), cc=(), bcc=(), reply_to=(), html=None, text=None, attachments=(), headers={}, metadata={})` with `.recipients -> tuple[Address, ...]` (to + cc + bcc)
  - `to_mime(message: EmailMessage) -> email.message.EmailMessage`

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_mail_message.py`:

```python
from pathlib import Path

import pytest

from goatnotify.core.errors import InvalidMessageError
from goatnotify.core.mail.message import Address, Attachment, EmailMessage

SENDER = Address("noreply@goat.dev", "Goat")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ada@example.com", Address("ada@example.com")),
        ("Ada Lovelace <ada@example.com>", Address("ada@example.com", "Ada Lovelace")),
        (Address("x@y.z"), Address("x@y.z")),
    ],
)
def test_addresses_are_parsed(raw: str | Address, expected: Address) -> None:
    assert Address.parse(raw) == expected


@pytest.mark.parametrize("raw", ["", "not-an-email", "@example.com", "ada@"])
def test_invalid_addresses_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidMessageError):
        Address.parse(raw)


def test_addresses_format_with_their_display_name() -> None:
    assert str(Address("ada@example.com", "Ada")) == "Ada <ada@example.com>"
    assert str(Address("ada@example.com")) == "ada@example.com"


def test_attachment_from_path_guesses_the_mimetype(tmp_path: Path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-1.7")
    attachment = Attachment.from_path(path)
    assert (attachment.filename, attachment.content, attachment.mimetype) == (
        "report.pdf",
        b"%PDF-1.7",
        "application/pdf",
    )


def test_an_email_needs_a_recipient_and_a_body() -> None:
    with pytest.raises(InvalidMessageError, match="recipient"):
        EmailMessage(subject="Hi", sender=SENDER, text="Hello")
    with pytest.raises(InvalidMessageError, match="body"):
        EmailMessage(subject="Hi", sender=SENDER, to=(Address("a@b.c"),))


def test_recipients_include_cc_and_bcc() -> None:
    message = EmailMessage(
        subject="Hi",
        sender=SENDER,
        to=(Address("a@b.c"),),
        cc=(Address("c@b.c"),),
        bcc=(Address("d@b.c"),),
        text="Hello",
    )
    assert [a.email for a in message.recipients] == ["a@b.c", "c@b.c", "d@b.c"]


@pytest.mark.parametrize(
    "build",
    [
        lambda: Address.parse("Ada\r\nBcc: evil@x.y <ada@example.com>"),
        lambda: Address("ada@example.com", "Ada\nBcc: evil@x.y"),
        lambda: EmailMessage(subject="Hi\r\nBcc: evil@x.y", sender=SENDER, to=(SENDER,), text="x"),
        lambda: EmailMessage(
            subject="Hi", sender=SENDER, to=(SENDER,), text="x", headers={"X-Tag": "a\nb"}
        ),
        lambda: Attachment(filename="a\r\n.txt", content=b""),
    ],
)
def test_line_breaks_are_rejected_everywhere(build: object) -> None:
    assert callable(build)
    with pytest.raises(InvalidMessageError, match="line breaks"):
        build()


@pytest.mark.parametrize("header", ["Subject", "bcc", "Content-Type"])
def test_reserved_headers_cannot_be_overridden(header: str) -> None:
    with pytest.raises(InvalidMessageError, match="reserved"):
        EmailMessage(subject="Hi", sender=SENDER, to=(SENDER,), text="x", headers={header: "v"})
```

`packages/goatnotify-core/tests/test_mime.py`:

```python
from email import message_from_bytes, policy
from email.message import EmailMessage as MimeMessage

from goatnotify.core.mail.message import Address, Attachment, EmailMessage
from goatnotify.core.mail.mime import to_mime

SENDER = Address("noreply@goat.dev", "Goat")
ADA = Address("ada@example.com", "Ada")


def _parse(message: EmailMessage) -> MimeMessage:
    parsed = message_from_bytes(to_mime(message).as_bytes(), policy=policy.default)
    assert isinstance(parsed, MimeMessage)
    return parsed


def test_envelope_headers() -> None:
    mime = _parse(
        EmailMessage(
            subject="Welcome",
            sender=SENDER,
            to=(ADA,),
            cc=(Address("cc@example.com"),),
            bcc=(Address("hidden@example.com"),),
            reply_to=(Address("support@goat.dev"),),
            text="Hello",
            headers={"X-Campaign": "welcome"},
        )
    )
    assert mime["Subject"] == "Welcome"
    assert mime["From"] == "Goat <noreply@goat.dev>"
    assert mime["To"] == "Ada <ada@example.com>"
    assert mime["Cc"] == "cc@example.com"
    assert mime["Reply-To"] == "support@goat.dev"
    assert mime["X-Campaign"] == "welcome"
    assert mime["Bcc"] is None
    assert str(mime["Message-ID"]).endswith("@goat.dev>")
    assert mime["Date"] is not None


def test_an_explicit_message_id_is_kept() -> None:
    mime = _parse(
        EmailMessage(
            subject="x", sender=SENDER, to=(ADA,), text="x", headers={"Message-ID": "<id@goat.dev>"}
        )
    )
    assert mime.get_all("Message-ID") == ["<id@goat.dev>"]


def test_text_and_html_become_alternatives() -> None:
    mime = _parse(EmailMessage(subject="x", sender=SENDER, to=(ADA,), text="Hi", html="<p>Hi</p>"))
    assert mime.get_content_type() == "multipart/alternative"
    text, html = mime.get_body(("plain",)), mime.get_body(("html",))
    assert text is not None and text.get_content().strip() == "Hi"
    assert html is not None and html.get_content().strip() == "<p>Hi</p>"


def test_html_only() -> None:
    mime = _parse(EmailMessage(subject="x", sender=SENDER, to=(ADA,), html="<p>Hi</p>"))
    assert mime.get_content_type() == "text/html"


def test_attachments_and_inline_images() -> None:
    mime = _parse(
        EmailMessage(
            subject="x",
            sender=SENDER,
            to=(ADA,),
            text="Hi",
            html='<img src="cid:logo.png">',
            attachments=(
                Attachment("report.pdf", b"%PDF", "application/pdf"),
                Attachment("logo.png", b"\x89PNG", "image/png", inline=True),
            ),
        )
    )
    assert mime.get_content_type() == "multipart/mixed"
    files = {part.get_filename(): part for part in mime.walk() if part.get_filename()}
    assert files["report.pdf"].get_content() == b"%PDF"
    assert files["report.pdf"].get_content_disposition() == "attachment"
    assert files["logo.png"]["Content-ID"] == "<logo.png>"
    assert files["logo.png"].get_content_disposition() == "inline"


def test_non_ascii_content_survives() -> None:
    mime = _parse(
        EmailMessage(
            subject="Bienvenue, Zoé",
            sender=Address("noreply@goat.dev", "Équipe Goat"),
            to=(ADA,),
            text="Merci à vous",
        )
    )
    assert mime["Subject"] == "Bienvenue, Zoé"
    assert mime["From"] == "Équipe Goat <noreply@goat.dev>"
    body = mime.get_body(("plain",))
    assert body is not None and body.get_content().strip() == "Merci à vous"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_mail_message.py packages/goatnotify-core/tests/test_mime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.mail'`

- [ ] **Step 3: Implement**

`mail/message.py`:

```python
"""Rendered email value objects, the input of every EmailTransport."""

import mimetypes
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Final

from goatnotify.core.errors import InvalidMessageError

DEFAULT_MIMETYPE: Final = "application/octet-stream"
RESERVED_HEADERS: Final = frozenset(
    {"subject", "from", "to", "cc", "bcc", "reply-to", "date", "content-type", "mime-version"}
)


def _reject_line_breaks(value: str, what: str) -> None:
    if "\r" in value or "\n" in value:
        raise InvalidMessageError(f"{what} must not contain line breaks")


@dataclass(frozen=True, slots=True)
class Address:
    email: str
    name: str | None = None

    def __post_init__(self) -> None:
        _reject_line_breaks(self.email, "An email address")
        if self.name is not None:
            _reject_line_breaks(self.name, "An address name")
        local, _, domain = self.email.rpartition("@")
        if not local or not domain or any(c.isspace() for c in self.email):
            raise InvalidMessageError(f"{self.email!r} is not an email address")

    @classmethod
    def parse(cls, value: str | Address) -> Address:
        if isinstance(value, Address):
            return value
        _reject_line_breaks(value, "An email address")
        name, email = parseaddr(value)
        if not email:
            raise InvalidMessageError(f"{value!r} is not an email address")
        return cls(email=email, name=name or None)

    def __str__(self) -> str:
        return formataddr((self.name, self.email)) if self.name else self.email


type AddressLike = str | Address


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content: bytes
    mimetype: str = DEFAULT_MIMETYPE
    inline: bool = False

    def __post_init__(self) -> None:
        _reject_line_breaks(self.filename, "An attachment filename")
        if self.mimetype.count("/") != 1:
            raise InvalidMessageError(f"{self.mimetype!r} is not a MIME type")

    @classmethod
    def from_path(
        cls, path: str | Path, *, mimetype: str | None = None, inline: bool = False
    ) -> Attachment:
        path = Path(path)
        guessed, _ = mimetypes.guess_file_type(path)
        return cls(
            filename=path.name,
            content=path.read_bytes(),
            mimetype=mimetype or guessed or DEFAULT_MIMETYPE,
            inline=inline,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailMessage:
    subject: str
    sender: Address
    to: tuple[Address, ...] = ()
    cc: tuple[Address, ...] = ()
    bcc: tuple[Address, ...] = ()
    reply_to: tuple[Address, ...] = ()
    html: str | None = None
    text: str | None = None
    attachments: tuple[Attachment, ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    metadata: Mapping[str, str] = field(default_factory=dict[str, str])

    def __post_init__(self) -> None:
        _reject_line_breaks(self.subject, "A subject")
        for name, value in self.headers.items():
            _reject_line_breaks(name, "A header name")
            _reject_line_breaks(value, f"Header {name!r}")
            if name.lower() in RESERVED_HEADERS:
                raise InvalidMessageError(f"{name} is reserved: set it through the message fields")
        if not self.recipients:
            raise InvalidMessageError("An email needs at least one recipient")
        if self.html is None and self.text is None:
            raise InvalidMessageError("An email needs an HTML or a text body")

    @property
    def recipients(self) -> tuple[Address, ...]:
        return self.to + self.cc + self.bcc
```

`mail/mime.py`:

```python
"""Conversion of a rendered EmailMessage to a standard library MIME message."""

from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid

from goatnotify.core.mail.message import Address, Attachment, EmailMessage


def to_mime(message: EmailMessage) -> MimeMessage:
    mime = MimeMessage()
    mime["Subject"] = message.subject
    mime["From"] = str(message.sender)
    _set_addresses(mime, "To", message.to)
    _set_addresses(mime, "Cc", message.cc)
    _set_addresses(mime, "Reply-To", message.reply_to)
    mime["Date"] = formatdate(usegmt=True)
    for name, value in message.headers.items():
        mime[name] = value
    if "Message-ID" not in mime:
        mime["Message-ID"] = make_msgid(domain=message.sender.email.rpartition("@")[2])
    _set_body(mime, message)
    for attachment in message.attachments:
        _attach(mime, attachment)
    return mime


def _set_addresses(mime: MimeMessage, header: str, addresses: tuple[Address, ...]) -> None:
    if addresses:
        mime[header] = ", ".join(str(address) for address in addresses)


def _set_body(mime: MimeMessage, message: EmailMessage) -> None:
    if message.text is not None:
        mime.set_content(message.text)
        if message.html is not None:
            mime.add_alternative(message.html, subtype="html")
    elif message.html is not None:
        mime.set_content(message.html, subtype="html")


def _attach(mime: MimeMessage, attachment: Attachment) -> None:
    maintype, subtype = attachment.mimetype.split("/")
    html = mime.get_body(("html",)) if attachment.inline else None
    if html is None:
        mime.add_attachment(
            attachment.content, maintype=maintype, subtype=subtype, filename=attachment.filename
        )
        return
    html.add_related(
        attachment.content,
        maintype=maintype,
        subtype=subtype,
        cid=f"<{attachment.filename}>",
        filename=attachment.filename,
        disposition="inline",
    )
```

If `test_attachments_and_inline_images` shows the inline part missing because `get_body` returned a copy, attach inline parts before regular attachments (loop twice: `inline=True` first). Keep whichever order passes.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the rendered email model and MIME conversion"
```

---

### Task 6: Mailable, Mailer, EmailChannel and MemoryTransport

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/templates.py`, `mail/mailable.py`, `mail/transport.py`, `mail/mailer.py`, `channels/__init__.py` (docstring: `"""Built-in delivery channels."""`), `channels/email.py`
- Modify: `packages/goatnotify-core/src/goatnotify/core/testing.py` (add `MemoryTransport`)
- Test: `packages/goatnotify-core/tests/test_mailer.py`, `packages/goatnotify-core/tests/test_email_channel.py`

**Interfaces:**
- Consumes: Tasks 2 to 5.
- Produces:
  - `TemplateRenderer` protocol: `async render(self, template: str, context: Mapping[str, object]) -> str`
  - `Mailable(Message)` class attributes `subject: str = ""`, `sender: AddressLike | None = None`, `to/cc/bcc/reply_to: Sequence[AddressLike] = ()`, `headers: Mapping[str, str]`, `metadata: Mapping[str, str]`; overridable methods `attachments()`, `html()`, `text()`, `template()`, `text_template()`, `context()`
  - `EmailTransport` protocol: `async send(self, message: EmailMessage) -> str | None`
  - `Mailer(transport: EmailTransport, *, sender: AddressLike, renderer: TemplateRenderer | None = None)` with `async render(mailable, *, to: Sequence[AddressLike] = ()) -> EmailMessage` and `async send(mailable, *, to=()) -> str | None`; a non-empty `to` replaces `mailable.to`
  - `EmailChannel(mailer: Mailer, *, retry: RetryPolicy | None = None)`, `name = "email"`, `message_type = Mailable`
  - `MemoryTransport()` with `.outbox: list[EmailMessage]`, `fail_next(*errors: Exception) -> None`, `send()` returns `"memory-<n>"`

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_mailer.py`:

```python
from collections.abc import Mapping, Sequence

import pytest

from goatnotify.core.errors import ConfigurationError, InvalidMessageError
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address, Attachment
from goatnotify.core.testing import MemoryTransport


class RecordingRenderer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        self.calls.append((template, dict(context)))
        return f"rendered:{template}:{context['name']}"


class Welcome(Mailable):
    subject = "Welcome"

    def __init__(self, name: str = "Ada") -> None:
        self.name = name

    def template(self) -> str | None:
        return "welcome.html"

    def text_template(self) -> str | None:
        return "welcome.txt"

    def context(self) -> Mapping[str, object]:
        return {"name": self.name}


class Raw(Mailable):
    subject = "Raw"
    to = ("ada@example.com",)
    cc = ("Boss <boss@example.com>",)
    bcc = (Address("audit@example.com"),)
    reply_to = ("support@goat.dev",)
    headers = {"X-Campaign": "raw"}
    metadata = {"tag": "raw"}

    def html(self) -> str | None:
        return "<p>raw</p>"

    def attachments(self) -> Sequence[Attachment]:
        return [Attachment("a.txt", b"a", "text/plain")]


async def test_raw_content_and_envelope() -> None:
    message = await Mailer(MemoryTransport(), sender="Goat <noreply@goat.dev>").render(Raw())
    assert message.subject == "Raw"
    assert message.sender == Address("noreply@goat.dev", "Goat")
    assert message.to == (Address("ada@example.com"),)
    assert message.cc == (Address("boss@example.com", "Boss"),)
    assert message.bcc == (Address("audit@example.com"),)
    assert message.reply_to == (Address("support@goat.dev"),)
    assert (message.html, message.text) == ("<p>raw</p>", None)
    assert message.attachments == (Attachment("a.txt", b"a", "text/plain"),)
    assert dict(message.headers) == {"X-Campaign": "raw"}
    assert dict(message.metadata) == {"tag": "raw"}


async def test_templates_are_rendered_with_the_context() -> None:
    renderer = RecordingRenderer()
    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev", renderer=renderer)
    message = await mailer.render(Welcome("Zoé"), to=["zoe@example.com"])
    assert message.html == "rendered:welcome.html:Zoé"
    assert message.text == "rendered:welcome.txt:Zoé"
    assert renderer.calls == [("welcome.html", {"name": "Zoé"}), ("welcome.txt", {"name": "Zoé"})]


async def test_raw_content_wins_over_templates() -> None:
    class Both(Welcome):
        def html(self) -> str | None:
            return "<p>raw</p>"

    renderer = RecordingRenderer()
    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev", renderer=renderer)
    message = await mailer.render(Both(), to=["a@b.c"])
    assert message.html == "<p>raw</p>"
    assert [template for template, _ in renderer.calls] == ["welcome.txt"]


async def test_a_template_without_renderer_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="TemplateRenderer"):
        await Mailer(MemoryTransport(), sender="noreply@goat.dev").render(Welcome(), to=["a@b.c"])


async def test_a_mailable_needs_a_subject_and_a_body() -> None:
    class NoSubject(Raw):
        subject = ""

    class NoBody(Mailable):
        subject = "Empty"

    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev")
    with pytest.raises(InvalidMessageError, match="subject"):
        await mailer.render(NoSubject())
    with pytest.raises(InvalidMessageError, match="body"):
        await mailer.render(NoBody(), to=["a@b.c"])


async def test_explicit_recipients_and_sender_override_defaults() -> None:
    class Custom(Raw):
        sender = "Billing <billing@goat.dev>"

    message = await Mailer(MemoryTransport(), sender="noreply@goat.dev").render(
        Custom(), to=["other@example.com"]
    )
    assert message.sender == Address("billing@goat.dev", "Billing")
    assert message.to == (Address("other@example.com"),)


async def test_send_hands_the_rendered_message_to_the_transport() -> None:
    transport = MemoryTransport()
    provider_id = await Mailer(transport, sender="noreply@goat.dev").send(Raw())
    assert provider_id == "memory-1"
    assert [m.subject for m in transport.outbox] == ["Raw"]
```

`packages/goatnotify-core/tests/test_email_channel.py`:

```python
from collections.abc import Iterable

import pytest
from core_support import User

from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.errors import RetryableError, SkipDelivery
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.testing import MemoryTransport, no_sleep


class Hello(Mailable):
    subject = "Hello"

    def text(self) -> str | None:
        return "Hello!"


class Greeting(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Hello()


def _channel() -> tuple[EmailChannel, MemoryTransport]:
    transport = MemoryTransport()
    return EmailChannel(Mailer(transport, sender="noreply@goat.dev")), transport


async def test_the_email_route_is_used_when_the_mailable_has_no_recipient() -> None:
    channel, transport = _channel()
    await channel.send(User(email="ada@example.com"), Hello())
    assert transport.outbox[0].to == (Address("ada@example.com"),)


async def test_explicit_mailable_recipients_win_over_the_route() -> None:
    class Direct(Hello):
        to = ("boss@example.com",)

    channel, transport = _channel()
    await channel.send(User(email="ada@example.com"), Direct())
    assert transport.outbox[0].to == (Address("boss@example.com"),)


async def test_a_recipient_without_email_route_is_skipped() -> None:
    channel, _ = _channel()
    with pytest.raises(SkipDelivery, match="no email route"):
        await channel.send(User(email=None), Hello())


async def test_end_to_end_with_retry() -> None:
    channel, transport = _channel()
    transport.fail_next(RetryableError("421 try later"))
    result = await Notifier([channel], sleep=no_sleep).notify(User(), Greeting())
    (delivery,) = result.deliveries
    assert (delivery.status, delivery.attempts, delivery.provider_id) == (
        DeliveryStatus.SENT,
        2,
        "memory-1",
    )
    assert len(transport.outbox) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_mailer.py packages/goatnotify-core/tests/test_email_channel.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.mail.mailable'`

- [ ] **Step 3: Implement**

`templates.py`:

```python
"""Template rendering protocol; engines are provided by optional packages."""

from collections.abc import Mapping
from typing import Protocol


class TemplateRenderer(Protocol):
    async def render(self, template: str, context: Mapping[str, object]) -> str: ...
```

`mail/mailable.py`:

```python
"""Mailable: an email described by a class."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import ClassVar

from goatnotify.core.mail.message import AddressLike, Attachment
from goatnotify.core.notification import Message

_EMPTY: MappingProxyType[str, str] = MappingProxyType({})


class Mailable(Message):
    """Subclass it: set envelope attributes and override the content methods you need."""

    subject: str = ""
    sender: AddressLike | None = None
    to: Sequence[AddressLike] = ()
    cc: Sequence[AddressLike] = ()
    bcc: Sequence[AddressLike] = ()
    reply_to: Sequence[AddressLike] = ()
    headers: Mapping[str, str] = _EMPTY
    metadata: Mapping[str, str] = _EMPTY

    def attachments(self) -> Sequence[Attachment]:
        return ()

    def html(self) -> str | None:
        return None

    def text(self) -> str | None:
        return None

    def template(self) -> str | None:
        return None

    def text_template(self) -> str | None:
        return None

    def context(self) -> Mapping[str, object]:
        return _EMPTY
```

Remove the unused `ClassVar` import if ruff flags it. Because `Message` declares `__slots__ = ()` and `Mailable` does not, mailable instances have a `__dict__`, so subclasses may assign attributes in `__init__`.

`mail/transport.py`:

```python
"""Email transport protocol."""

from typing import Protocol

from goatnotify.core.mail.message import EmailMessage


class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> str | None: ...
```

`mail/mailer.py`:

```python
"""Mailer: renders mailables and hands them to a transport."""

from collections.abc import Iterable, Mapping, Sequence

from goatnotify.core.errors import ConfigurationError, InvalidMessageError
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.message import Address, AddressLike, EmailMessage
from goatnotify.core.mail.transport import EmailTransport
from goatnotify.core.templates import TemplateRenderer


class Mailer:
    def __init__(
        self,
        transport: EmailTransport,
        *,
        sender: AddressLike,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._transport = transport
        self._sender = Address.parse(sender)
        self._renderer = renderer

    async def render(self, mailable: Mailable, *, to: Sequence[AddressLike] = ()) -> EmailMessage:
        if not mailable.subject:
            raise InvalidMessageError(f"{type(mailable).__qualname__} has no subject")
        context = mailable.context()
        html = mailable.html()
        if html is None:
            html = await self._render(mailable.template(), context)
        text = mailable.text()
        if text is None:
            text = await self._render(mailable.text_template(), context)
        return EmailMessage(
            subject=mailable.subject,
            sender=self._sender if mailable.sender is None else Address.parse(mailable.sender),
            to=_addresses(to or mailable.to),
            cc=_addresses(mailable.cc),
            bcc=_addresses(mailable.bcc),
            reply_to=_addresses(mailable.reply_to),
            html=html,
            text=text,
            attachments=tuple(mailable.attachments()),
            headers=dict(mailable.headers),
            metadata=dict(mailable.metadata),
        )

    async def send(self, mailable: Mailable, *, to: Sequence[AddressLike] = ()) -> str | None:
        return await self._transport.send(await self.render(mailable, to=to))

    async def _render(self, template: str | None, context: Mapping[str, object]) -> str | None:
        if template is None:
            return None
        if self._renderer is None:
            raise ConfigurationError(
                f"Template {template!r} needs a TemplateRenderer: pass renderer= to Mailer"
            )
        return await self._renderer.render(template, context)


def _addresses(values: Iterable[AddressLike]) -> tuple[Address, ...]:
    return tuple(Address.parse(value) for value in values)
```

`channels/email.py`:

```python
"""Email channel: delivers Mailable messages through a Mailer."""

from goatnotify.core.channel import Channel
from goatnotify.core.errors import SkipDelivery
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.notification import Notifiable
from goatnotify.core.retry import RetryPolicy


class EmailChannel(Channel[Mailable]):
    name = "email"
    message_type = Mailable

    def __init__(self, mailer: Mailer, *, retry: RetryPolicy | None = None) -> None:
        self._mailer = mailer
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: Mailable) -> str | None:
        if message.to:
            return await self._mailer.send(message)
        route = notifiable.route_notification(self.name)
        if route is None:
            raise SkipDelivery(f"{type(notifiable).__qualname__} has no email route")
        return await self._mailer.send(message, to=[route])
```

Append to `testing.py`:

```python
from collections import deque

from goatnotify.core.mail.message import EmailMessage


class MemoryTransport:
    """EmailTransport keeping sent messages in `outbox`."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []
        self._failures: deque[Exception] = deque()

    def fail_next(self, *errors: Exception) -> None:
        self._failures.extend(errors)

    async def send(self, message: EmailMessage) -> str | None:
        if self._failures:
            raise self._failures.popleft()
        self.outbox.append(message)
        return f"memory-{len(self.outbox)}"
```

(Move the imports to the top of the module.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`. If pyright rejects `to = ("ada@example.com",)` in `Raw` as an incompatible override, annotate it in the test (`to: Sequence[AddressLike] = (...)`); do not weaken `Mailable`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add mailables, the mailer and the email channel"
```

---

### Task 7: SMTP transport

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/mail/smtp.py`
- Create: `packages/goatnotify-core/tests/fake_smtp.py`
- Test: `packages/goatnotify-core/tests/test_smtp.py`

**Interfaces:**
- Consumes: `to_mime`, `EmailMessage` (Task 5), errors (Task 2), `logger` name `"goatnotify"`.
- Produces:
  - `type SmtpSecurity = Literal["starttls", "tls", "none"]`
  - `SmtpTransport(host: str, port: int = 587, *, username: str | None = None, password: str | None = None, security: SmtpSecurity = "starttls", timeout: float = 30.0, ssl_context: ssl.SSLContext | None = None)`; `async send(message) -> str | None` returns the `Message-ID`
  - `classify_smtp_error(error: Exception) -> DeliveryError` (reused by the Django transport in Task 13)

- [ ] **Step 1: Write the fake SMTP server**

`packages/goatnotify-core/tests/fake_smtp.py`:

```python
"""Minimal in-process SMTP server for transport tests."""

import asyncio
from dataclasses import dataclass, field


@dataclass
class FakeSmtpServer:
    replies: dict[str, str] = field(default_factory=dict[str, str])
    commands: list[str] = field(default_factory=list[str])
    messages: list[bytes] = field(default_factory=list[bytes])
    port: int = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 fake ESMTP\r\n")
        while line := await reader.readline():
            command = line.decode().strip()
            verb = command.split(" ", 1)[0].upper()
            self.commands.append(command)
            if verb in self.replies:
                writer.write(f"{self.replies[verb]}\r\n".encode())
            elif verb == "DATA":
                writer.write(b"354 go ahead\r\n")
                await writer.drain()
                self.messages.append(await reader.readuntil(b"\r\n.\r\n"))
                writer.write(b"250 queued\r\n")
            elif verb == "QUIT":
                writer.write(b"221 bye\r\n")
                await writer.drain()
                writer.close()
                return
            else:
                writer.write(b"250 ok\r\n")
            await writer.drain()
```

- [ ] **Step 2: Write the failing tests**

`packages/goatnotify-core/tests/test_smtp.py`:

```python
import asyncio
import smtplib
import socket
from collections.abc import AsyncIterator

import pytest
from fake_smtp import FakeSmtpServer

from goatnotify.core.errors import PermanentError, RetryableError
from goatnotify.core.mail.message import Address, EmailMessage
from goatnotify.core.mail.smtp import SmtpTransport, classify_smtp_error

MESSAGE = EmailMessage(
    subject="Hello",
    sender=Address("noreply@goat.dev"),
    to=(Address("ada@example.com"),),
    bcc=(Address("audit@example.com"),),
    text="Hi",
)


@pytest.fixture
async def smtp_server() -> AsyncIterator[FakeSmtpServer]:
    fake = FakeSmtpServer()
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    fake.port = server.sockets[0].getsockname()[1]
    async with server:
        yield fake


def _transport(server: FakeSmtpServer) -> SmtpTransport:
    return SmtpTransport("127.0.0.1", server.port, security="none", timeout=5)


async def test_a_message_is_sent_to_every_recipient(smtp_server: FakeSmtpServer) -> None:
    message_id = await _transport(smtp_server).send(MESSAGE)
    assert message_id is not None and message_id.endswith("@goat.dev>")
    assert "MAIL FROM:<noreply@goat.dev>" in smtp_server.commands
    assert {"RCPT TO:<ada@example.com>", "RCPT TO:<audit@example.com>"} <= set(
        smtp_server.commands
    )
    (data,) = smtp_server.messages
    assert b"Subject: Hello" in data
    assert b"audit@example.com" not in data


async def test_a_temporary_refusal_is_retryable(smtp_server: FakeSmtpServer) -> None:
    smtp_server.replies["MAIL"] = "451 try again later"
    with pytest.raises(RetryableError, match="451"):
        await _transport(smtp_server).send(MESSAGE)


async def test_a_permanent_refusal_is_permanent(smtp_server: FakeSmtpServer) -> None:
    smtp_server.replies["MAIL"] = "550 mailbox unavailable"
    with pytest.raises(PermanentError, match="550"):
        await _transport(smtp_server).send(MESSAGE)


async def test_an_unreachable_server_is_retryable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(RetryableError, match="connection"):
        await SmtpTransport("127.0.0.1", port, security="none", timeout=2).send(MESSAGE)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (smtplib.SMTPAuthenticationError(535, b"bad credentials"), PermanentError),
        (smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no")}), PermanentError),
        (smtplib.SMTPNotSupportedError("no STARTTLS"), PermanentError),
        (smtplib.SMTPDataError(452, b"insufficient storage"), RetryableError),
        (smtplib.SMTPDataError(554, b"rejected"), PermanentError),
        (smtplib.SMTPServerDisconnected("gone"), RetryableError),
        (ConnectionRefusedError("refused"), RetryableError),
        (TimeoutError("slow"), RetryableError),
    ],
)
def test_smtp_errors_are_classified(error: Exception, expected: type[Exception]) -> None:
    assert type(classify_smtp_error(error)) is expected
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_smtp.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.mail.smtp'`

- [ ] **Step 4: Implement**

`mail/smtp.py`:

```python
"""SMTP transport built on smtplib, run in a worker thread."""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage as MimeMessage
from typing import Final, Literal

from goatnotify.core.errors import DeliveryError, PermanentError, RetryableError
from goatnotify.core.mail.message import EmailMessage
from goatnotify.core.mail.mime import to_mime

logger: Final = logging.getLogger("goatnotify")

type SmtpSecurity = Literal["starttls", "tls", "none"]


def classify_smtp_error(error: Exception) -> DeliveryError:
    match error:
        case (
            smtplib.SMTPAuthenticationError()
            | smtplib.SMTPRecipientsRefused()
            | smtplib.SMTPNotSupportedError()
        ):
            return PermanentError(f"SMTP delivery refused: {error}")
        case smtplib.SMTPResponseException(smtp_code=code) if 400 <= code < 500:
            return RetryableError(f"SMTP server answered {code}: {error}")
        case smtplib.SMTPResponseException(smtp_code=code):
            return PermanentError(f"SMTP server answered {code}: {error}")
        case smtplib.SMTPServerDisconnected():
            return RetryableError(f"SMTP connection lost: {error}")
        case smtplib.SMTPException():
            return PermanentError(f"SMTP delivery failed: {error}")
        case OSError():
            return RetryableError(f"SMTP connection failed: {error}")
        case _:
            return PermanentError(f"Unexpected SMTP error: {error!r}")


class SmtpTransport:
    def __init__(
        self,
        host: str,
        port: int = 587,
        *,
        username: str | None = None,
        password: str | None = None,
        security: SmtpSecurity = "starttls",
        timeout: float = 30.0,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._security = security
        self._timeout = timeout
        self._ssl_context = ssl_context

    async def send(self, message: EmailMessage) -> str | None:
        mime = to_mime(message)
        await asyncio.to_thread(self._deliver, mime, message)
        return str(mime["Message-ID"])

    def _deliver(self, mime: MimeMessage, message: EmailMessage) -> None:
        try:
            with self._connect() as smtp:
                if self._username is not None:
                    smtp.login(self._username, self._password or "")
                refused = smtp.send_message(
                    mime,
                    from_addr=message.sender.email,
                    to_addrs=[address.email for address in message.recipients],
                )
        except (smtplib.SMTPException, OSError) as error:
            raise classify_smtp_error(error) from error
        if refused:
            logger.warning("SMTP server refused some recipients: %s", sorted(refused))

    def _connect(self) -> smtplib.SMTP:
        context = self._ssl_context or ssl.create_default_context()
        if self._security == "tls":
            return smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout, context=context)
        smtp = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        if self._security == "starttls":
            try:
                smtp.starttls(context=context)
            except BaseException:
                smtp.close()
                raise
        return smtp
```

Note: `smtplib.SMTPServerDisconnected` is not an `SMTPResponseException`, and `SMTPAuthenticationError` is one, which is why the order of the `case` arms matters.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 6: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the SMTP transport"
```

---

### Task 8: Database channel

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/channels/database.py`
- Modify: `packages/goatnotify-core/src/goatnotify/core/testing.py` (add `MemoryStore`)
- Test: `packages/goatnotify-core/tests/test_database_channel.py`

**Interfaces:**
- Consumes: `JsonValue` (Task 2), `Channel`, `Notifiable`, `Message` (Task 3).
- Produces:
  - `DatabaseMessage(kind: str, data: Mapping[str, JsonValue])`
  - `StoredNotification(id: UUID, kind: str, data: Mapping[str, JsonValue], created_at: datetime)`
  - `NotificationStore` protocol: `async store(self, notifiable: Notifiable, record: StoredNotification) -> None`
  - `DatabaseChannel(store, *, retry=None, clock: Callable[[], datetime] = utc_now)`, `name = "database"`; `send` returns `str(record.id)`
  - `MemoryStore()` with `.records: list[tuple[Notifiable, StoredNotification]]` and `for_notifiable(notifiable) -> list[StoredNotification]` (identity match)

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_database_channel.py`:

```python
from collections.abc import Iterable
from datetime import UTC, datetime

from core_support import User

from goatnotify.core.channels.database import DatabaseChannel, DatabaseMessage
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.testing import MemoryStore

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


class Invoice(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield DatabaseMessage(kind="invoice.paid", data={"amount": 42, "lines": ["a", "b"]})


async def test_the_message_is_stored_for_the_notifiable() -> None:
    store = MemoryStore()
    user = User(email=None)
    notifier = Notifier([DatabaseChannel(store, clock=lambda: NOW)])
    result = await notifier.notify(user, Invoice())
    (record,) = store.for_notifiable(user)
    assert (record.kind, dict(record.data), record.created_at) == (
        "invoice.paid",
        {"amount": 42, "lines": ["a", "b"]},
        NOW,
    )
    assert result.deliveries[0].provider_id == str(record.id)


async def test_records_are_kept_per_notifiable() -> None:
    store = MemoryStore()
    ada, bob = User(), User()
    notifier = Notifier([DatabaseChannel(store)])
    await notifier.notify(ada, Invoice())
    await notifier.notify(ada, Invoice())
    await notifier.notify(bob, Invoice())
    assert len(store.for_notifiable(ada)) == 2
    assert len(store.for_notifiable(bob)) == 1
    assert store.for_notifiable(ada)[0].created_at.tzinfo is UTC
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_database_channel.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.channels.database'`

- [ ] **Step 3: Implement**

`channels/database.py`:

```python
"""Database channel: persists notifications through a NotificationStore."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy


@dataclass(frozen=True, slots=True)
class DatabaseMessage(Message):
    kind: str
    data: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StoredNotification:
    id: UUID
    kind: str
    data: Mapping[str, JsonValue]
    created_at: datetime


class NotificationStore(Protocol):
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class DatabaseChannel(Channel[DatabaseMessage]):
    name = "database"
    message_type = DatabaseMessage

    def __init__(
        self,
        store: NotificationStore,
        *,
        retry: RetryPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._store = store
        self._clock = clock
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: DatabaseMessage) -> str | None:
        record = StoredNotification(
            id=uuid4(), kind=message.kind, data=message.data, created_at=self._clock()
        )
        await self._store.store(notifiable, record)
        return str(record.id)
```

Append to `testing.py` (imports at the top of the module):

```python
from goatnotify.core.channels.database import StoredNotification
from goatnotify.core.notification import Notifiable


class MemoryStore:
    """NotificationStore keeping records in memory."""

    def __init__(self) -> None:
        self.records: list[tuple[Notifiable, StoredNotification]] = []

    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        self.records.append((notifiable, record))

    def for_notifiable(self, notifiable: Notifiable) -> list[StoredNotification]:
        return [record for owner, record in self.records if owner is notifiable]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the database channel and notification store protocol"
```

---

### Task 9: HTTP transport and webhook channel

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/http.py`, `channels/webhook.py`
- Modify: `packages/goatnotify-core/src/goatnotify/core/testing.py` (add `MemoryHttpTransport`)
- Test: `packages/goatnotify-core/tests/test_http.py`, `packages/goatnotify-core/tests/test_webhook_channel.py`

**Interfaces:**
- Consumes: errors (Task 2), `JsonValue`, `Channel` (Task 3).
- Produces:
  - `HttpRequest(method: str, url: str, headers: Mapping[str, str], body: bytes, timeout: float)`
  - `HttpResponse(status: int, headers: Mapping[str, str], body: bytes)` with `header(name: str) -> str | None` (case-insensitive)
  - `HttpTransport` protocol: `async send(self, request: HttpRequest) -> HttpResponse` (non-2xx statuses are returned, network failures raise `OSError`)
  - `UrllibTransport()`; `require_http_url(url: str) -> None` raising `InvalidMessageError`
  - `WebhookMessage(payload: JsonValue, url: str | None = None, headers: Mapping[str, str] = {}, method: Literal["POST", "PUT"] = "POST")`
  - `WebhookChannel(transport: HttpTransport | None = None, *, secret: str | None = None, timeout: float = 10.0, retry: RetryPolicy | None = None, clock: Callable[[], float] = time.time)`, `name = "webhook"`
  - `SIGNATURE_HEADER = "X-GoatNotify-Signature"`, `TIMESTAMP_HEADER = "X-GoatNotify-Timestamp"`, `MAX_RETRY_AFTER = 300.0`
  - `MemoryHttpTransport()` with `.requests: list[HttpRequest]` and `respond(*outcomes: HttpResponse | Exception)`; default response `HttpResponse(200, {}, b"")`

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_http.py`:

```python
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from goatnotify.core.errors import InvalidMessageError
from goatnotify.core.http import HttpRequest, HttpResponse, UrllibTransport


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        status = 500 if self.path == "/fail" else 200
        self.send_response(status)
        self.send_header("X-Echo", self.headers["X-Token"] or "")
        self.end_headers()
        self.wfile.write(body.upper())

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def base_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _request(url: str) -> HttpRequest:
    return HttpRequest(method="POST", url=url, headers={"X-Token": "t"}, body=b"ping", timeout=5)


async def test_a_successful_response(base_url: str) -> None:
    response = await UrllibTransport().send(_request(f"{base_url}/ok"))
    assert (response.status, response.body, response.header("x-echo")) == (200, b"PING", "t")


async def test_error_statuses_are_returned_not_raised(base_url: str) -> None:
    response = await UrllibTransport().send(_request(f"{base_url}/fail"))
    assert response.status == 500


async def test_only_http_urls_are_allowed() -> None:
    with pytest.raises(InvalidMessageError, match="http"):
        await UrllibTransport().send(_request("file:///etc/passwd"))


async def test_network_failures_raise_os_error() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(OSError):
        await UrllibTransport().send(_request(f"http://127.0.0.1:{port}/"))


def test_header_lookup_is_case_insensitive() -> None:
    assert HttpResponse(200, {"Retry-After": "5"}, b"").header("retry-after") == "5"
```

`packages/goatnotify-core/tests/test_webhook_channel.py`:

```python
import hashlib
import hmac
import json
from collections.abc import Iterable

import pytest
from core_support import User

from goatnotify.core.channels.webhook import WebhookChannel, WebhookMessage
from goatnotify.core.errors import InvalidMessageError, PermanentError, RetryableError, SkipDelivery
from goatnotify.core.http import HttpResponse
from goatnotify.core.notification import Message, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.results import DeliveryStatus
from goatnotify.core.testing import MemoryHttpTransport, no_sleep

HOOK = "https://hooks.example.com/api/webhooks/123/SECRET-TOKEN?key=abc"


class Deployed(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield WebhookMessage(payload={"event": "deployed", "version": "1.2.0"})


async def test_the_payload_is_posted_as_compact_json() -> None:
    transport = MemoryHttpTransport()
    await WebhookChannel(transport).send(User(), WebhookMessage({"a": [1, "é"]}, url=HOOK))
    (request,) = transport.requests
    assert (request.method, request.url, request.timeout) == ("POST", HOOK, 10.0)
    assert request.body == '{"a":[1,"é"]}'.encode()
    assert request.headers["Content-Type"] == "application/json"


async def test_the_webhook_route_is_used_when_the_message_has_no_url() -> None:
    transport = MemoryHttpTransport()
    await WebhookChannel(transport).send(User(webhook=HOOK), WebhookMessage({}))
    assert transport.requests[0].url == HOOK


async def test_no_url_and_no_route_is_skipped() -> None:
    with pytest.raises(SkipDelivery, match="no webhook route"):
        await WebhookChannel(MemoryHttpTransport()).send(User(), WebhookMessage({}))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "not a url"])
async def test_non_http_urls_are_rejected(url: str) -> None:
    with pytest.raises(InvalidMessageError):
        await WebhookChannel(MemoryHttpTransport()).send(User(), WebhookMessage({}, url=url))


async def test_requests_are_signed_when_a_secret_is_configured() -> None:
    transport = MemoryHttpTransport()
    channel = WebhookChannel(transport, secret="s3cret", clock=lambda: 1_700_000_000.9)
    await channel.send(User(), WebhookMessage({"a": 1}, url=HOOK, headers={"X-Extra": "1"}))
    (request,) = transport.requests
    expected = hmac.new(b"s3cret", b"1700000000." + request.body, hashlib.sha256).hexdigest()
    assert request.headers["X-GoatNotify-Timestamp"] == "1700000000"
    assert request.headers["X-GoatNotify-Signature"] == f"sha256={expected}"
    assert request.headers["X-Extra"] == "1"


async def test_message_headers_cannot_forge_the_signature() -> None:
    transport = MemoryHttpTransport()
    message = WebhookMessage({}, url=HOOK, headers={"X-GoatNotify-Signature": "forged"})
    await WebhookChannel(transport, secret="s3cret").send(User(), message)
    assert transport.requests[0].headers["X-GoatNotify-Signature"] != "forged"


@pytest.mark.parametrize("status", [408, 429, 500, 503])
async def test_transient_statuses_are_retryable(status: int) -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(status, {}, b"busy"))
    with pytest.raises(RetryableError):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


async def test_retry_after_is_honoured() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(429, {"Retry-After": "7"}, b""))
    with pytest.raises(RetryableError) as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert caught.value.retry_after == 7.0


@pytest.mark.parametrize(("header", "expected"), [("86400", 300.0), ("-5", None), ("soon", None)])
async def test_retry_after_is_capped(header: str, expected: float | None) -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(503, {"Retry-After": header}, b""))
    with pytest.raises(RetryableError) as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert caught.value.retry_after == expected


async def test_client_errors_are_permanent() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(404, {}, b"unknown webhook"))
    with pytest.raises(PermanentError, match="404"):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


async def test_network_errors_are_retryable() -> None:
    transport = MemoryHttpTransport()
    transport.respond(ConnectionResetError("reset"))
    with pytest.raises(RetryableError):
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))


@pytest.mark.parametrize(
    "outcome", [HttpResponse(404, {}, b""), HttpResponse(500, {}, b""), OSError("down")]
)
async def test_errors_do_not_leak_the_webhook_url(outcome: HttpResponse | Exception) -> None:
    transport = MemoryHttpTransport()
    transport.respond(outcome)
    with pytest.raises(Exception) as caught:
        await WebhookChannel(transport).send(User(), WebhookMessage({}, url=HOOK))
    assert "SECRET-TOKEN" not in str(caught.value)
    assert "key=abc" not in str(caught.value)
    assert "hooks.example.com" in str(caught.value)


async def test_end_to_end_retry_then_success() -> None:
    transport = MemoryHttpTransport()
    transport.respond(HttpResponse(502, {}, b""), HttpResponse(204, {}, b""))
    notifier = Notifier([WebhookChannel(transport)], sleep=no_sleep)
    result = await notifier.notify(User(webhook=HOOK), Deployed())
    assert (result.deliveries[0].status, result.deliveries[0].attempts) == (DeliveryStatus.SENT, 2)
    assert json.loads(transport.requests[0].body) == {"event": "deployed", "version": "1.2.0"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_http.py packages/goatnotify-core/tests/test_webhook_channel.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.http'`

- [ ] **Step 3: Implement**

`http.py`:

```python
"""Minimal HTTP transport abstraction shared by webhook and HTTP-based email providers."""

import asyncio
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from goatnotify.core.errors import InvalidMessageError

ALLOWED_SCHEMES = frozenset({"http", "https"})


def require_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.netloc:
        raise InvalidMessageError("Only absolute http and https URLs are allowed")


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout: float


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        return next((v for k, v in self.headers.items() if k.lower() == wanted), None)


class HttpTransport(Protocol):
    async def send(self, request: HttpRequest) -> HttpResponse: ...


class UrllibTransport:
    """HttpTransport on urllib.request, run in a worker thread."""

    async def send(self, request: HttpRequest) -> HttpResponse:
        require_http_url(request.url)
        return await asyncio.to_thread(self._send, request)

    def _send(self, request: HttpRequest) -> HttpResponse:
        prepared = urllib.request.Request(  # noqa: S310 (scheme checked by require_http_url)
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            with urllib.request.urlopen(prepared, timeout=request.timeout) as response:  # noqa: S310
                return HttpResponse(response.status, dict(response.headers.items()), response.read())
        except urllib.error.HTTPError as error:
            with error:
                return HttpResponse(error.code, dict(error.headers.items()), error.read())
```

`channels/webhook.py`:

```python
"""Webhook channel: posts JSON payloads over an HttpTransport."""

import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final, Literal
from urllib.parse import urlsplit

from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.errors import PermanentError, RetryableError, SkipDelivery
from goatnotify.core.http import (
    HttpRequest,
    HttpResponse,
    HttpTransport,
    UrllibTransport,
    require_http_url,
)
from goatnotify.core.notification import Message, Notifiable
from goatnotify.core.retry import RetryPolicy

SIGNATURE_HEADER: Final = "X-GoatNotify-Signature"
TIMESTAMP_HEADER: Final = "X-GoatNotify-Timestamp"
MAX_RETRY_AFTER: Final = 300.0
RETRYABLE_STATUSES: Final = frozenset({408, 429})
ERROR_BODY_LIMIT: Final = 200


@dataclass(frozen=True, slots=True)
class WebhookMessage(Message):
    payload: JsonValue
    url: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    method: Literal["POST", "PUT"] = "POST"


class WebhookChannel(Channel[WebhookMessage]):
    name = "webhook"
    message_type = WebhookMessage

    def __init__(
        self,
        transport: HttpTransport | None = None,
        *,
        secret: str | None = None,
        timeout: float = 10.0,
        retry: RetryPolicy | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._secret = secret
        self._timeout = timeout
        self._clock = clock
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: WebhookMessage) -> str | None:
        url = message.url or notifiable.route_notification(self.name)
        if url is None:
            raise SkipDelivery(f"{type(notifiable).__qualname__} has no webhook route")
        require_http_url(url)
        body = json.dumps(message.payload, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json", **message.headers, **self._sign(body)}
        # Webhook URLs often embed credentials (Discord, Slack), so errors only name the host.
        host = urlsplit(url).netloc
        try:
            response = await self._transport.send(
                HttpRequest(message.method, url, headers, body, self._timeout)
            )
        except OSError as error:
            raise RetryableError(f"Webhook request to {host} failed: {error}") from error
        _raise_for_status(response, host)
        return None

    def _sign(self, body: bytes) -> dict[str, str]:
        if self._secret is None:
            return {}
        timestamp = str(int(self._clock()))
        digest = hmac.new(
            self._secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return {TIMESTAMP_HEADER: timestamp, SIGNATURE_HEADER: f"sha256={digest}"}


def _raise_for_status(response: HttpResponse, host: str) -> None:
    if 200 <= response.status < 300:
        return
    detail = f"Webhook {host} answered {response.status}: {response.body[:ERROR_BODY_LIMIT]!r}"
    if response.status in RETRYABLE_STATUSES or response.status >= 500:
        raise RetryableError(detail, retry_after=_retry_after(response))
    raise PermanentError(detail)


def _retry_after(response: HttpResponse) -> float | None:
    value = response.header("Retry-After")
    if value is None or not value.strip().isdigit():
        return None
    return min(float(value), MAX_RETRY_AFTER)
```

`OSError` raised from `str(error)` may itself contain the URL (urllib includes it in some messages). If `test_errors_do_not_leak_the_webhook_url` fails for the `OSError` case, drop `{error}` and use `{type(error).__name__}` instead.

Append to `testing.py` (imports at the top of the module):

```python
from goatnotify.core.http import HttpRequest, HttpResponse

OK = HttpResponse(200, {}, b"")


class MemoryHttpTransport:
    """HttpTransport recording requests and replaying scripted outcomes."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self._outcomes: deque[HttpResponse | Exception] = deque()

    def respond(self, *outcomes: HttpResponse | Exception) -> None:
        self._outcomes.extend(outcomes)

    async def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        outcome = self._outcomes.popleft() if self._outcomes else OK
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the HTTP transport and the webhook channel"
```

---

### Task 10: Queues

**Files:**
- Create: `packages/goatnotify-core/src/goatnotify/core/queue.py`
- Modify: `packages/goatnotify-core/src/goatnotify/core/notifier.py` (add `queue=`, `queue` property, `enqueue()`)
- Test: `packages/goatnotify-core/tests/test_queue.py`

**Interfaces:**
- Consumes: `Notifier` (Task 4).
- Produces:
  - `NotificationJob[R: Notifiable](notifier: Notifier, notifiable: R, notification: Notification[R])` with `async run() -> NotificationResult`
  - `Queue` protocol: `async enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None`
  - `ClosableQueue(Queue)` runtime-checkable protocol adding `async aclose() -> None`
  - `AsyncioQueue(*, concurrency: int = 10)` with `enqueue`, `drain()`, `aclose()`, async context manager
  - `Notifier(..., queue: Queue | None = None)`, `Notifier.queue -> Queue | None`, `async Notifier.enqueue[R](notifiable: R, notification: Notification[R]) -> None`

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-core/tests/test_queue.py`:

```python
import asyncio
import gc
import logging
from typing import Any

import pytest
from core_support import Ping, PingChannel, Pings, User

from goatnotify.core.errors import ConfigurationError, PermanentError
from goatnotify.core.notification import Notifiable
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import AsyncioQueue, ClosableQueue


async def test_enqueue_without_a_queue_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="queue"):
        await Notifier([PingChannel()]).enqueue(User(), Pings("x"))


async def test_jobs_run_in_the_background_and_drain_waits_for_them() -> None:
    queue = AsyncioQueue()
    channel = PingChannel()
    notifier = Notifier([channel], queue=queue)
    await notifier.enqueue(User(), Pings("later"))
    assert channel.sent == []
    await queue.drain()
    assert channel.sent == [Ping("later")]
    assert notifier.queue is queue


async def test_background_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    loop_errors: list[dict[str, Any]] = []
    asyncio.get_running_loop().set_exception_handler(lambda _, context: loop_errors.append(context))
    queue = AsyncioQueue()
    notifier = Notifier([PingChannel(PermanentError("rejected"))], queue=queue)
    with caplog.at_level(logging.ERROR, logger="goatnotify"):
        await notifier.enqueue(User(), Pings("x"))
        await queue.drain()
    gc.collect()
    assert "Queued notification Pings failed" in caplog.text
    assert loop_errors == []


async def test_a_closed_queue_rejects_new_jobs() -> None:
    async with AsyncioQueue() as queue:
        notifier = Notifier([PingChannel()], queue=queue)
    with pytest.raises(ConfigurationError, match="closed"):
        await notifier.enqueue(User(), Pings("x"))


async def test_concurrency_is_bounded() -> None:
    running = 0
    peak = 0

    class Slow(PingChannel):
        async def send(self, notifiable: Notifiable, message: Ping) -> str | None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            return None

    queue = AsyncioQueue(concurrency=2)
    notifier = Notifier([Slow()], queue=queue)
    for index in range(6):
        await notifier.enqueue(User(), Pings(str(index)))
    await queue.drain()
    assert peak == 2


def test_asyncio_queue_is_closable_and_validates_concurrency() -> None:
    assert isinstance(AsyncioQueue(), ClosableQueue)
    with pytest.raises(ValueError, match="concurrency"):
        AsyncioQueue(concurrency=0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-core/tests/test_queue.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.core.queue'`

- [ ] **Step 3: Implement**

`queue.py`:

```python
"""Background dispatch of notifications."""

import asyncio
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Final, Protocol, Self, runtime_checkable

from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable, Notification
from goatnotify.core.results import NotificationResult

if TYPE_CHECKING:
    from goatnotify.core.notifier import Notifier

logger: Final = logging.getLogger("goatnotify")


@dataclass(frozen=True, slots=True)
class NotificationJob[R: Notifiable]:
    notifier: Notifier
    notifiable: R
    notification: Notification[R]

    async def run(self) -> NotificationResult:
        return await self.notifier.notify(self.notifiable, self.notification)


class Queue(Protocol):
    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None: ...


@runtime_checkable
class ClosableQueue(Queue, Protocol):
    async def aclose(self) -> None: ...


class AsyncioQueue:
    """In-process queue running jobs as asyncio tasks; drain or close it on shutdown."""

    def __init__(self, *, concurrency: int = 10) -> None:
        if concurrency < 1:
            raise ValueError("AsyncioQueue.concurrency must be at least 1")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        if self._closed:
            raise ConfigurationError("AsyncioQueue is closed")
        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def aclose(self) -> None:
        self._closed = True
        await self.drain()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _run[R: Notifiable](self, job: NotificationJob[R]) -> None:
        async with self._semaphore:
            try:
                await job.run()
            except Exception:
                logger.exception(
                    "Queued notification %s failed", type(job.notification).__qualname__
                )
```

In `notifier.py`: import `from goatnotify.core.queue import NotificationJob, Queue`; add the keyword parameter `queue: Queue | None = None` after `hooks`, store it as `self._queue`, and add:

```python
    @property
    def queue(self) -> Queue | None:
        return self._queue

    async def enqueue[R: Notifiable](self, notifiable: R, notification: Notification[R]) -> None:
        if self._queue is None:
            raise ConfigurationError("No queue configured: pass queue= to Notifier")
        await self._queue.enqueue(NotificationJob(self, notifiable, notification))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-core -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core
git commit -m "feat(core): add the queue protocol and the asyncio reference queue"
```

---

### Task 11: Public API and facade

**Files:**
- Modify: `packages/goatnotify-core/src/goatnotify/core/__init__.py`, `packages/goatnotify/src/goatnotify/__init__.py`
- Test: `packages/goatnotify-core/tests/test_public_api.py`

**Interfaces:**
- Produces: `from goatnotify import <name>` and `from goatnotify.core import <name>` for every name in `PUBLIC` below. `goatnotify.core.testing` stays a separate module.

- [ ] **Step 1: Write the failing test**

`packages/goatnotify-core/tests/test_public_api.py`:

```python
import goatnotify
import goatnotify.core

PUBLIC = {
    "NO_RETRY", "Address", "AsyncioQueue", "Attachment", "Backoff", "Channel", "ClosableQueue",
    "ConfigurationError", "DatabaseChannel", "DatabaseMessage", "DeliveryError", "DeliveryFailed",
    "DeliveryResult", "DeliveryStatus", "EmailChannel", "EmailMessage", "EmailTransport", "Event",
    "ExponentialBackoff", "Hook", "HttpRequest", "HttpResponse", "HttpTransport",
    "InvalidMessageError", "JsonValue", "Mailable", "Mailer", "Message", "Notifiable",
    "Notification", "NotificationError", "NotificationJob", "NotificationResult",
    "NotificationStore", "Notifier", "PermanentError", "Queue", "RetryPolicy", "RetryableError",
    "SkipDelivery", "SmtpTransport", "StoredNotification", "TemplateRenderer", "UrllibTransport",
    "WebhookChannel", "WebhookMessage", "events", "to_mime",
}


def test_the_core_exports_the_public_api() -> None:
    assert set(goatnotify.core.__all__) == PUBLIC
    assert all(hasattr(goatnotify.core, name) for name in PUBLIC)


def test_the_facade_re_exports_the_core() -> None:
    assert set(goatnotify.__all__) == PUBLIC
    assert all(getattr(goatnotify, name) is getattr(goatnotify.core, name) for name in PUBLIC)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/goatnotify-core/tests/test_public_api.py -q`
Expected: FAIL with `AttributeError: module 'goatnotify.core' has no attribute '__all__'`

- [ ] **Step 3: Implement**

`packages/goatnotify-core/src/goatnotify/core/__init__.py`:

```python
"""Framework-agnostic core of GoatNotify."""

from goatnotify.core import events
from goatnotify.core._json import JsonValue
from goatnotify.core.channel import Channel
from goatnotify.core.channels.database import (
    DatabaseChannel,
    DatabaseMessage,
    NotificationStore,
    StoredNotification,
)
from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.channels.webhook import WebhookChannel, WebhookMessage
from goatnotify.core.errors import (
    ConfigurationError,
    DeliveryError,
    DeliveryFailed,
    InvalidMessageError,
    NotificationError,
    PermanentError,
    RetryableError,
    SkipDelivery,
)
from goatnotify.core.events import Event, Hook
from goatnotify.core.http import HttpRequest, HttpResponse, HttpTransport, UrllibTransport
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.mail.message import Address, Attachment, EmailMessage
from goatnotify.core.mail.mime import to_mime
from goatnotify.core.mail.smtp import SmtpTransport
from goatnotify.core.mail.transport import EmailTransport
from goatnotify.core.notification import Message, Notifiable, Notification
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import AsyncioQueue, ClosableQueue, NotificationJob, Queue
from goatnotify.core.results import DeliveryResult, DeliveryStatus, NotificationResult
from goatnotify.core.retry import NO_RETRY, Backoff, ExponentialBackoff, RetryPolicy
from goatnotify.core.templates import TemplateRenderer

__all__ = [
    "NO_RETRY",
    "Address",
    "AsyncioQueue",
    "Attachment",
    "Backoff",
    "Channel",
    "ClosableQueue",
    "ConfigurationError",
    "DatabaseChannel",
    "DatabaseMessage",
    "DeliveryError",
    "DeliveryFailed",
    "DeliveryResult",
    "DeliveryStatus",
    "EmailChannel",
    "EmailMessage",
    "EmailTransport",
    "Event",
    "ExponentialBackoff",
    "Hook",
    "HttpRequest",
    "HttpResponse",
    "HttpTransport",
    "InvalidMessageError",
    "JsonValue",
    "Mailable",
    "Mailer",
    "Message",
    "Notifiable",
    "Notification",
    "NotificationError",
    "NotificationJob",
    "NotificationResult",
    "NotificationStore",
    "Notifier",
    "PermanentError",
    "Queue",
    "RetryPolicy",
    "RetryableError",
    "SkipDelivery",
    "SmtpTransport",
    "StoredNotification",
    "TemplateRenderer",
    "UrllibTransport",
    "WebhookChannel",
    "WebhookMessage",
    "events",
    "to_mime",
]
```

Append to `packages/goatnotify/src/goatnotify/__init__.py`, after the `extend_path` line, the same import block written as `from goatnotify.core import (...)` with the same names, and the same `__all__` list. Let ruff sort both (`RUF022` sorts `__all__`).

If an import cycle appears (`ImportError: cannot import name ... from partially initialized module`), the culprit is a submodule importing a name from `goatnotify.core` instead of from its defining submodule; fix that submodule's import.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-core packages/goatnotify
git commit -m "feat: expose the public API from goatnotify and goatnotify.core"
```

---

### Task 12: Jinja renderer

**Files:**
- Modify: `packages/goatnotify-jinja/src/goatnotify/jinja/__init__.py`
- Test: `packages/goatnotify-jinja/tests/test_jinja.py`

**Interfaces:**
- Consumes: `TemplateRenderer` protocol, `Mailer`, `Mailable`, `MemoryTransport`.
- Produces: `JinjaRenderer(environment: jinja2.Environment)`, `JinjaRenderer.from_directory(directory: str | Path, *, enable_async: bool = True) -> Self`, `async render(template, context) -> str`.

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-jinja/tests/test_jinja.py`:

```python
from collections.abc import Mapping
from pathlib import Path

import jinja2
import pytest

from goatnotify import Mailable, Mailer, TemplateRenderer
from goatnotify.core.testing import MemoryTransport
from goatnotify.jinja import JinjaRenderer

TEMPLATES = {"hello.html": "<p>Hello {{ name }}</p>", "hello.txt": "Hello {{ name }}"}


@pytest.mark.parametrize("enable_async", [True, False])
async def test_templates_render_in_both_environment_modes(enable_async: bool) -> None:
    environment = jinja2.Environment(
        loader=jinja2.DictLoader(TEMPLATES), enable_async=enable_async, autoescape=True
    )
    renderer = JinjaRenderer(environment)
    assert await renderer.render("hello.txt", {"name": "Ada"}) == "Hello Ada"


async def test_from_directory_escapes_html_but_not_text(tmp_path: Path) -> None:
    for name, source in TEMPLATES.items():
        (tmp_path / name).write_text(source, encoding="utf-8")
    renderer = JinjaRenderer.from_directory(tmp_path)
    context = {"name": "<script>"}
    assert await renderer.render("hello.html", context) == "<p>Hello &lt;script&gt;</p>"
    assert await renderer.render("hello.txt", context) == "Hello <script>"


async def test_missing_variables_are_errors(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("Hello {{ name }}", encoding="utf-8")
    with pytest.raises(jinja2.UndefinedError):
        await JinjaRenderer.from_directory(tmp_path).render("hello.txt", {})


async def test_the_renderer_plugs_into_the_mailer(tmp_path: Path) -> None:
    for name, source in TEMPLATES.items():
        (tmp_path / name).write_text(source, encoding="utf-8")

    class Hello(Mailable):
        subject = "Hello"

        def template(self) -> str | None:
            return "hello.html"

        def text_template(self) -> str | None:
            return "hello.txt"

        def context(self) -> Mapping[str, object]:
            return {"name": "Zoé"}

    renderer: TemplateRenderer = JinjaRenderer.from_directory(tmp_path)
    mailer = Mailer(MemoryTransport(), sender="noreply@goat.dev", renderer=renderer)
    message = await mailer.render(Hello(), to=["zoe@example.com"])
    assert (message.html, message.text) == ("<p>Hello Zoé</p>", "Hello Zoé")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-jinja -q`
Expected: FAIL with `ImportError: cannot import name 'JinjaRenderer'`

- [ ] **Step 3: Implement**

`packages/goatnotify-jinja/src/goatnotify/jinja/__init__.py`:

```python
"""Jinja2 template renderer for GoatNotify."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Self

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

__all__ = ["JinjaRenderer"]


class JinjaRenderer:
    def __init__(self, environment: Environment) -> None:
        self._environment = environment

    @classmethod
    def from_directory(cls, directory: str | Path, *, enable_async: bool = True) -> Self:
        return cls(
            Environment(
                loader=FileSystemLoader(directory),
                autoescape=select_autoescape(("html", "htm", "xml")),
                undefined=StrictUndefined,
                enable_async=enable_async,
            )
        )

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        compiled = self._environment.get_template(template)
        if self._environment.is_async:
            return await compiled.render_async(dict(context))
        return await asyncio.to_thread(compiled.render, dict(context))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-jinja -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: `5 passed`, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-jinja
git commit -m "feat(jinja): add the Jinja2 template renderer"
```

---

### Task 13: Django email, templates and ORM store

**Files:**
- Create: `packages/goatnotify-django/src/goatnotify/django/apps.py`, `mail.py`, `templates.py`, `notifiable.py`, `models.py`, `store.py`, `migrations/__init__.py`, `migrations/0001_initial.py` (generated)
- Create: `packages/goatnotify-django/tests/conftest.py`, `packages/goatnotify-django/tests/goatnotify_testapp/__init__.py`, `goatnotify_testapp/models.py`
- Test: `packages/goatnotify-django/tests/test_django_mail.py`, `packages/goatnotify-django/tests/test_django_store.py`

**Interfaces:**
- Consumes: core public API, `classify_smtp_error` from `goatnotify.core.mail.smtp`.
- Produces:
  - `GoatNotifyConfig` (app `goatnotify.django`, label `goatnotify`)
  - `DjangoEmailTransport(*, connection: BaseEmailBackend | None = None)` implementing `EmailTransport`
  - `DjangoTemplateRenderer(*, using: str | None = None)` implementing `TemplateRenderer`
  - `NotifiableModel` mixin (routes `"email"` to a non-empty `email` attribute)
  - `NotificationRecord` model (table `goatnotify_notification`) with manager `objects: NotificationRecordManager` offering `for_recipient(obj)`; queryset methods `for_recipient`, `unread`, `mark_as_read() -> int`
  - `DjangoNotificationStore()` implementing `NotificationStore`
  - test app model `goatnotify_testapp.models.Member(NotifiableModel, Model)` with `email`, `webhook_url`

- [ ] **Step 1: Test configuration and test app**

`packages/goatnotify-django/tests/goatnotify_testapp/__init__.py`: empty.

`packages/goatnotify-django/tests/goatnotify_testapp/models.py`:

```python
from django.db import models

from goatnotify.django.notifiable import NotifiableModel


class Member(NotifiableModel, models.Model):
    email = models.EmailField(blank=True)
    webhook_url = models.URLField(blank=True)

    def route_notification(self, channel: str) -> str | None:
        if channel == "webhook":
            return self.webhook_url or None
        return super().route_notification(channel)
```

`packages/goatnotify-django/tests/conftest.py`:

```python
import tempfile
from collections.abc import Iterator
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command

TEMPLATES = {
    "emails/welcome.html": "<p>Welcome {{ name }}</p>",
    "emails/welcome.txt": "Welcome {{ name }}",
}

if not settings.configured:
    # A file database, because sync_to_async threads would each see their own :memory: one.
    settings.configure(
        SECRET_KEY="goatnotify-tests",
        INSTALLED_APPS=["django.contrib.contenttypes", "goatnotify.django", "goatnotify_testapp"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(Path(tempfile.mkdtemp()) / "db.sqlite3"),
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Goat <noreply@goat.dev>",
        TASKS={"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}},
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
    from goatnotify.django.models import NotificationRecord
    from goatnotify_testapp.models import Member

    mail.outbox = []
    yield
    NotificationRecord.objects.all().delete()
    Member.objects.all().delete()
```

- [ ] **Step 2: Write the failing tests**

`packages/goatnotify-django/tests/test_django_mail.py`:

```python
import smtplib
from collections.abc import Iterable, Mapping, Sequence

import pytest
from django.core import mail
from django.core.mail import EmailMessage as DjangoEmail
from django.core.mail.backends.base import BaseEmailBackend
from goatnotify_testapp.models import Member

from goatnotify import (
    Address,
    Attachment,
    EmailChannel,
    EmailMessage,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
    RetryableError,
)
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.templates import DjangoTemplateRenderer

MESSAGE = EmailMessage(
    subject="Hello",
    sender=Address("noreply@goat.dev", "Goat"),
    to=(Address("ada@example.com", "Ada"),),
    cc=(Address("cc@example.com"),),
    bcc=(Address("audit@example.com"),),
    reply_to=(Address("support@goat.dev"),),
    text="Hi",
    html="<p>Hi</p>",
    attachments=(Attachment("a.txt", b"a", "text/plain"),),
    headers={"X-Campaign": "hello"},
)


class Broken(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[DjangoEmail]) -> int:
        raise smtplib.SMTPServerDisconnected("gone")


async def test_the_message_goes_through_the_django_backend() -> None:
    message_id = await DjangoEmailTransport().send(MESSAGE)
    (sent,) = mail.outbox
    assert sent.subject == "Hello"
    assert sent.from_email == "Goat <noreply@goat.dev>"
    assert (sent.to, sent.cc, sent.bcc, sent.reply_to) == (
        ["Ada <ada@example.com>"],
        ["cc@example.com"],
        ["audit@example.com"],
        ["support@goat.dev"],
    )
    assert sent.body == "Hi"
    assert sent.alternatives[0].content == "<p>Hi</p>"
    assert sent.attachments[0].filename == "a.txt"
    assert sent.extra_headers["X-Campaign"] == "hello"
    assert sent.extra_headers["Message-ID"] == message_id


async def test_html_only_messages_use_an_html_body() -> None:
    await DjangoEmailTransport().send(
        EmailMessage(subject="x", sender=Address("a@goat.dev"), to=(Address("b@c.d"),), html="<b>x</b>")
    )
    assert mail.outbox[0].content_subtype == "html"


async def test_backend_errors_are_classified() -> None:
    with pytest.raises(RetryableError):
        await DjangoEmailTransport(connection=Broken()).send(MESSAGE)


async def test_django_templates_render_mailables() -> None:
    class Welcome(Mailable):
        subject = "Welcome"

        def template(self) -> str | None:
            return "emails/welcome.html"

        def text_template(self) -> str | None:
            return "emails/welcome.txt"

        def context(self) -> Mapping[str, object]:
            return {"name": "Zoé"}

    class Joined(Notification[Member]):
        def messages(self, notifiable: Member) -> Iterable[Message]:
            yield Welcome()

    member = await Member.objects.acreate(email="zoe@example.com")
    mailer = Mailer(DjangoEmailTransport(), sender="noreply@goat.dev", renderer=DjangoTemplateRenderer())
    await Notifier([EmailChannel(mailer)]).notify(member, Joined())
    (sent,) = mail.outbox
    assert (sent.to, sent.body, sent.alternatives[0].content) == (
        ["zoe@example.com"],
        "Welcome Zoé",
        "<p>Welcome Zoé</p>",
    )
```

`packages/goatnotify-django/tests/test_django_store.py`:

```python
from collections.abc import Iterable

import pytest
from django.core.management import call_command
from goatnotify_testapp.models import Member

from goatnotify import (
    ConfigurationError,
    DatabaseChannel,
    DatabaseMessage,
    Message,
    Notifiable,
    Notification,
    Notifier,
)
from goatnotify.django.models import NotificationRecord
from goatnotify.django.store import DjangoNotificationStore


class Paid(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield DatabaseMessage(kind="invoice.paid", data={"amount": 42})


class Plain:
    def route_notification(self, channel: str) -> str | None:
        return None


async def test_records_are_stored_for_the_recipient() -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    bob = await Member.objects.acreate(email="bob@example.com")
    notifier = Notifier([DatabaseChannel(DjangoNotificationStore())])
    result = await notifier.notify(ada, Paid())
    await notifier.notify(bob, Paid())
    records = [record async for record in NotificationRecord.objects.for_recipient(ada)]
    assert len(records) == 1
    assert (records[0].kind, records[0].data, str(records[0].id)) == (
        "invoice.paid",
        {"amount": 42},
        result.deliveries[0].provider_id,
    )


def test_unread_and_mark_as_read() -> None:
    ada = Member.objects.create(email="ada@example.com")
    Notifier([DatabaseChannel(DjangoNotificationStore())]).notify_sync(ada, Paid())
    assert NotificationRecord.objects.for_recipient(ada).unread().count() == 1
    assert NotificationRecord.objects.for_recipient(ada).mark_as_read() == 1
    assert NotificationRecord.objects.for_recipient(ada).unread().count() == 0


async def test_a_non_model_recipient_is_a_configuration_error() -> None:
    notifier = Notifier([DatabaseChannel(DjangoNotificationStore())])
    result = await notifier.notify(Plain(), Paid(), raise_on_failure=False)
    assert isinstance(result.deliveries[0].error, ConfigurationError)


def test_migrations_are_up_to_date() -> None:
    try:
        call_command("makemigrations", "goatnotify", check=True, dry_run=True, verbosity=0)
    except SystemExit as exit_:
        pytest.fail(f"Missing migration for goatnotify (exit code {exit_.code})")
```

Note: `test_unread_and_mark_as_read` is a sync test calling `notify_sync`: `asyncio.run` runs the store in a thread through `sync_to_async`, and the main thread does the sync ORM reads with no running loop, which Django allows.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-django -q`
Expected: FAIL during collection with `ModuleNotFoundError: No module named 'goatnotify.django.notifiable'`

- [ ] **Step 4: Implement**

`apps.py`:

```python
from django.apps import AppConfig


class GoatNotifyConfig(AppConfig):
    name = "goatnotify.django"
    label = "goatnotify"
    verbose_name = "GoatNotify"
    default_auto_field = "django.db.models.BigAutoField"
```

`notifiable.py`:

```python
"""Notifiable mixin for Django models."""


class NotifiableModel:
    """Routes the email channel to the model's `email` attribute; override for other channels."""

    def route_notification(self, channel: str) -> str | None:
        if channel != "email":
            return None
        email = getattr(self, "email", None)
        return email if isinstance(email, str) and email else None
```

`mail.py`:

```python
"""EmailTransport sending through the configured Django email backend."""

import smtplib
from email.utils import make_msgid

from asgiref.sync import sync_to_async
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend

from goatnotify.core.errors import PermanentError
from goatnotify.core.mail.message import Address, EmailMessage
from goatnotify.core.mail.smtp import classify_smtp_error


def _formatted(addresses: tuple[Address, ...]) -> list[str]:
    return [str(address) for address in addresses]


class DjangoEmailTransport:
    def __init__(self, *, connection: BaseEmailBackend | None = None) -> None:
        self._connection = connection

    async def send(self, message: EmailMessage) -> str | None:
        return await sync_to_async(self._send)(message)

    def _send(self, message: EmailMessage) -> str:
        message_id = message.headers.get("Message-ID") or make_msgid(
            domain=message.sender.email.rpartition("@")[2]
        )
        email = EmailMultiAlternatives(
            subject=message.subject,
            body=message.text if message.text is not None else message.html or "",
            from_email=str(message.sender),
            to=_formatted(message.to),
            cc=_formatted(message.cc),
            bcc=_formatted(message.bcc),
            reply_to=_formatted(message.reply_to),
            headers={**message.headers, "Message-ID": message_id},
            connection=self._connection,
        )
        if message.text is None:
            email.content_subtype = "html"
        elif message.html is not None:
            email.attach_alternative(message.html, "text/html")
        for attachment in message.attachments:
            email.attach(attachment.filename, attachment.content, attachment.mimetype)
        try:
            sent = email.send()
        except (smtplib.SMTPException, OSError) as error:
            raise classify_smtp_error(error) from error
        if sent == 0:
            raise PermanentError("The Django email backend accepted no message")
        return message_id
```

`templates.py`:

```python
"""TemplateRenderer backed by the Django template engines."""

from collections.abc import Mapping

from asgiref.sync import sync_to_async
from django.template.loader import render_to_string


class DjangoTemplateRenderer:
    def __init__(self, *, using: str | None = None) -> None:
        self._using = using

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        return await sync_to_async(render_to_string)(template, dict(context), using=self._using)
```

`models.py`:

```python
"""Database table backing DjangoNotificationStore."""

import uuid
from typing import Self

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class NotificationRecordQuerySet(models.QuerySet["NotificationRecord"]):
    def for_recipient(self, recipient: models.Model) -> Self:
        return self.filter(
            content_type=ContentType.objects.get_for_model(recipient),
            object_id=str(recipient.pk),
        )

    def unread(self) -> Self:
        return self.filter(read_at__isnull=True)

    def mark_as_read(self) -> int:
        return self.unread().update(read_at=timezone.now())


class NotificationRecordManager(models.Manager["NotificationRecord"]):
    def get_queryset(self) -> NotificationRecordQuerySet:
        return NotificationRecordQuerySet(self.model, using=self._db)

    def for_recipient(self, recipient: models.Model) -> NotificationRecordQuerySet:
        return self.get_queryset().for_recipient(recipient)


class NotificationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    recipient = GenericForeignKey("content_type", "object_id")
    kind = models.CharField(max_length=255)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationRecordManager()

    class Meta:
        db_table = "goatnotify_notification"
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("content_type", "object_id", "-created_at"),
                name="goatnotify_recipient_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.kind} for {self.content_type_id}:{self.object_id}"
```

`store.py`:

```python
"""NotificationStore persisting to the NotificationRecord model."""

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from django.db import models

from goatnotify.core.channels.database import StoredNotification
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable
from goatnotify.django.models import NotificationRecord


class DjangoNotificationStore:
    async def store(self, notifiable: Notifiable, record: StoredNotification) -> None:
        if not isinstance(notifiable, models.Model) or notifiable.pk is None:
            raise ConfigurationError(
                f"DjangoNotificationStore needs a saved model instance, got {type(notifiable).__qualname__}"
            )
        await sync_to_async(self._store)(notifiable, record)

    def _store(self, recipient: models.Model, record: StoredNotification) -> None:
        NotificationRecord.objects.create(
            id=record.id,
            content_type=ContentType.objects.get_for_model(recipient),
            object_id=str(recipient.pk),
            kind=record.kind,
            data=dict(record.data),
            created_at=record.created_at,
        )
```

Generate the migration:

```bash
uv run python -c "
import django
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.contenttypes', 'goatnotify.django'], DEFAULT_AUTO_FIELD='django.db.models.BigAutoField')
django.setup()
from django.core.management import call_command
call_command('makemigrations', 'goatnotify', name='initial')
"
touch packages/goatnotify-django/src/goatnotify/django/migrations/__init__.py
uv run ruff format packages/goatnotify-django/src/goatnotify/django/migrations
```

Expected: `packages/goatnotify-django/src/goatnotify/django/migrations/0001_initial.py` created. If `makemigrations` complains that the migrations package is missing, create `migrations/__init__.py` first and rerun.

Pyright strict notes: `django-stubs` types most of this. If pyright reports `reportUnknownMemberType` on `self._db` or `ContentType.objects`, prefer a typed local (`manager: models.Manager[ContentType] = ContentType.objects`) over `# pyright: ignore`; use a targeted `# pyright: ignore[rule]` with the reason only as a last resort.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-django -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`.

- [ ] **Step 6: Commit**

```bash
git add packages/goatnotify-django
git commit -m "feat(django): add the email transport, template renderer and ORM store"
```

---

### Task 14: Django Tasks queue and default notifier

**Files:**
- Create: `packages/goatnotify-django/src/goatnotify/django/serialization.py`, `tasks.py`, `queue.py`, `notifier.py`
- Modify: `packages/goatnotify-django/src/goatnotify/django/apps.py` (connect `setting_changed` in `ready()`)
- Create: `packages/goatnotify-django/tests/goatnotify_testapp/notifications.py`
- Test: `packages/goatnotify-django/tests/test_django_tasks.py`

**Interfaces:**
- Consumes: Task 13, `Notifier.enqueue`, `NotificationJob` (Task 10).
- Produces:
  - `dump_model(instance) -> dict[str, JsonValue]`, `load_notifiable(reference) -> Notifiable`, `dump_notification(notification) -> dict[str, JsonValue]`, `load_notification(payload) -> Notification[Any]`, `MODEL_KEY = "__model__"`
  - task `deliver_notification(notifiable: dict[str, JsonValue], notification: dict[str, JsonValue])` (async Django task)
  - `DjangoTasksQueue(*, queue_name: str | None = None, priority: int | None = None, backend: str | None = None)` implementing `Queue`
  - `get_notifier() -> Notifier` (cached), `default_notifier() -> Notifier`, `reset_notifier_on_setting_change(sender, *, setting, **kwargs)`; setting `GOATNOTIFY_NOTIFIER`

- [ ] **Step 1: Test notifications**

`packages/goatnotify-django/tests/goatnotify_testapp/notifications.py`:

```python
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    DatabaseChannel,
    DatabaseMessage,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
)
from goatnotify.core.testing import MemoryStore, MemoryTransport
from goatnotify_testapp.models import Member


class WelcomeMail(Mailable):
    subject = "Welcome"

    def __init__(self, plan: str) -> None:
        self.plan = plan

    def text(self) -> str | None:
        return f"Welcome on the {self.plan} plan"


@dataclass
class Welcome(Notification[Member]):
    plan: str
    referrer: Member | None = None

    def messages(self, notifiable: Member) -> Iterable[Message]:
        yield WelcomeMail(self.plan)
        referrer = None if self.referrer is None else self.referrer.email
        yield DatabaseMessage(kind="welcome", data={"plan": self.plan, "referrer": referrer})


MEMORY = MemoryTransport()


def build_notifier() -> Notifier:
    return Notifier(
        [EmailChannel(Mailer(MEMORY, sender="noreply@goat.dev")), DatabaseChannel(MemoryStore())]
    )


def build_nothing() -> object:
    return object()
```

- [ ] **Step 2: Write the failing tests**

`packages/goatnotify-django/tests/test_django_tasks.py`:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from django.core import mail
from django.test import override_settings
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import MEMORY, Welcome

from goatnotify import ConfigurationError, Message, Notification
from goatnotify.django.models import NotificationRecord
from goatnotify.django.notifier import get_notifier
from goatnotify.django.serialization import (
    dump_model,
    dump_notification,
    load_notifiable,
    load_notification,
)


class NotADataclass(Notification[Member]):
    def messages(self, notifiable: Member) -> Iterable[Message]:
        return []


@dataclass
class HasDatetime(Notification[Member]):
    when: datetime

    def messages(self, notifiable: Member) -> Iterable[Message]:
        return []


class Plain:
    def route_notification(self, channel: str) -> str | None:
        return None


def test_models_and_notifications_round_trip() -> None:
    ada = Member.objects.create(email="ada@example.com")
    bob = Member.objects.create(email="bob@example.com")
    assert load_notifiable(dump_model(ada)) == ada
    restored = load_notification(dump_notification(Welcome(plan="pro", referrer=bob)))
    assert restored == Welcome(plan="pro", referrer=bob)


async def test_enqueue_runs_through_django_tasks() -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    bob = await Member.objects.acreate(email="bob@example.com")
    await get_notifier().enqueue(ada, Welcome(plan="pro", referrer=bob))
    (sent,) = mail.outbox
    assert (sent.to, sent.body) == (["ada@example.com"], "Welcome on the pro plan")
    record = await NotificationRecord.objects.aget()
    assert record.data == {"plan": "pro", "referrer": "bob@example.com"}


@pytest.mark.parametrize(
    ("notification", "match"),
    [
        (NotADataclass(), "dataclass"),
        (HasDatetime(when=datetime(2026, 1, 1, tzinfo=UTC)), "JSON"),
    ],
)
async def test_unserializable_notifications_fail_at_enqueue(
    notification: Notification[Member], match: str
) -> None:
    ada = await Member.objects.acreate(email="ada@example.com")
    with pytest.raises(ConfigurationError, match=match):
        await get_notifier().enqueue(ada, notification)
    assert mail.outbox == []


async def test_unsaved_and_non_model_recipients_fail_at_enqueue() -> None:
    with pytest.raises(ConfigurationError, match="saved"):
        await get_notifier().enqueue(Member(email="x@example.com"), Welcome(plan="pro"))
    with pytest.raises(ConfigurationError, match="model instance"):
        await get_notifier().enqueue(Plain(), Welcome(plan="pro"))  # pyright: ignore[reportArgumentType]


def test_a_custom_notifier_factory_is_used() -> None:
    with override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_notifier"):
        ada = Member.objects.create(email="ada@example.com")
        get_notifier().notify_sync(ada, Welcome(plan="team"))
        assert [m.subject for m in MEMORY.outbox][-1] == "Welcome"
    assert get_notifier() is not None


def test_a_factory_must_return_a_notifier() -> None:
    with (
        override_settings(GOATNOTIFY_NOTIFIER="goatnotify_testapp.notifications.build_nothing"),
        pytest.raises(ConfigurationError, match="Notifier"),
    ):
        get_notifier()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-django/tests/test_django_tasks.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'goatnotify.django.notifier'`

- [ ] **Step 4: Implement**

`serialization.py`:

```python
"""JSON forms of notifiables and notifications for Django Tasks, which only accepts JSON."""

import dataclasses
import importlib
import json
from collections.abc import Mapping
from typing import Any, Final, cast

from django.apps import apps
from django.db import models

from goatnotify.core._json import JsonValue
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable, Notification

MODEL_KEY: Final = "__model__"


def dump_model(instance: models.Model) -> dict[str, JsonValue]:
    if instance.pk is None:
        raise ConfigurationError(f"{type(instance).__qualname__} must be saved before it is queued")
    pk: object = instance.pk
    return {MODEL_KEY: instance._meta.label_lower, "pk": pk if isinstance(pk, str | int) else str(pk)}


def load_model(reference: Mapping[str, JsonValue]) -> models.Model:
    label = reference.get(MODEL_KEY)
    if not isinstance(label, str):
        raise ConfigurationError("Malformed queued model reference")
    return apps.get_model(label)._default_manager.get(pk=reference["pk"])


def load_notifiable(reference: Mapping[str, JsonValue]) -> Notifiable:
    instance = load_model(reference)
    if not callable(getattr(instance, "route_notification", None)):
        raise ConfigurationError(f"{type(instance).__qualname__} is not notifiable")
    return cast(Notifiable, instance)


def dump_notification(notification: Notification[Any]) -> dict[str, JsonValue]:
    cls = type(notification)
    if not dataclasses.is_dataclass(notification) or "<locals>" in cls.__qualname__:
        raise ConfigurationError(
            f"{cls.__qualname__} must be a module-level dataclass to be queued with Django Tasks"
        )
    fields: dict[str, JsonValue] = {}
    for field in dataclasses.fields(notification):
        if not field.init:
            continue
        value: object = getattr(notification, field.name)
        if isinstance(value, models.Model):
            fields[field.name] = dump_model(value)
            continue
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"{cls.__qualname__}.{field.name} is not JSON serializable"
            ) from error
        fields[field.name] = cast(JsonValue, value)
    return {"class": f"{cls.__module__}:{cls.__qualname__}", "fields": fields}


def load_notification(payload: Mapping[str, JsonValue]) -> Notification[Any]:
    path, fields = payload.get("class"), payload.get("fields")
    if not isinstance(path, str) or not isinstance(fields, dict):
        raise ConfigurationError("Malformed queued notification")
    module_name, _, qualname = path.partition(":")
    target: object = importlib.import_module(module_name)
    for part in qualname.split("."):
        target = getattr(target, part)
    if not (isinstance(target, type) and issubclass(target, Notification)):
        raise ConfigurationError(f"{path} is not a Notification")
    arguments = {
        name: load_model(value) if isinstance(value, dict) and MODEL_KEY in value else value
        for name, value in fields.items()
    }
    return cast(type[Notification[Any]], target)(**arguments)
```

`tasks.py`:

```python
"""Django task delivering queued notifications in the worker."""

from asgiref.sync import sync_to_async
from django.tasks import task

from goatnotify.core._json import JsonValue
from goatnotify.django.serialization import load_notifiable, load_notification


@task
async def deliver_notification(
    notifiable: dict[str, JsonValue], notification: dict[str, JsonValue]
) -> None:
    # Imported here because the default notifier builds a DjangoTasksQueue that enqueues this task.
    from goatnotify.django.notifier import get_notifier  # noqa: PLC0415

    recipient = await sync_to_async(load_notifiable)(notifiable)
    instance = await sync_to_async(load_notification)(notification)
    await get_notifier().notify(recipient, instance)
```

`queue.py`:

```python
"""Queue dispatching notifications through Django Tasks."""

from django.db import models

from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable
from goatnotify.core.queue import NotificationJob
from goatnotify.django.serialization import dump_model, dump_notification
from goatnotify.django.tasks import deliver_notification


class DjangoTasksQueue:
    def __init__(
        self,
        *,
        queue_name: str | None = None,
        priority: int | None = None,
        backend: str | None = None,
    ) -> None:
        self._queue_name = queue_name
        self._priority = priority
        self._backend = backend

    async def enqueue[R: Notifiable](self, job: NotificationJob[R]) -> None:
        if not isinstance(job.notifiable, models.Model):
            raise ConfigurationError("DjangoTasksQueue needs a Django model instance as notifiable")
        notifiable = dump_model(job.notifiable)
        notification = dump_notification(job.notification)
        task = deliver_notification.using(
            queue_name=self._queue_name, priority=self._priority, backend=self._backend
        )
        await task.aenqueue(notifiable, notification)
```

Check the installed `Task.using` signature first (`uv run python -c "import inspect, django.tasks.base as b; print(inspect.signature(b.Task.using))"`, expected `(self, *, priority=None, queue_name=None, run_after=None, backend=None)`). If passing `None` does not keep the task defaults, build the keyword arguments from the non-`None` values only.

`notifier.py`:

```python
"""Process-wide notifier for Django projects, built from settings."""

from functools import cache
from typing import Final

from django.conf import settings
from django.utils.module_loading import import_string

from goatnotify.core.channels.database import DatabaseChannel
from goatnotify.core.channels.email import EmailChannel
from goatnotify.core.channels.webhook import WebhookChannel
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.notifier import Notifier
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify.django.store import DjangoNotificationStore
from goatnotify.django.templates import DjangoTemplateRenderer

WATCHED_SETTINGS: Final = frozenset(
    {"GOATNOTIFY_NOTIFIER", "DEFAULT_FROM_EMAIL", "EMAIL_BACKEND", "TASKS", "TEMPLATES"}
)


def default_notifier() -> Notifier:
    mailer = Mailer(
        DjangoEmailTransport(),
        sender=settings.DEFAULT_FROM_EMAIL,
        renderer=DjangoTemplateRenderer(),
    )
    return Notifier(
        [EmailChannel(mailer), DatabaseChannel(DjangoNotificationStore()), WebhookChannel()],
        queue=DjangoTasksQueue(),
    )


@cache
def get_notifier() -> Notifier:
    path: object = getattr(settings, "GOATNOTIFY_NOTIFIER", None)
    if path is None:
        return default_notifier()
    if not isinstance(path, str):
        raise ConfigurationError("GOATNOTIFY_NOTIFIER must be a dotted path to a factory")
    notifier: object = import_string(path)()
    if not isinstance(notifier, Notifier):
        raise ConfigurationError(f"{path} must return a Notifier")
    return notifier


def reset_notifier_on_setting_change(sender: object, *, setting: str, **kwargs: object) -> None:
    if setting in WATCHED_SETTINGS:
        get_notifier.cache_clear()
```

Add to `GoatNotifyConfig` in `apps.py`:

```python
    def ready(self) -> None:
        from django.test.signals import setting_changed

        # Imported late: the notifier module loads models, which requires a ready app registry.
        from goatnotify.django.notifier import reset_notifier_on_setting_change  # noqa: PLC0415

        setting_changed.connect(reset_notifier_on_setting_change)
```

(Move `setting_changed` to the module top level; only the notifier import must stay inside `ready()`.)

Also add to the autouse fixture in `conftest.py`, before `yield`: `from goatnotify.django.notifier import get_notifier` and `get_notifier.cache_clear()`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-django -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: all pass, `0 errors`. If `test_enqueue_runs_through_django_tasks` hangs, the immediate backend is running the async task in a thread that cannot reach the test loop: check `django.tasks.backends.immediate.ImmediateBackend.supports_async_task` is `True` and that `aenqueue` is used (never `enqueue`) from async code.

- [ ] **Step 6: Commit**

```bash
git add packages/goatnotify-django
git commit -m "feat(django): add the Django Tasks queue and the settings-driven notifier"
```

---

### Task 15: FastAPI integration

**Files:**
- Modify: `packages/goatnotify-fastapi/src/goatnotify/fastapi/__init__.py`
- Test: `packages/goatnotify-fastapi/tests/test_fastapi.py`

**Interfaces:**
- Consumes: `Notifier`, `ClosableQueue`, `ConfigurationError`.
- Produces: `attach(app: FastAPI, notifier: Notifier) -> AbstractAsyncContextManager[None]`, `lifespan(notifier: Notifier) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]`, `get_notifier(request: Request) -> Notifier`, `NotifierDep = Annotated[Notifier, Depends(get_notifier)]`.

- [ ] **Step 1: Write the failing tests**

`packages/goatnotify-fastapi/tests/test_fastapi.py`:

```python
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

import pytest
from core_support import User
from fastapi import FastAPI
from fastapi.testclient import TestClient

from goatnotify import (
    AsyncioQueue,
    ConfigurationError,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
)
from goatnotify.core.testing import MemoryTransport
from goatnotify.fastapi import NotifierDep, attach, lifespan


class Hello(Mailable):
    subject = "Hello"

    def text(self) -> str | None:
        return "Hello!"


class Greeting(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Hello()


def _app(app: FastAPI) -> FastAPI:
    @app.post("/now")
    async def now(notifier: NotifierDep) -> dict[str, bool]:
        result = await notifier.notify(User(), Greeting())
        return {"ok": result.ok}

    @app.post("/later")
    async def later(notifier: NotifierDep) -> dict[str, bool]:
        await notifier.enqueue(User(), Greeting())
        return {"queued": True}

    return app


def _notifier() -> tuple[Notifier, MemoryTransport]:
    transport = MemoryTransport()
    mailer = Mailer(transport, sender="noreply@goat.dev")
    return Notifier([EmailChannel(mailer)], queue=AsyncioQueue()), transport


def test_the_notifier_is_injected() -> None:
    notifier, transport = _notifier()
    with TestClient(_app(FastAPI(lifespan=lifespan(notifier)))) as client:
        assert client.post("/now").json() == {"ok": True}
    assert len(transport.outbox) == 1


def test_queued_notifications_are_drained_on_shutdown() -> None:
    notifier, transport = _notifier()
    with TestClient(_app(FastAPI(lifespan=lifespan(notifier)))) as client:
        assert client.post("/later").json() == {"queued": True}
    assert len(transport.outbox) == 1


def test_attach_composes_with_an_existing_lifespan() -> None:
    notifier, transport = _notifier()

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with attach(app, notifier):
            yield

    with TestClient(_app(FastAPI(lifespan=app_lifespan))) as client:
        client.post("/now")
    assert len(transport.outbox) == 1


def test_a_missing_notifier_is_a_configuration_error() -> None:
    with TestClient(_app(FastAPI())) as client, pytest.raises(ConfigurationError, match="lifespan"):
        client.post("/now")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/goatnotify-fastapi -q`
Expected: FAIL with `ImportError: cannot import name 'NotifierDep'`

- [ ] **Step 3: Implement**

`packages/goatnotify-fastapi/src/goatnotify/fastapi/__init__.py`:

```python
"""FastAPI integration for GoatNotify."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated, Final

from fastapi import Depends, FastAPI, Request

from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notifier import Notifier
from goatnotify.core.queue import ClosableQueue

__all__ = ["NotifierDep", "attach", "get_notifier", "lifespan"]

STATE_KEY: Final = "goatnotify"


@asynccontextmanager
async def attach(app: FastAPI, notifier: Notifier) -> AsyncIterator[None]:
    setattr(app.state, STATE_KEY, notifier)
    try:
        yield
    finally:
        if isinstance(notifier.queue, ClosableQueue):
            await notifier.queue.aclose()


def lifespan(notifier: Notifier) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    def _lifespan(app: FastAPI) -> AbstractAsyncContextManager[None]:
        return attach(app, notifier)

    return _lifespan


def get_notifier(request: Request) -> Notifier:
    notifier: object = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(notifier, Notifier):
        raise ConfigurationError(
            "No notifier attached: use FastAPI(lifespan=goatnotify.fastapi.lifespan(notifier))"
        )
    return notifier


NotifierDep = Annotated[Notifier, Depends(get_notifier)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/goatnotify-fastapi -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright`
Expected: `4 passed`, `0 errors`. With `filterwarnings = ["error"]`, a third-party deprecation warning from Starlette or httpx fails the suite: add a narrowly scoped `filterwarnings` entry for that exact message in `pyproject.toml` rather than a blanket ignore.

- [ ] **Step 5: Commit**

```bash
git add packages/goatnotify-fastapi pyproject.toml
git commit -m "feat(fastapi): add the lifespan and notifier dependency"
```

---

### Task 16: Examples, isolation and typing contract

**Files:**
- Create: `examples/app.py`, `examples/discord_channel.py`, `examples/resend_transport.py`
- Create: `scripts/smoke_test.py`, `scripts/consumer.py`
- Create: `tests/typing/pyrightconfig.json`, `tests/typing/test_type_contract.py`, `tests/typing/fixtures/accepted.py`, `tests/typing/fixtures/rejected.py`
- Test: `tests/integration/test_isolation.py`, `tests/integration/test_examples.py`

**Interfaces:**
- Consumes: the whole public API.
- Produces: runnable examples (`python examples/<name>.py`), CI helper scripts used by Task 17.

- [ ] **Step 1: Write the failing tests**

`tests/integration/test_isolation.py`:

```python
import ast
import subprocess
import sys
from pathlib import Path
from typing import Final

FORBIDDEN: Final = frozenset(
    {"django", "fastapi", "starlette", "jinja2", "sqlalchemy", "celery", "httpx", "pydantic", "asgiref"}
)
CORE_SOURCE: Final = Path(__file__).parents[2] / "packages" / "goatnotify-core" / "src"


def test_importing_the_core_loads_no_framework() -> None:
    code = (
        "import sys, goatnotify, goatnotify.core, goatnotify.core.testing;"
        "print(','.join(sorted({name.split('.')[0] for name in sys.modules})))"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert FORBIDDEN.isdisjoint(completed.stdout.strip().split(","))


def _imported_modules(path: Path) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules


def test_the_core_source_never_imports_a_framework() -> None:
    offenders = [
        f"{path.relative_to(CORE_SOURCE)}: {module}"
        for path in CORE_SOURCE.rglob("*.py")
        for module in _imported_modules(path)
        if module.split(".")[0] in FORBIDDEN
    ]
    assert offenders == []
```

`tests/integration/test_examples.py`:

```python
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
```

`tests/typing/pyrightconfig.json`:

```json
{
  "include": ["fixtures"],
  "pythonVersion": "3.14",
  "typeCheckingMode": "strict",
  "venvPath": "../..",
  "venv": ".venv",
  "extraPaths": ["../../.typecheck"],
  "reportUnusedExpression": "none",
  "reportUnnecessaryTypeIgnoreComment": "error"
}
```

`tests/typing/test_type_contract.py`:

```python
"""Static typing is part of the API contract: invalid usages must be rejected by Pyright."""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final, TypedDict

import pytest

HERE: Final = Path(__file__).parent
FIXTURES: Final = HERE / "fixtures"
MARKER: Final = "# expect-error"


class _Position(TypedDict):
    line: int


class _Range(TypedDict):
    start: _Position


class _Diagnostic(TypedDict):
    file: str
    severity: str
    message: str
    range: _Range


class _Report(TypedDict):
    generalDiagnostics: list[_Diagnostic]


@pytest.fixture(scope="module")
def errors_by_file() -> dict[str, set[int]]:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pyright", "--outputjson", "-p", str(HERE / "pyrightconfig.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    report: _Report = json.loads(completed.stdout)
    errors: defaultdict[str, set[int]] = defaultdict(set)
    for diagnostic in report["generalDiagnostics"]:
        if diagnostic["severity"] == "error":
            errors[Path(diagnostic["file"]).name].add(diagnostic["range"]["start"]["line"] + 1)
    return dict(errors)


def _expected_lines(path: Path) -> set[int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {number for number, line in enumerate(lines, start=1) if line.endswith(MARKER)}


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("*.py")), ids=lambda path: path.name)
def test_pyright_reports_exactly_the_expected_errors(
    fixture: Path, errors_by_file: dict[str, set[int]]
) -> None:
    assert errors_by_file.get(fixture.name, set()) == _expected_lines(fixture)


def test_fixtures_cover_rejections_and_valid_usage() -> None:
    expectations = {path.name: _expected_lines(path) for path in FIXTURES.glob("*.py")}
    assert expectations["accepted.py"] == set()
    assert len(expectations["rejected.py"]) >= 10
```

`tests/typing/fixtures/accepted.py`:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from typing import assert_never, assert_type

from goatnotify import (
    Channel,
    DatabaseMessage,
    DeliveryFailed,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notifiable,
    Notification,
    NotificationResult,
    Notifier,
    RetryPolicy,
    WebhookMessage,
    events,
)
from goatnotify.core.testing import MemoryTransport


@dataclass
class User:
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None


class Welcome(Mailable):
    subject = "Welcome"

    def text(self) -> str | None:
        return "Hi"


class Joined(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        yield Welcome()
        yield DatabaseMessage(kind="joined", data={"email": notifiable.email, "tags": ["new"]})
        yield WebhookMessage(payload={"event": "joined"}, method="PUT")


class Broadcast(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        return []


@dataclass(frozen=True, slots=True)
class Sms(Message):
    body: str


class SmsChannel(Channel[Sms]):
    name = "sms"
    message_type = Sms

    async def send(self, notifiable: Notifiable, message: Sms) -> str | None:
        return message.body


def describe(event: events.Event) -> str:
    match event:
        case events.Sending() | events.Sent():
            return event.name
        case events.Retrying(delay=delay):
            return f"retry in {delay}"
        case events.Failed(error=error):
            return repr(error)
        case events.Skipped(reason=reason):
            return reason
        case _:
            assert_never(event)


async def log(event: events.Event) -> None:
    describe(event)


async def usage(user: User) -> None:
    notifier = Notifier(
        [EmailChannel(Mailer(MemoryTransport(), sender="noreply@goat.dev")), SmsChannel()],
        retry=RetryPolicy(max_attempts=5),
        hooks=[log],
    )
    assert_type(await notifier.notify(user, Joined()), NotificationResult)
    assert_type(notifier.notify_sync(user, Broadcast()), NotificationResult)
    try:
        await notifier.notify(user, Joined())
    except DeliveryFailed as failure:
        assert_type(failure.result, NotificationResult)
```

`tests/typing/fixtures/rejected.py`:

```python
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    Channel,
    DatabaseMessage,
    Mailable,
    Message,
    Notifiable,
    Notification,
    Notifier,
    RetryPolicy,
    WebhookMessage,
)


@dataclass
class User:
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email


@dataclass
class Admin(User):
    level: int = 1


class Anonymous:
    pass


class ForUsers(Notification[User]):
    def messages(self, notifiable: User) -> Iterable[Message]:
        return []


class AdminOnly(Notification[Admin]):
    def messages(self, notifiable: Admin) -> Iterable[Message]:
        return []


class WrongSend(Channel[Mailable]):
    name = "wrong"
    message_type = Mailable

    async def send(self, notifiable: Notifiable, message: WebhookMessage) -> str | None:  # expect-error
        return None


class WrongType(Channel[Mailable]):
    name = "wrong"
    message_type = WebhookMessage  # expect-error

    async def send(self, notifiable: Notifiable, message: Mailable) -> str | None:
        return None


class NotAMessage(Channel[str]):  # expect-error
    pass


async def misuse(notifier: Notifier, user: User) -> None:
    await notifier.notify(user, AdminOnly())  # expect-error
    await notifier.notify(Anonymous(), ForUsers())  # expect-error
    await notifier.notify(user, ForUsers(), raise_on_failure="yes")  # expect-error
    DatabaseMessage(kind="x", data={"when": object()})  # expect-error
    RetryPolicy(max_attempts="3")  # expect-error
    WebhookMessage(payload={}, method="GET")  # expect-error
    Notifier([object()])  # expect-error
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests -q`
Expected: FAIL: `test_examples_run` cannot find the example files; typing tests may already pass.

If a `# expect-error` line is not flagged by pyright, first check whether the library's annotations can be tightened so it is (that is the purpose of the contract). If the library is correct and pyright simply reports the error on a neighbouring line, move the marker to that line. Never delete an expectation without writing down why in the commit summary to the reviewer.

- [ ] **Step 3: Write the examples**

`examples/app.py`:

```python
"""A plain asyncio application sending email, database and webhook notifications."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from html import escape

from goatnotify import (
    DatabaseChannel,
    DatabaseMessage,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notification,
    Notifier,
    WebhookChannel,
    WebhookMessage,
    events,
)
from goatnotify.core.testing import MemoryHttpTransport, MemoryStore, MemoryTransport


@dataclass
class User:
    id: int
    name: str
    email: str
    slack_webhook: str | None = None

    def route_notification(self, channel: str) -> str | None:
        match channel:
            case "email":
                return self.email
            case "webhook":
                return self.slack_webhook
            case _:
                return None


class WelcomeMail(Mailable):
    subject = "Welcome to Goat"

    def __init__(self, user: User) -> None:
        self.user = user

    def html(self) -> str | None:
        return f"<h1>Welcome, {escape(self.user.name)}!</h1>"

    def text(self) -> str | None:
        return f"Welcome, {self.user.name}!"


class Welcome(Notification[User]):
    def __init__(self, plan: str) -> None:
        self.plan = plan

    def messages(self, notifiable: User) -> Iterable[Message]:
        yield WelcomeMail(notifiable)
        yield DatabaseMessage(kind="welcome", data={"plan": self.plan})
        if notifiable.slack_webhook:
            yield WebhookMessage(payload={"text": f"{notifiable.name} joined on {self.plan}"})


def log(event: events.Event) -> None:
    print(f"{event.name:<24} {event.channel:<9} attempt {event.attempt}")


async def main() -> None:
    outbox, store, http = MemoryTransport(), MemoryStore(), MemoryHttpTransport()
    notifier = Notifier(
        [
            EmailChannel(Mailer(outbox, sender="Goat <noreply@goat.dev>")),
            DatabaseChannel(store),
            WebhookChannel(http),
        ],
        hooks=[log],
    )
    user = User(1, "Ada", "ada@example.com", slack_webhook="https://hooks.slack.com/services/T/B/X")
    result = await notifier.notify(user, Welcome(plan="pro"))
    print(
        f"ok={result.ok} email={outbox.outbox[0].subject!r} "
        f"stored={store.records[0][1].kind!r} webhooks={len(http.requests)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
```

`examples/discord_channel.py`:

```python
"""A custom channel: Discord webhooks, built on the HttpTransport abstraction."""

import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    Channel,
    HttpRequest,
    HttpTransport,
    Message,
    Notifiable,
    Notification,
    Notifier,
    PermanentError,
    RetryableError,
    SkipDelivery,
    UrllibTransport,
)
from goatnotify.core.http import require_http_url
from goatnotify.core.testing import MemoryHttpTransport


@dataclass(frozen=True, slots=True)
class DiscordMessage(Message):
    content: str
    username: str | None = None


class DiscordChannel(Channel[DiscordMessage]):
    name = "discord"
    message_type = DiscordMessage

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self._transport = transport or UrllibTransport()

    async def send(self, notifiable: Notifiable, message: DiscordMessage) -> str | None:
        url = notifiable.route_notification(self.name)
        if url is None:
            raise SkipDelivery("no Discord webhook")
        require_http_url(url)
        payload = {"content": message.content}
        if message.username is not None:
            payload["username"] = message.username
        request = HttpRequest(
            "POST", url, {"Content-Type": "application/json"}, json.dumps(payload).encode(), 10.0
        )
        try:
            response = await self._transport.send(request)
        except OSError as error:
            raise RetryableError(f"Discord is unreachable: {type(error).__name__}") from error
        if response.status == 429 or response.status >= 500:
            raise RetryableError(f"Discord answered {response.status}")
        if response.status >= 400:
            raise PermanentError(f"Discord answered {response.status}")
        return None


@dataclass
class Team:
    discord_webhook: str

    def route_notification(self, channel: str) -> str | None:
        return self.discord_webhook if channel == "discord" else None


class Deployed(Notification[Team]):
    def messages(self, notifiable: Team) -> Iterable[Message]:
        yield DiscordMessage("Version 1.2.0 is live", username="GoatNotify")


async def main() -> None:
    http = MemoryHttpTransport()
    notifier = Notifier([DiscordChannel(http)])
    await notifier.notify(Team("https://discord.com/api/webhooks/1/token"), Deployed())
    print(f"discord requests={len(http.requests)}")


if __name__ == "__main__":
    asyncio.run(main())
```

`examples/resend_transport.py`:

```python
"""A custom email transport for the Resend HTTP API, built on HttpTransport."""

import asyncio
import base64
import json
from typing import Final, cast

from goatnotify import (
    EmailMessage,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    JsonValue,
    Mailable,
    Mailer,
    PermanentError,
    RetryableError,
    UrllibTransport,
)
from goatnotify.core.testing import MemoryHttpTransport

ENDPOINT: Final = "https://api.resend.com/emails"


class ResendTransport:
    def __init__(self, api_key: str, *, http: HttpTransport | None = None) -> None:
        self._api_key = api_key
        self._http = http or UrllibTransport()

    async def send(self, message: EmailMessage) -> str | None:
        request = HttpRequest(
            "POST",
            ENDPOINT,
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json.dumps(_payload(message)).encode(),
            30.0,
        )
        try:
            response = await self._http.send(request)
        except OSError as error:
            raise RetryableError(f"Resend is unreachable: {type(error).__name__}") from error
        return _message_id(response)


def _payload(message: EmailMessage) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "from": str(message.sender),
        "to": [str(address) for address in message.to],
        "subject": message.subject,
        "cc": [str(address) for address in message.cc],
        "bcc": [str(address) for address in message.bcc],
        "reply_to": [str(address) for address in message.reply_to],
        "headers": dict(message.headers),
        "attachments": [
            {"filename": a.filename, "content": base64.b64encode(a.content).decode()}
            for a in message.attachments
        ],
        "tags": [{"name": name, "value": value} for name, value in message.metadata.items()],
    }
    if message.html is not None:
        payload["html"] = message.html
    if message.text is not None:
        payload["text"] = message.text
    return payload


def _message_id(response: HttpResponse) -> str | None:
    if response.status == 429 or response.status >= 500:
        raise RetryableError(f"Resend answered {response.status}")
    if response.status >= 400:
        raise PermanentError(f"Resend answered {response.status}: {response.body[:200]!r}")
    data: object = json.loads(response.body)
    if isinstance(data, dict):
        identifier = cast(dict[str, object], data).get("id")
        return identifier if isinstance(identifier, str) else None
    return None


class Receipt(Mailable):
    subject = "Your receipt"

    def text(self) -> str | None:
        return "Thanks for your order."


async def main() -> None:
    http = MemoryHttpTransport()
    http.respond(HttpResponse(200, {}, b'{"id": "re_123"}'))
    mailer = Mailer(ResendTransport("re_test_key", http=http), sender="shop@goat.dev")
    print(f"resend id={await mailer.send(Receipt(), to=['ada@example.com'])}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Write the CI helper scripts**

`scripts/smoke_test.py`:

```python
"""Checks that the built wheels install and work outside the repository."""

import asyncio
from collections.abc import Iterable
from importlib.resources import files

from goatnotify import DatabaseChannel, DatabaseMessage, Message, Notifiable, Notification, Notifier
from goatnotify.core.testing import MemoryStore

PACKAGES = ("core", "jinja", "django", "fastapi")


class Recipient:
    def route_notification(self, channel: str) -> str | None:
        return None


class Ping(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield DatabaseMessage(kind="ping", data={"ok": True})


store = MemoryStore()
result = asyncio.run(Notifier([DatabaseChannel(store)]).notify(Recipient(), Ping()))

assert result.ok, result
assert store.records[0][1].kind == "ping"
assert files("goatnotify").joinpath("py.typed").is_file()
for package in PACKAGES:
    assert files(f"goatnotify.{package}").joinpath("py.typed").is_file(), package
```

`scripts/consumer.py`:

```python
"""Type-checked against the installed wheels in CI: every public name must be exported."""

from collections.abc import Iterable

from fastapi import FastAPI

from goatnotify import (
    AsyncioQueue,
    DatabaseChannel,
    EmailChannel,
    Mailable,
    Mailer,
    Message,
    Notifiable,
    Notification,
    Notifier,
    RetryPolicy,
    SmtpTransport,
    WebhookChannel,
)
from goatnotify.core.testing import MemoryStore
from goatnotify.django.mail import DjangoEmailTransport
from goatnotify.django.notifiable import NotifiableModel
from goatnotify.django.notifier import get_notifier
from goatnotify.django.queue import DjangoTasksQueue
from goatnotify.django.templates import DjangoTemplateRenderer
from goatnotify.fastapi import NotifierDep, lifespan
from goatnotify.jinja import JinjaRenderer


class Hello(Mailable):
    subject = "Hello"

    def template(self) -> str | None:
        return "hello.html"


class Greeting(Notification[Notifiable]):
    def messages(self, notifiable: Notifiable) -> Iterable[Message]:
        yield Hello()


notifier = Notifier(
    [
        EmailChannel(
            Mailer(
                SmtpTransport("smtp.example.com", username="u", password="p"),
                sender="noreply@example.com",
                renderer=JinjaRenderer.from_directory("templates"),
            )
        ),
        DatabaseChannel(MemoryStore()),
        WebhookChannel(secret="s"),
    ],
    retry=RetryPolicy(max_attempts=4),
    queue=AsyncioQueue(),
)
app = FastAPI(lifespan=lifespan(notifier))


@app.post("/hello")
async def hello(injected: NotifierDep) -> None:
    await injected.enqueue(NotifiableModel(), Greeting())


django_parts = (DjangoEmailTransport(), DjangoTemplateRenderer(), DjangoTasksQueue(), get_notifier)
```

- [ ] **Step 5: Run everything**

Run: `uv run pytest -q && uv run ruff check --fix . && uv run ruff format . && uv run pyright && uv run python examples/app.py`
Expected: all tests pass, `0 errors`, and the example prints three `notification.sent` lines followed by `ok=True email='Welcome to Goat' stored='welcome' webhooks=1`.

- [ ] **Step 6: Commit**

```bash
git add examples scripts tests
git commit -m "test: add examples, isolation checks and the typing contract"
```

---

### Task 17: CI, security, release and Dependabot

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/security.yml`, `.github/workflows/release-please.yml`, `.github/workflows/release.yml`, `.github/workflows/docs.yml`, `.github/dependabot.yml`
- Create: `release/config.json`, `release/.manifest.json`

Pinned actions (latest as used by GoatSEO on 2026-09-25; before committing, check each repository's latest release and update hash and comment together if a newer one exists):

| Action | Pin |
|---|---|
| `actions/checkout` | `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` |
| `astral-sh/setup-uv` | `c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0` |
| `actions/upload-artifact` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1` |
| `actions/download-artifact` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1` |
| `pypa/gh-action-pypi-publish` | `dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2` |
| `googleapis/release-please-action` | `45996ed1f6d02564a971a2fa1b5860e934307cf7 # v5.0.0` |
| `github/codeql-action/init` and `/analyze` | `1c5b675653bb5c22dbe9b12b556ec555138e09fd # v4.38.1` |
| `actions/dependency-review-action` | `a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0` |
| `actions/upload-pages-artifact` | `fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0` |
| `actions/configure-pages` | `45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0` |
| `actions/deploy-pages` | `368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1` |

- [ ] **Step 1: Write the workflows**

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  workflow_call:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  UV_LOCKED: "1"
  ACTIONLINT_VERSION: "1.7.12.25"

jobs:
  lint:
    name: Lint and type-check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --all-packages
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pyright
      - name: actionlint
        run: uvx --from "actionlint-py==${ACTIONLINT_VERSION}" actionlint

  test:
    name: Test (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --all-packages
      - run: uv run pytest

  build:
    name: Build and validate packages
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv build --all-packages
      - run: uv run twine check --strict dist/*
      - name: Install the wheels in a clean environment and smoke test them
        run: |
          uv venv "$RUNNER_TEMP/smoke"
          uv pip install --python "$RUNNER_TEMP/smoke" dist/*.whl
          cd "$RUNNER_TEMP"
          "$RUNNER_TEMP/smoke/bin/python" "$GITHUB_WORKSPACE/scripts/smoke_test.py"
      - name: Type-check a consumer project against the installed wheels
        run: |
          mkdir "$RUNNER_TEMP/consumer"
          cp scripts/consumer.py "$RUNNER_TEMP/consumer/"
          echo '{"typeCheckingMode": "strict"}' > "$RUNNER_TEMP/consumer/pyrightconfig.json"
          uv run --directory "$RUNNER_TEMP/consumer" --project "$GITHUB_WORKSPACE" \
            pyright --pythonpath "$RUNNER_TEMP/smoke/bin/python" consumer.py
```

`.github/workflows/security.yml`: copy GoatSEO's file verbatim (CodeQL matrix `[python, actions]` with `security-extended`, `pip-audit==2.10.1` over `uv export --locked --all-packages --all-groups --no-emit-workspace`, dependency review on pull requests with `fail-on-severity: moderate`), using the pins above. Its full content:

```yaml
name: Security

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: "17 5 * * 1"

permissions:
  contents: read

concurrency:
  group: security-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  codeql:
    name: CodeQL (${{ matrix.language }})
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [python, actions]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: github/codeql-action/init@1c5b675653bb5c22dbe9b12b556ec555138e09fd # v4.38.1
        with:
          languages: ${{ matrix.language }}
          queries: security-extended
      - uses: github/codeql-action/analyze@1c5b675653bb5c22dbe9b12b556ec555138e09fd # v4.38.1
        with:
          category: /language:${{ matrix.language }}

  dependencies:
    name: Audit dependencies
    runs-on: ubuntu-latest
    env:
      PIP_AUDIT_VERSION: "2.10.1"
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - name: Export the locked dependencies
        run: uv export --locked --all-packages --all-groups --no-emit-workspace --format requirements-txt > "$RUNNER_TEMP/requirements.txt"
      - name: pip-audit
        run: uvx "pip-audit==${PIP_AUDIT_VERSION}" --strict --disable-pip --requirement "$RUNNER_TEMP/requirements.txt"

  dependency-review:
    name: Dependency review
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0
        with:
          fail-on-severity: moderate
          comment-summary-in-pr: on-failure
```

`.github/workflows/release-please.yml`:

```yaml
name: Release Please

on:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  release-please:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    outputs:
      release_created: ${{ steps.release.outputs.release_created }}
      tag_name: ${{ steps.release.outputs.tag_name }}
    steps:
      - id: release
        uses: googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7 # v5.0.0
        with:
          config-file: release/config.json
          manifest-file: release/.manifest.json

  release:
    needs: release-please
    if: needs.release-please.outputs.release_created == 'true'
    permissions:
      contents: write
      id-token: write
    uses: ./.github/workflows/release.yml
    with:
      tag: ${{ needs.release-please.outputs.tag_name }}
```

`.github/workflows/release.yml`:

```yaml
name: Release

on:
  workflow_call:
    inputs:
      tag:
        description: Git tag of the release to build and publish.
        required: true
        type: string

permissions:
  contents: read

jobs:
  ci:
    uses: ./.github/workflows/ci.yml

  build:
    needs: ci
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ inputs.tag }}
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: uv build --all-packages --no-sources
      - run: uvx twine check --strict dist/*
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: dist
          path: dist/
          if-no-files-found: error

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/goatnotify/
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2

  assets:
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - name: Attach the distributions to the GitHub release
        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ inputs.tag }}
        run: gh release upload "$TAG" dist/* --repo "$GITHUB_REPOSITORY" --clobber
```

`.github/workflows/docs.yml`:

```yaml
name: Docs

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: docs-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv run --locked --only-group docs mkdocs build --strict --site-dir site
      - uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0
        with:
          path: site/

  deploy:
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'
    needs: build
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0
      - id: deployment
        uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1
```

`.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
    groups:
      python:
        patterns: ["*"]
    commit-message:
      prefix: build

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      actions:
        patterns: ["*"]
    commit-message:
      prefix: ci
```

`release/config.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "bump-minor-pre-major": true,
  "include-component-in-tag": false,
  "include-v-in-tag": true,
  "packages": {
    ".": {
      "package-name": "goatnotify",
      "changelog-path": "CHANGELOG.md",
      "extra-files": [
        "packages/goatnotify/pyproject.toml",
        "packages/goatnotify-core/pyproject.toml",
        "packages/goatnotify-jinja/pyproject.toml",
        "packages/goatnotify-django/pyproject.toml",
        "packages/goatnotify-fastapi/pyproject.toml"
      ]
    }
  }
}
```

`release/.manifest.json`:

```json
{
  ".": "0.0.0"
}
```

- [ ] **Step 2: Lint the workflows and verify the build locally**

Run: `uvx --from actionlint-py==1.7.12.25 actionlint && uv build --all-packages && uv run twine check --strict dist/* && rm -rf dist`
Expected: actionlint prints nothing; five wheels and five sdists pass `twine check`.

- [ ] **Step 3: Commit**

```bash
git add .github release
git commit -m "ci: add CI, security, release and Dependabot workflows"
```

---

### Task 18: Documentation, README and project CLAUDE.md

**Files:**
- Create: `mkdocs.yml`, `docs/index.md`, `docs/getting-started.md`, `docs/notifications.md`, `docs/mailables.md`, `docs/channels.md`, `docs/transports.md`, `docs/notifiable.md`, `docs/queues.md`, `docs/retries.md`, `docs/templates.md`, `docs/custom-channels.md`, `docs/custom-transports.md`, `docs/integrations/django.md`, `docs/integrations/fastapi.md`, `CLAUDE.md`
- Replace: `README.md`, every `packages/<dist>/README.md`

- [ ] **Step 1: README**

`README.md`:

````markdown
# GoatNotify

**A modern, type-safe, framework-agnostic notification system for Python.**

GoatNotify sends notifications by email, stores them in a database, posts them to webhooks, or
delivers them through any channel you write. A notification yields typed messages, and the type
of each message decides which channel delivers it, so Pyright checks the whole path.

- Async-first, with a synchronous `notify_sync()` for scripts and sync views
- Zero runtime dependencies in the core: SMTP and webhooks use the standard library
- Retries with exponential backoff, structured results and lightweight hooks
- Pluggable channels, transports, template renderers, stores and queues
- Optional Django (email backend, templates, ORM, Django Tasks), FastAPI and Jinja2 integrations

## Installation

```bash
pip install goatnotify              # the core
pip install "goatnotify[django]"    # or [fastapi], [jinja]
```

Python 3.14 or newer is required.

## Quickstart

```python
import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from goatnotify import (
    DatabaseMessage, EmailChannel, Mailable, Mailer, Message, Notification, Notifier,
    SmtpTransport,
)


@dataclass
class User:
    name: str
    email: str

    def route_notification(self, channel: str) -> str | None:
        return self.email if channel == "email" else None


class WelcomeMail(Mailable):
    subject = "Welcome to Goat"

    def __init__(self, user: User) -> None:
        self.user = user

    def text(self) -> str | None:
        return f"Welcome, {self.user.name}!"


class Welcome(Notification[User]):
    def messages(self, user: User) -> Iterable[Message]:
        yield WelcomeMail(user)


notifier = Notifier([
    EmailChannel(Mailer(SmtpTransport("smtp.example.com"), sender="noreply@example.com")),
])

asyncio.run(notifier.notify(User("Ada", "ada@example.com"), Welcome()))
```

Add a `DatabaseMessage` or a `WebhookMessage` to `messages()` and register `DatabaseChannel` or
`WebhookChannel`: nothing else changes.

## Documentation

<https://goatlabshq.github.io/goatnotify/>

## Packages

| Package | Contents |
|---|---|
| `goatnotify` | Facade re-exporting the core, with the `django`, `fastapi` and `jinja` extras |
| `goatnotify-core` | Notifications, channels, SMTP and HTTP transports, retries, queues, testing fakes |
| `goatnotify-jinja` | `JinjaRenderer` |
| `goatnotify-django` | Django email transport, template renderer, ORM store, Django Tasks queue |
| `goatnotify-fastapi` | Lifespan and `NotifierDep` dependency |

## Development

```bash
uv sync --all-packages
uv run pytest
uv run pyright
uv run ruff check . && uv run ruff format --check .
```

## Licence

MIT
````

Each `packages/<dist>/README.md`: title, the one-line description, `pip install <dist>` and a link to the documentation.

- [ ] **Step 2: mkdocs configuration**

`mkdocs.yml`: copy GoatSEO's theme, palette and `markdown_extensions` blocks verbatim, with:

```yaml
site_name: GoatNotify
site_description: A modern, type-safe, framework-agnostic notification system for Python.
repo_url: https://github.com/goatlabshq/goatnotify
site_url: https://goatlabshq.github.io/goatnotify/
repo_name: goatlabshq/goatnotify
edit_uri: edit/main/docs/
strict: true

nav:
  - Introduction: index.md
  - Getting started: getting-started.md
  - Guide:
      - Notifications: notifications.md
      - Notifiables: notifiable.md
      - Mailables: mailables.md
      - Templates: templates.md
      - Channels: channels.md
      - Transports: transports.md
      - Retries and failures: retries.md
      - Queues: queues.md
  - Extending:
      - Custom channels: custom-channels.md
      - Custom transports: custom-transports.md
  - Integrations:
      - Django: integrations/django.md
      - FastAPI: integrations/fastapi.md
```

`docs/superpowers/` must not appear in the site: add `exclude_docs: superpowers/` to `mkdocs.yml`.

- [ ] **Step 3: Write the pages**

Each page is written for a Python developer who has never seen GoatNotify. Every code block must be valid against the implemented API (copy names from `goatnotify.__all__`). Required content per page:

| Page | Must cover |
|---|---|
| `index.md` | The one-line pitch, the architecture diagram from spec §3, the five packages, a link to getting started |
| `getting-started.md` | Installation, a `Notifiable` dataclass, a `Mailable`, a `Notification`, building a `Notifier` with `EmailChannel` + `SmtpTransport`, `await notify`, `notify_sync`, reading `NotificationResult` |
| `notifications.md` | `messages()` yielding several message types, conditional yields, routing by message type and MRO, `ConfigurationError` for unroutable messages, concurrency and result order, `Notification[Notifiable]` for generic notifications |
| `notifiable.md` | The protocol, dataclass / Pydantic / Django / SQLAlchemy examples, `None` means skipped, `NotifiableModel` |
| `mailables.md` | Every attribute and method of the table in spec §7.1, precedence rules, `Attachment.from_path`, inline images with `cid:`, `Mailer.send` without notifications, header injection protection and reserved headers |
| `templates.md` | `TemplateRenderer` protocol, `JinjaRenderer.from_directory` (autoescape, `StrictUndefined`), `DjangoTemplateRenderer`, writing a custom renderer |
| `channels.md` | Email, database (`DatabaseMessage`, `NotificationStore`, `StoredNotification`) and webhook (`WebhookMessage`, signature verification snippet for receivers, retryable statuses, `Retry-After` cap, URL secrecy in errors) |
| `transports.md` | `EmailTransport`, `SmtpTransport` options and error mapping table, `HttpTransport` and `UrllibTransport`, `MemoryTransport` / `MemoryHttpTransport` for tests |
| `retries.md` | `RetryPolicy`, `ExponentialBackoff` formula and full jitter, per-channel overrides, `RetryableError` / `PermanentError` / `SkipDelivery`, `DeliveryFailed` with `except*`, `raise_on_failure=False`, hooks and event names, logging on the `goatnotify` logger |
| `queues.md` | `Notifier.enqueue`, `Queue` protocol, `AsyncioQueue` (`drain`, `aclose`, concurrency, background failure logging), `DjangoTasksQueue`, sketch of a Celery adapter implementing `Queue` |
| `custom-channels.md` | The complete `examples/discord_channel.py` explained step by step, testing it with `MemoryHttpTransport` |
| `custom-transports.md` | The complete `examples/resend_transport.py` explained, error classification guidance, using `to_mime` for raw-MIME providers |
| `integrations/django.md` | `INSTALLED_APPS`, migrations, `get_notifier()`, `GOATNOTIFY_NOTIFIER` factory, `NotifiableModel`, `NotificationRecord` queries (`for_recipient`, `unread`, `mark_as_read`), `DjangoTasksQueue` serialization rules (dataclass notifications, JSON fields, saved model instances), `notify_sync` from sync views |
| `integrations/fastapi.md` | `FastAPI(lifespan=lifespan(notifier))`, composing with an existing lifespan through `attach`, `NotifierDep`, background delivery with `AsyncioQueue` drained on shutdown |

- [ ] **Step 4: Project CLAUDE.md**

`CLAUDE.md`:

````markdown
# GoatNotify

uv workspace of independently published packages sharing the `goatnotify` import namespace.

## Layout

- `packages/goatnotify-core`: framework-agnostic engine, standard library only. It must never
  import `django`, `fastapi`, `starlette`, `jinja2`, `sqlalchemy`, `celery`, `httpx`, `pydantic`
  or `asgiref`; `tests/integration/test_isolation.py` enforces it.
- `packages/goatnotify-{jinja,django,fastapi}`: optional adapters.
- `packages/goatnotify`: facade distribution. It alone owns `goatnotify/__init__.py`; every other
  package is a namespace portion. `pkgutil.extend_path` in that file makes editable installs work.

## Rules

- `.typecheck/goatnotify` is a symlink tree merging the facade and every portion, because Pyright
  cannot merge a regular package with namespace portions spread over several editable roots.
  Add a symlink there when adding a package.
- Message routing is by type: a new built-in message type needs its own channel, and two
  channels can never share a `message_type`.
- `tests/typing/fixtures` is the static API contract: a `# expect-error` line must stay rejected.
- Internal dependency pins and versions carry `# x-release-please-version`; release-please
  (`release/`) bumps them all together.
- `packages/goatnotify-django/src/goatnotify/django/migrations/` is generated with
  `makemigrations`; never edit a released migration.

## Commands

```bash
uv sync --all-packages
uv run pytest
uv run pyright
uv run ruff check . && uv run ruff format --check .
uv run --only-group docs mkdocs build --strict
```
````

- [ ] **Step 5: Verify**

Run: `uv sync --all-packages --group docs && uv run --only-group docs mkdocs build --strict --site-dir site && grep -rnP "\x{2014}" README.md CLAUDE.md docs packages examples scripts tests || echo "no em dash"`
Expected: the site builds without warnings; `no em dash`.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md mkdocs.yml docs packages/*/README.md uv.lock
git commit -m "docs: add the README, the documentation site and the project guide"
```

---

### Task 19: Final verification

- [ ] **Step 1: Full local CI**

Run:

```bash
uv sync --all-packages --locked
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
uvx --from actionlint-py==1.7.12.25 actionlint
uv build --all-packages && uv run twine check --strict dist/* && rm -rf dist
```

Expected: every command succeeds; pytest reports no failures, no errors and no warnings.

- [ ] **Step 2: Check the commit history**

Run: `git log --format='%s%n%b' | grep -iE "claude|anthropic|co-authored" || echo clean`
Expected: `clean`.
