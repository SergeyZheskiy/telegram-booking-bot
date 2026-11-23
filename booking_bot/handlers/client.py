from datetime import datetime

from aiogram import Bot, F, Router, html
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from ..config import Config, Service
from ..db import Repository, SlotTaken, TooManyBookings
from ..keyboards import (
    BackCb,
    CancelCb,
    ConfirmCb,
    DayCb,
    ServiceCb,
    TimeCb,
    confirm_kb,
    days_kb,
    main_menu,
    my_bookings_kb,
    price_label,
    services_kb,
    times_kb,
)
from ..services import Clock, display_name, free_slots
from ..texts import TEXTS, T
from .common import notify_admins, when

router = Router(name="client")


def button(key: str):
    """Match a reply-keyboard button in any language, so switching language never breaks old keyboards."""
    return F.text.in_({texts[key] for texts in TEXTS.values()})


def minutes(service: Service) -> int:
    return int(service.duration.total_seconds() // 60)


@router.message(CommandStart())
async def start(message: Message, cfg: Config, t: T) -> None:
    name = html.quote(message.from_user.first_name or "") if message.from_user else ""
    await message.answer(
        t("welcome", name=name, business=html.quote(cfg.business_name)),
        reply_markup=main_menu(t),
    )


@router.message(button("btn_book"))
async def book(message: Message, cfg: Config, t: T) -> None:
    await message.answer(t("choose_service"), reply_markup=services_kb(cfg, t))


@router.message(button("btn_contacts"))
async def contacts(message: Message, cfg: Config, t: T) -> None:
    await message.answer(
        t(
            "contacts",
            business=html.quote(cfg.business_name),
            address=html.quote(cfg.address),
            phone=html.quote(cfg.phone),
        )
    )


@router.callback_query(BackCb.filter(F.to == "services"))
async def back_to_services(callback: CallbackQuery, cfg: Config, t: T) -> None:
    await callback.message.edit_text(t("choose_service"), reply_markup=services_kb(cfg, t))
    await callback.answer()


async def show_days(
    callback: CallbackQuery, service: Service, repo: Repository, cfg: Config, t: T, now: datetime
) -> None:
    days = await free_slots(repo, cfg, service, now)
    if not days:
        await callback.message.edit_text(t("no_days", days=cfg.horizon_days))
        return
    await callback.message.edit_text(
        t("choose_day", service=html.quote(service.name)), reply_markup=days_kb(service.id, list(days), t)
    )


@router.callback_query(ServiceCb.filter())
async def pick_service(
    callback: CallbackQuery, callback_data: ServiceCb, repo: Repository, cfg: Config, t: T, clock: Clock
) -> None:
    service = cfg.service(callback_data.service)
    if service:
        await show_days(callback, service, repo, cfg, t, clock())
    await callback.answer()


@router.callback_query(BackCb.filter(F.to == "days"))
async def back_to_days(
    callback: CallbackQuery, callback_data: BackCb, repo: Repository, cfg: Config, t: T, clock: Clock
) -> None:
    service = cfg.service(callback_data.service)
    if service:
        await show_days(callback, service, repo, cfg, t, clock())
    await callback.answer()


@router.callback_query(DayCb.filter())
async def pick_day(
    callback: CallbackQuery, callback_data: DayCb, repo: Repository, cfg: Config, t: T, clock: Clock
) -> None:
    service = cfg.service(callback_data.service)
    if service is None:
        await callback.answer()
        return
    day = datetime.strptime(callback_data.day, "%Y%m%d").date()
    slots = (await free_slots(repo, cfg, service, clock())).get(day, [])
    if not slots:
        await callback.answer(t("no_times"), show_alert=True)
        await show_days(callback, service, repo, cfg, t, clock())
        return
    await callback.message.edit_text(
        t("choose_time", service=html.quote(service.name), day=t.day(day)), reply_markup=times_kb(service.id, slots, t)
    )
    await callback.answer()


@router.callback_query(TimeCb.filter())
async def pick_time(callback: CallbackQuery, callback_data: TimeCb, cfg: Config, t: T) -> None:
    service = cfg.service(callback_data.service)
    if service is None:
        await callback.answer()
        return
    start = datetime.fromtimestamp(callback_data.ts, cfg.tz)
    await callback.message.edit_text(
        t(
            "confirm",
            service=html.quote(service.name),
            minutes=minutes(service),
            price=price_label(service.price, cfg),
            **when(start, cfg, t),
        ),
        reply_markup=confirm_kb(service.id, callback_data.ts, start.date(), t),
    )
    await callback.answer()


@router.callback_query(ConfirmCb.filter())
async def confirm(
    callback: CallbackQuery,
    callback_data: ConfirmCb,
    repo: Repository,
    cfg: Config,
    t: T,
    clock: Clock,
    bot: Bot,
) -> None:
    service = cfg.service(callback_data.service)
    if service is None:
        await callback.answer()
        return
    now = clock()
    start = datetime.fromtimestamp(callback_data.ts, cfg.tz)

    # Callback data comes from the client and buttons can be hours old: re-check the slot against
    # the current schedule (working hours, lead time, existing bookings) before writing anything.
    if start not in (await free_slots(repo, cfg, service, now)).get(start.date(), []):
        await callback.answer(t("too_late"), show_alert=True)
        await show_days(callback, service, repo, cfg, t, now)
        return

    user = callback.from_user
    try:
        booking = await repo.create_booking(
            user_id=user.id,
            user_name=display_name(user.first_name, user.last_name, user.username),
            service_id=service.id,
            starts_at=start,
            ends_at=start + service.duration,
            now=now,
            max_active=cfg.max_active_per_user,
        )
    except SlotTaken:  # lost a race with another user between the check above and the insert
        await callback.answer(t("slot_taken"), show_alert=True)
        await show_days(callback, service, repo, cfg, t, now)
        return
    except TooManyBookings:
        await callback.answer(t("too_many", max=cfg.max_active_per_user), show_alert=True)
        return

    fmt = when(booking.starts_at, cfg, t)
    await callback.message.edit_text(t("booked", service=html.quote(service.name), **fmt))
    await callback.answer()
    await notify_admins(
        bot,
        cfg,
        t("admin_new", id=booking.id, service=html.quote(service.name), user=html.quote(booking.user_name), **fmt),
    )


@router.message(button("btn_my"))
async def my_bookings(message: Message, repo: Repository, cfg: Config, t: T, clock: Clock) -> None:
    items = await repo.upcoming_for_user(message.from_user.id, clock())
    if not items:
        await message.answer(t("my_empty"))
        return
    lines, buttons = [t("my_header")], []
    for b in items:
        service = cfg.service(b.service_id)
        fmt = when(b.starts_at, cfg, t)
        lines.append(t("my_line", service=html.quote(service.name if service else b.service_id), **fmt))
        buttons.append((b.id, fmt["day"], fmt["time"]))
    await message.answer("\n".join(lines), reply_markup=my_bookings_kb(buttons, t))


@router.callback_query(CancelCb.filter())
async def cancel(
    callback: CallbackQuery, callback_data: CancelCb, repo: Repository, cfg: Config, t: T, bot: Bot
) -> None:
    booking = await repo.cancel(callback_data.id, user_id=callback.from_user.id)  # only the owner can cancel
    if booking is None:
        await callback.answer(t("cancel_failed"), show_alert=True)
        return
    fmt = when(booking.starts_at, cfg, t)
    await callback.message.edit_text(t("cancelled", **fmt))
    await callback.answer()
    service = cfg.service(booking.service_id)
    await notify_admins(
        bot,
        cfg,
        t(
            "admin_cancelled",
            id=booking.id,
            service=html.quote(service.name if service else booking.service_id),
            user=html.quote(booking.user_name),
            **fmt,
        ),
    )


@router.message()
async def fallback(message: Message, t: T) -> None:
    await message.answer(t("unknown"), reply_markup=main_menu(t))
