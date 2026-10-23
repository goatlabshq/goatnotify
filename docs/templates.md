# Templates

The core renders no template itself. It defines a protocol, and optional packages provide
engines:

```python
class TemplateRenderer(Protocol):
    async def render(self, template: str, context: Mapping[str, object]) -> str: ...
```

Pass a renderer to the `Mailer`; mailables then name templates in `subject_template()`,
`template()` and `text_template()`.

## Jinja2

```bash
pip install "goatnotify[jinja]"
```

```python
from goatnotify.jinja import JinjaRenderer

renderer = JinjaRenderer.from_directory("templates")
mailer = Mailer(transport, sender="noreply@example.com", renderer=renderer)
```

`from_directory()` builds an environment with:

- HTML autoescaping for `.html`, `.htm` and `.xml` templates (plain-text templates are not
  escaped);
- `StrictUndefined`, so a missing variable is an error instead of an empty string;
- async rendering.

To use your own environment, pass it directly: `JinjaRenderer(environment)`. Synchronous
environments render in a worker thread.

## Django templates

```python
from goatnotify.django.templates import DjangoTemplateRenderer

renderer = DjangoTemplateRenderer()  # or DjangoTemplateRenderer(using="jinja2")
```

It calls `render_to_string()` through `sync_to_async`, so it uses your `TEMPLATES` setting.

Django escapes HTML in every template, plain-text ones included. Wrap subject and text templates
in `{% autoescape off %}`, as Django's own password reset emails do:

```django
{% autoescape off %}Invoice {{ number }} for {{ customer.name }}{% endautoescape %}
```

## A custom renderer

Any object with a matching `render` coroutine works:

```python
from string import Template


class StringTemplateRenderer:
    def __init__(self, templates: Mapping[str, str]) -> None:
        self._templates = templates

    async def render(self, template: str, context: Mapping[str, object]) -> str:
        return Template(self._templates[template]).substitute(context)
```
