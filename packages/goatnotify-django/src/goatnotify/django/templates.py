"""TemplateRenderer backed by the Django template engines."""

from collections.abc import Mapping

from asgiref.sync import sync_to_async

from django.template.loader import render_to_string


class DjangoTemplateRenderer:
    def __init__(self, *, using: str | None = None) -> None:
        self._using = using

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        return await sync_to_async(render_to_string)(template, dict(context), using=self._using)
