import smtplib
import threading
from collections.abc import Sequence

from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise smtplib.SMTPServerDisconnected("gone")


class HandshakeBackend(BaseEmailBackend):
    released = threading.Event()
    saw_release = False

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        type(self).saw_release = type(self).released.wait(timeout=2)
        return len(email_messages)
