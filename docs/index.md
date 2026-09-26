# GoatNotify

**A modern, type-safe, framework-agnostic notification system for Python.**

GoatNotify takes the good ideas of Laravel Notifications and Mailables and rebuilds them for
Python: async-first, checked end to end by Pyright in strict mode, and free of any framework
in its core.

A notification describes *what* to say as typed messages. Channels decide *where* each message
goes. Transports do the low-level I/O.

```text
Notification ──yields──▶ Message ──routed by type──▶ Channel ──▶ Transport / Store
                                                         ▲
Notifier: owns channels, retry policy, hooks, queue ─────┘
```

Because the type of a message selects its channel, there is no string lookup between a channel
name and a `to_<channel>()` method: a `Mailable` goes to the `EmailChannel`, a
`DatabaseMessage` to the `DatabaseChannel`, and your own `DiscordMessage` to your own
`DiscordChannel`.

## Packages

| Package | Contents |
|---|---|
| `goatnotify` | Facade re-exporting the core, with the `django`, `fastapi` and `jinja` extras |
| `goatnotify-core` | Notifications, channels, SMTP and HTTP transports, retries, queues, testing fakes. Standard library only. |
| `goatnotify-jinja` | `JinjaRenderer` |
| `goatnotify-django` | Django email transport, template renderer, ORM store, Django Tasks queue |
| `goatnotify-fastapi` | Lifespan and `NotifierDep` dependency |

```bash
pip install goatnotify              # the core
pip install "goatnotify[django]"    # or [fastapi], [jinja]
```

Next: [Getting started](getting-started.md).
