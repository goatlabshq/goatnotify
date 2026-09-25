# .typecheck

Symlinks exposing one merged `goatnotify` package, used only by Pyright through
`extraPaths = [".typecheck"]` in the root `pyproject.toml`.

In the workspace, `goatnotify/__init__.py` (facade) and its subpackages (`goatnotify.core`,
`goatnotify.django`, ...) live in separate editable roots. Python merges them at runtime through
`pkgutil.extend_path`, but Pyright stops at the first regular `goatnotify` package it finds and
cannot resolve the others. Installed wheels share one `site-packages/goatnotify/` directory, so end
users never need this.

When adding a package, add its symlink:

```bash
ln -s ../../packages/goatnotify-<name>/src/goatnotify/<name> .typecheck/goatnotify/<name>
```
