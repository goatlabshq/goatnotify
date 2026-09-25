"""Template rendering protocol; engines are provided by optional packages."""

from collections.abc import Mapping
from typing import Protocol


class TemplateRenderer(Protocol):
    async def render(self, template: str, context: Mapping[str, object]) -> str: ...
