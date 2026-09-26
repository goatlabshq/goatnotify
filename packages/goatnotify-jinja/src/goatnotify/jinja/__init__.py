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
            # A Flask-oriented rule; HTML autoescaping is enabled right below.
            Environment(  # nosemgrep
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
