import tomllib
from pathlib import Path
from typing import Final

PACKAGES: Final = sorted((Path(__file__).parents[2] / "packages").iterdir())


def _build_system(package: Path) -> dict[str, object]:
    return tomllib.loads((package / "pyproject.toml").read_text())["build-system"]


def test_every_package_builds_with_the_same_backend_range() -> None:
    systems = {package.name: _build_system(package) for package in PACKAGES}
    assert {str(system["requires"]) for system in systems.values()} == {"['uv_build>=0.12,<0.14']"}
    assert {system["build-backend"] for system in systems.values()} == {"uv_build"}


def test_licenses_use_pep_639_metadata_only() -> None:
    for package in PACKAGES:
        project = tomllib.loads((package / "pyproject.toml").read_text())["project"]
        assert project["license"] == "MIT"
        assert not [c for c in project["classifiers"] if c.startswith("License ::")], package.name
