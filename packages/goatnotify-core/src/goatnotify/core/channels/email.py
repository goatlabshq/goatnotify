from goatnotify.core.channel import Channel
from goatnotify.core.errors import SkipDelivery
from goatnotify.core.mail.mailable import Mailable
from goatnotify.core.mail.mailer import Mailer
from goatnotify.core.notification import Notifiable
from goatnotify.core.retry import RetryPolicy


class EmailChannel(Channel[Mailable]):
    name = "email"
    message_type = Mailable

    def __init__(self, mailer: Mailer, *, retry: RetryPolicy | None = None) -> None:
        self._mailer = mailer
        self.retry = retry

    async def send(self, notifiable: Notifiable, message: Mailable) -> str | None:
        if message.to:
            return await self._mailer.send(message)
        route = notifiable.route_notification(self.name)
        if route is None:
            raise SkipDelivery(f"{type(notifiable).__qualname__} has no email route")
        return await self._mailer.send(message, to=[route])
