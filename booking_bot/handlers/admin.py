import contextlib
import csv
import io
from datetime import datetime, timedelta

from aiogram import Bot, Router, html
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import BufferedInputFile, Message

from ..config import Config
from ..db import Repository
from ..services import Clock
from ..texts import T
from .common import when

router = Router(name="admin")


class IsAdmin(Filter):
    async def __call__(self, message: Message, cfg: Config) -> bool:
        return message.from_user is not None and message.from_user.id in cfg.admin_ids


router.message.filter(IsAdmin())


async def agenda(repo: Repository, cfg: Config, t: T, start: datetime, days: int, period: str) -> str:
    bookings = await repo.between(start, start + timedelta(days=days))
    if not bookings:
        return t("agenda_empty", period=period)
    lines = [t("agenda_header", period=period)]
    current_day = None
    for b in bookings:
        fmt = when(b.starts_at, cfg, t)
        if days > 1 and fmt["day"] != current_day:
            current_day = fmt["day"]
            lines.append(f"\n<b>{current_day}</b>")
        service = cfg.service(b.service_id)
        lines.append(
            t(
                "agenda_line",
                id=b.id,
                time=fmt["time"],
                service=html.quote(service.name if service else b.service_id),
                user=html.link(b.user_name, f"tg://user?id={b.user_id}"),
            )
        )
    return "\n".join(lines)


def local_midnight(now: datetime, cfg: Config, plus_days: int = 0) -> datetime:
    day = now.astimezone(cfg.tz).date() + timedelta(days=plus_days)
    return datetime.combine(day, datetime.min.time(), tzinfo=cfg.tz)


@router.message(Command("admin"))
async def admin_help(message: Message, t: T) -> None:
    await message.answer(t("admin_help"))


@router.message(Command("today"))
async def today(message: Message, repo: Repository, cfg: Config, t: T, clock: Clock) -> None:
    await message.answer(await agenda(repo, cfg, t, local_midnight(clock(), cfg), 1, t("period_today")))


@router.message(Command("tomorrow"))
async def tomorrow(message: Message, repo: Repository, cfg: Config, t: T, clock: Clock) -> None:
    await message.answer(await agenda(repo, cfg, t, local_midnight(clock(), cfg, 1), 1, t("period_tomorrow")))


@router.message(Command("week"))
async def week(message: Message, repo: Repository, cfg: Config, t: T, clock: Clock) -> None:
    await message.answer(await agenda(repo, cfg, t, local_midnight(clock(), cfg), 7, t("period_week")))


def bookings_csv(rows, cfg: Config) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "status", "service", "starts_at_local", "ends_at_local", "client", "telegram_user_id", "created_at_utc"]
    )
    for b in rows:
        service = cfg.service(b.service_id)
        w.writerow(
            [
                b.id,
                b.status,
                service.name if service else b.service_id,
                b.starts_at.astimezone(cfg.tz).strftime("%Y-%m-%d %H:%M"),
                b.ends_at.astimezone(cfg.tz).strftime("%Y-%m-%d %H:%M"),
                b.user_name,
                b.user_id,
                b.created_at.isoformat(),
            ]
        )
    return buf.getvalue().encode("utf-8-sig")  # BOM: opens correctly in Excel


@router.message(Command("export"))
async def export(message: Message, repo: Repository, cfg: Config, clock: Clock) -> None:
    data = bookings_csv(await repo.all(), cfg)
    await message.answer_document(BufferedInputFile(data, filename=f"bookings-{clock():%Y%m%d}.csv"))


@router.message(Command("cancel"))
async def admin_cancel(message: Message, command: CommandObject, repo: Repository, cfg: Config, t: T, bot: Bot) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer(t("admin_cancel_usage"))
        return
    booking = await repo.cancel(int(command.args))
    if booking is None:
        await message.answer(t("cancel_failed"))
        return
    # the client may have blocked the bot; the cancellation still stands
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(booking.user_id, t("client_cancelled_by_admin", **when(booking.starts_at, cfg, t)))
    await message.answer(t("admin_cancelled_by_you", id=booking.id))
