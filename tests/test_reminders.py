from datetime import timedelta
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage

from booking_bot.reminders import send_due_reminders
from booking_bot.texts import T

from .conftest import NOW, Clock


async def add(repo, user_id: int, starts_in: timedelta, created_before: timedelta = timedelta(days=1)):
    return await repo.create_booking(
        user_id=user_id,
        user_name="x",
        service_id="haircut",
        starts_at=NOW + starts_in,
        ends_at=NOW + starts_in + timedelta(minutes=45),
        now=NOW - created_before,
        max_active=5,
    )


async def test_sends_each_reminder_once(repo, cfg):
    await add(repo, 1, timedelta(minutes=90))
    await add(repo, 2, timedelta(hours=5))  # too far ahead
    bot = AsyncMock()
    assert await send_due_reminders(bot, repo, cfg, T("en"), Clock()) == 1
    (user_id, text), _ = bot.send_message.call_args
    assert user_id == 1 and "Reminder" in text and "10:30" in text
    assert await send_due_reminders(bot, repo, cfg, T("en"), Clock()) == 0


async def test_skips_short_notice_bookings_and_blocked_users(repo, cfg):
    await add(repo, 1, timedelta(minutes=45), created_before=timedelta(minutes=10))  # booked 55 min ahead
    await add(repo, 2, timedelta(minutes=100))
    bot = AsyncMock()
    bot.send_message.side_effect = TelegramForbiddenError(SendMessage(chat_id=2, text=""), "bot was blocked")
    assert await send_due_reminders(bot, repo, cfg, T("en"), Clock()) == 0
    assert bot.send_message.call_count == 1  # only user 2 was attempted
    assert await repo.due_reminders(NOW, NOW + timedelta(hours=3)) == []  # neither is retried
