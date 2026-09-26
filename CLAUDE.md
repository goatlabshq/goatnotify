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
