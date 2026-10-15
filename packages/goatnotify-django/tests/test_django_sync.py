import asyncio

from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.core import mail
from django.db import connections
from goatnotify_testapp.models import Member
from goatnotify_testapp.notifications import Welcome

from goatnotify.django.models import NotificationRecord
from goatnotify.django.notifier import enqueue_sync, notify_sync


def signup_view(email: str) -> None:
    member = Member.objects.create(email=email)
    notify_sync(member, Welcome(plan="pro"))
    enqueue_sync(member, Welcome(plan="team"))


async def test_sync_views_under_asgi_do_not_deadlock() -> None:
    # Django's ASGI handler runs sync views like this, where asyncio.run() deadlocks.
    async with ThreadSensitiveContext():
        await asyncio.wait_for(sync_to_async(signup_view)("ada@example.com"), timeout=5)
        # Django closes the request thread's connections when the response finishes.
        await sync_to_async(connections.close_all)()
    assert [m.body for m in mail.outbox] == ["Welcome on the pro plan", "Welcome on the team plan"]
    assert await NotificationRecord.objects.acount() == 2


def test_sync_helpers_work_without_an_event_loop() -> None:
    signup_view("bob@example.com")
    assert len(mail.outbox) == 2
