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

## Tooling decisions

- Ruff ignores `TC001`-`TC003` because FastAPI and Django resolve annotations at runtime, so
  typing-only imports must stay real imports. Examples and scripts may ignore `ARG002`:
  protocol implementations there legitimately skip parameters.
- uv resolves with `exclude-newer = "7 days"`.
- zizmor's `self-repository` audit is disabled (`.github/zizmor.yml`): actionlint 1.7.12
  rejects the `$/` reusable-workflow syntax it asks for.

## Commands

```bash
uv sync --all-packages
uv run pytest
uv run pyright
uv run ruff check . && uv run ruff format --check .
uv run --only-group docs mkdocs build --strict
```

Mailpit integration tests are skipped unless `MAILPIT_API_URL` is set; CI runs them against a
Mailpit service container:

```bash
docker run -d --name goatnotify-mailpit -p 127.0.0.1:11025:1025 -p 127.0.0.1:18025:8025 axllent/mailpit
MAILPIT_API_URL=http://127.0.0.1:18025 MAILPIT_SMTP_PORT=11025 uv run pytest
```
