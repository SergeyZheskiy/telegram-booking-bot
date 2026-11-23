import asyncio
import contextlib
import logging
import os
import sys
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import ConfigError, load_config_file
from .db import Repository
from .handlers import admin, client
from .reminders import reminder_loop
from .texts import T


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN is not set (get one from @BotFather and put it in .env)")
    try:
        cfg = load_config_file(os.getenv("CONFIG_PATH", "config.toml"))
    except (ConfigError, FileNotFoundError) as exc:
        sys.exit(f"Config error: {exc}")

    repo = await Repository.open(os.getenv("DATABASE_PATH", "bookings.db"))
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    t = T(cfg.language)
    clock = lambda: datetime.now(UTC)  # noqa: E731 — injected so tests can freeze time

    dp = Dispatcher(repo=repo, cfg=cfg, t=t, clock=clock)
    dp.include_routers(admin.router, client.router)  # admin first: its commands must win over the fallback

    await bot.set_my_commands([BotCommand(command="start", description=t("btn_book"))])
    reminders = asyncio.create_task(reminder_loop(bot, repo, cfg, t, clock))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminders
        await repo.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
