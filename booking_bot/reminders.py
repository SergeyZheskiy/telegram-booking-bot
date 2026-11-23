import asyncio
import logging

from aiogram import Bot, html
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from .config import Config
from .db import Repository
from .handlers.common import when
from .services import Clock
from .texts import T

log = logging.getLogger(__name__)


async def send_due_reminders(bot: Bot, repo: Repository, cfg: Config, t: T, clock: Clock) -> int:
    """Send reminders for bookings starting within `cfg.reminder_before`. Returns how many were sent."""
    now = clock()
    sent = 0
    for b in await repo.due_reminders(now, now + cfg.reminder_before):
        # Booked 30 minutes ahead? A "reminder" right after confirming would just be noise.
        if b.starts_at - b.created_at >= cfg.reminder_before:
            service = cfg.service(b.service_id)
            text = t(
                "reminder",
                service=html.quote(service.name if service else b.service_id),
                address=html.quote(cfg.address),
                time=when(b.starts_at, cfg, t)["time"],
            )
            try:
                await bot.send_message(b.user_id, text)
                sent += 1
            except TelegramForbiddenError:
                pass  # user blocked the bot: nothing to retry
            except TelegramAPIError as exc:
                log.warning("reminder for booking %s failed, will retry: %s", b.id, exc)
                continue
        await repo.mark_reminded(b.id)
    return sent


async def reminder_loop(bot: Bot, repo: Repository, cfg: Config, t: T, clock: Clock, interval: float = 60) -> None:
    while True:
        try:
            await send_due_reminders(bot, repo, cfg, t, clock)
        except Exception:
            log.exception("reminder loop iteration failed")
        await asyncio.sleep(interval)
