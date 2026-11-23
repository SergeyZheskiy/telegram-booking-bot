from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config
from .texts import T

# Every button carries the full context it needs (service, day, time). No FSM state is kept,
# so the flow survives bot restarts and a user can have several booking messages open at once.


class ServiceCb(CallbackData, prefix="svc"):
    service: str


class DayCb(CallbackData, prefix="day"):
    service: str
    day: str  # YYYYMMDD


class TimeCb(CallbackData, prefix="time"):
    service: str
    ts: int  # unix timestamp of the slot start


class ConfirmCb(CallbackData, prefix="ok"):
    service: str
    ts: int


class CancelCb(CallbackData, prefix="cancel"):
    id: int


class BackCb(CallbackData, prefix="back"):
    to: str  # "services" | "days"
    service: str = ""


def price_label(price: int, cfg: Config) -> str:
    return f"{price:,}".replace(",", " ") + (f" {cfg.currency}" if cfg.currency else "")


def main_menu(t: T) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_book"))],
            [KeyboardButton(text=t("btn_my")), KeyboardButton(text=t("btn_contacts"))],
        ],
        resize_keyboard=True,
    )


def services_kb(cfg: Config, t: T) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in cfg.services:
        label = t(
            "service_line", name=s.name, minutes=int(s.duration.total_seconds() // 60), price=price_label(s.price, cfg)
        )
        kb.button(text=label, callback_data=ServiceCb(service=s.id))
    kb.adjust(1)
    return kb.as_markup()


def days_kb(service_id: str, days: list[date], t: T) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in days:
        kb.button(text=t.day(d), callback_data=DayCb(service=service_id, day=f"{d:%Y%m%d}"))
    kb.button(text=t("btn_back"), callback_data=BackCb(to="services"))
    kb.adjust(*([3] * ((len(days) + 2) // 3)), 1)
    return kb.as_markup()


def times_kb(service_id: str, slots: list[datetime], t: T) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in slots:
        kb.button(text=f"{s:%H:%M}", callback_data=TimeCb(service=service_id, ts=int(s.timestamp())))
    kb.button(text=t("btn_back"), callback_data=BackCb(to="days", service=service_id))
    kb.adjust(*([4] * ((len(slots) + 3) // 4)), 1)
    return kb.as_markup()


def confirm_kb(service_id: str, ts: int, day: date, t: T) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_confirm"), callback_data=ConfirmCb(service=service_id, ts=ts))
    kb.button(text=t("btn_back"), callback_data=DayCb(service=service_id, day=f"{day:%Y%m%d}"))
    kb.adjust(1)
    return kb.as_markup()


def my_bookings_kb(items: list[tuple[int, str, str]], t: T) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for booking_id, day, time in items:
        kb.button(text=t("btn_cancel", day=day, time=time), callback_data=CancelCb(id=booking_id))
    kb.adjust(1)
    return kb.as_markup()
