# Mailables

A `Mailable` describes an email as a class. It is also a `Message`, so a notification can yield it
directly, and a `Mailer` can send it without any notification.

```python
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from goatnotify import Attachment, Mailable


class InvoiceMail(Mailable):
    subject = "Your invoice"
    reply_to = ("billing@example.com",)
    headers = MappingProxyType({"X-Campaign": "invoices"})
    metadata = MappingProxyType({"category": "billing"})

    def __init__(self, invoice: Invoice) -> None:
        self.invoice = invoice
        self.subject = f"Invoice {invoice.number}"

    def template(self) -> str | None:
        return "emails/invoice.html"

    def text_template(self) -> str | None:
        return "emails/invoice.txt"

    def context(self) -> Mapping[str, object]:
        return {"invoice": self.invoice}

    def attachments(self) -> Sequence[Attachment]:
        return [Attachment.from_path(self.invoice.pdf_path)]
```

## Reference

| Member | Type | Default |
|---|---|---|
| `subject` | `str` | required: an empty subject raises `InvalidMessageError` |
| `sender` | `str \| Address \| None` | the mailer's sender |
| `to`, `cc`, `bcc`, `reply_to` | `Sequence[str \| Address]` | `()`; an empty `to` uses the recipient's `"email"` route |
| `headers` | `Mapping[str, str]` | empty |
| `metadata` | `Mapping[str, str]` | empty; tags for providers, never sent as headers |
| `attachments()` | `Sequence[Attachment]` | `()` |
| `html()`, `text()` | `str \| None` | `None` |
| `template()`, `text_template()` | `str \| None` | `None` |
| `context()` | `Mapping[str, object]` | empty |

Addresses accept `"ada@example.com"`, `"Ada Lovelace <ada@example.com>"` or an `Address`.

## Body precedence

- `html()` wins over `template()`, and `text()` wins over `text_template()`.
- Templates are rendered with `context()` by the mailer's [template renderer](templates.md).
- At least one body is required; a template without a configured renderer raises
  `ConfigurationError`.

## Attachments and inline images

```python
Attachment("report.csv", data, "text/csv")
Attachment.from_path("logo.png", inline=True)
```

`from_path` guesses the MIME type from the file name. An inline attachment is referenced from the
HTML body with its file name as content id:

```html
<img src="cid:logo.png" alt="Goat">
```

## Sending without a notification

```python
mailer = Mailer(SmtpTransport("smtp.example.com"), sender="noreply@example.com")
await mailer.send(InvoiceMail(invoice), to=["ada@example.com"])
message = await mailer.render(InvoiceMail(invoice), to=["ada@example.com"])  # preview
```

A non-empty `to=` replaces the mailable's own `to`.

## Header injection protection

Subjects, display names, addresses, header names and header values containing a line break are
rejected with `InvalidMessageError` before any MIME is built. Custom headers cannot override
`Subject`, `From`, `To`, `Cc`, `Bcc`, `Reply-To`, `Date`, `Content-Type` or `MIME-Version`: set
those through the mailable's fields.
