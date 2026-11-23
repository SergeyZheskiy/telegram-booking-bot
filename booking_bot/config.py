"""Business configuration (config.toml) and secrets (environment variables)."""

import os
import re
import tomllib
from dataclasses import dataclass, field
from datetime import time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HOURS = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")
_ID = re.compile(r"^[a-z0-9_-]{1,20}$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Service:
    id: str
    name: str
    duration: timedelta
    price: int


@dataclass(frozen=True, slots=True)
class Config:
    business_name: str
    tz: ZoneInfo
    language: str
    address: str
    phone: str
    # index 0 = Monday; None = day off
    hours: tuple[tuple[time, time] | None, ...]
    breaks: tuple[tuple[time, time], ...]
    slot_step: timedelta
    horizon_days: int
    min_lead: timedelta
    reminder_before: timedelta
    max_active_per_user: int
    currency: str
    services: tuple[Service, ...]
    admin_ids: frozenset[int] = field(default_factory=frozenset)

    def service(self, service_id: str) -> Service | None:
        return next((s for s in self.services if s.id == service_id), None)


def _parse_time(value: str, where: str) -> time:
    try:
        h, m = value.strip().split(":")
        return time(int(h), int(m))
    except ValueError as exc:
        raise ConfigError(f"{where}: expected HH:MM, got {value!r}") from exc


def _parse_hours(value: str, where: str) -> tuple[time, time]:
    m = _HOURS.match(value.strip())
    if not m:
        raise ConfigError(f"{where}: expected 'HH:MM-HH:MM', got {value!r}")
    start, end = time(int(m[1]), int(m[2])), time(int(m[3]), int(m[4]))
    if start >= end:
        raise ConfigError(f"{where}: opening time must be before closing time")
    return start, end


def parse_admin_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    try:
        return frozenset(int(x) for x in re.split(r"[,\s]+", raw.strip()) if x)
    except ValueError as exc:
        raise ConfigError("ADMIN_IDS must be a comma-separated list of numeric Telegram user ids") from exc


def load_config(data: dict, admin_ids: frozenset[int] = frozenset()) -> Config:
    """Validate a parsed TOML document. Every error message says exactly which key is wrong."""
    try:
        biz, sched, services = data["business"], data["schedule"], data["services"]
    except KeyError as exc:
        raise ConfigError(f"missing section [{exc.args[0]}]") from exc

    hours_cfg = sched.get("hours", {})
    unknown = set(hours_cfg) - set(WEEKDAYS)
    if unknown:
        raise ConfigError(f"schedule.hours: unknown weekday(s) {sorted(unknown)}; use {', '.join(WEEKDAYS)}")
    hours = tuple(_parse_hours(hours_cfg[d], f"schedule.hours.{d}") if d in hours_cfg else None for d in WEEKDAYS)
    if not any(hours):
        raise ConfigError("schedule.hours: the business must be open at least one day a week")

    breaks = []
    for i, b in enumerate(sched.get("breaks", [])):
        start, end = _parse_time(b["start"], f"schedule.breaks[{i}]"), _parse_time(b["end"], f"schedule.breaks[{i}]")
        if start >= end:
            raise ConfigError(f"schedule.breaks[{i}]: start must be before end")
        breaks.append((start, end))

    parsed_services = []
    for i, s in enumerate(services):
        if not _ID.match(str(s.get("id", ""))):
            raise ConfigError(f"services[{i}].id must match [a-z0-9_-]{{1,20}} (it goes into button payloads)")
        if int(s.get("duration", 0)) <= 0:
            raise ConfigError(f"services[{i}].duration must be a positive number of minutes")
        parsed_services.append(
            Service(s["id"], s["name"], timedelta(minutes=int(s["duration"])), int(s.get("price", 0)))
        )
    if not parsed_services:
        raise ConfigError("define at least one [[services]] entry")
    if len({s.id for s in parsed_services}) != len(parsed_services):
        raise ConfigError("services: ids must be unique")

    language = biz.get("language", "en")
    if language not in ("en", "ru"):
        raise ConfigError("business.language must be 'en' or 'ru'")
    try:
        tz = ZoneInfo(biz.get("timezone", "UTC"))
    except Exception as exc:
        raise ConfigError(f"business.timezone: unknown time zone {biz.get('timezone')!r}") from exc

    return Config(
        business_name=biz["name"],
        tz=tz,
        language=language,
        address=biz.get("address", ""),
        phone=biz.get("phone", ""),
        hours=hours,
        breaks=tuple(breaks),
        slot_step=timedelta(minutes=int(sched.get("slot_step_minutes", 30))),
        horizon_days=int(sched.get("booking_horizon_days", 14)),
        min_lead=timedelta(minutes=int(sched.get("min_lead_minutes", 60))),
        reminder_before=timedelta(minutes=int(sched.get("reminder_minutes_before", 120))),
        max_active_per_user=int(sched.get("max_active_bookings_per_user", 3)),
        currency=biz.get("currency", ""),
        services=tuple(parsed_services),
        admin_ids=admin_ids,
    )


def load_config_file(path: str | Path) -> Config:
    with open(path, "rb") as f:
        return load_config(tomllib.load(f), parse_admin_ids(os.getenv("ADMIN_IDS")))
