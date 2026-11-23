import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from ..config import Config
from ..texts import T

log = logging.getLogger(__name__)


async def notify_admins(bot: Bot, cfg: Config, text: str) -> None:
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError as exc:  # an admin who blocked the bot must not break the booking flow
            log.warning("could not notify admin %s: %s", admin_id, exc)


def when(dt: datetime, cfg: Config, t: T) -> dict[str, str]:
    """Format a UTC/aware datetime in the business time zone for the texts."""
    local = dt.astimezone(cfg.tz)
    return {"day": t.day(local.date()), "time": f"{local:%H:%M}"}
