import ast
import re
import sys
import tomllib
from pathlib import Path
from typing import Final

import pytest

PACKAGES: Final = Path(__file__).parents[2] / "packages"


def _declared(package: Path) -> set[str]:
    dependencies = tomllib.loads((package / "pyproject.toml").read_text())["project"][
        "dependencies"
    ]
    names = {
        re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].lower() for requirement in dependencies
    }
    return {name.replace("-", "_") for name in names}


def _third_party_imports(package: Path) -> set[str]:
    found: set[str] = set()
    for path in (package / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                else []
            )
            found.update(module.split(".")[0] for module in modules)
    return found - set(sys.stdlib_module_names) - {"goatnotify"}


@pytest.mark.parametrize("package", sorted(PACKAGES.iterdir()), ids=lambda path: path.name)
def test_every_third_party_import_is_a_declared_dependency(package: Path) -> None:
    assert _third_party_imports(package) <= _declared(package)
