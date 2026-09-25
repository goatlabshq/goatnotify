import smtplib
from collections.abc import Sequence

from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise smtplib.SMTPServerDisconnected("gone")
