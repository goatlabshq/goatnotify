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
