"""Glue between the pure scheduler and the repository. Handlers and tests both use this."""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from .config import Config, Service
from .db import Repository
from .scheduling import available_days

Clock = Callable[[], datetime]


async def free_slots(repo: Repository, cfg: Config, service: Service, now: datetime) -> dict[date, list[datetime]]:
    today = now.astimezone(cfg.tz).date()
    window_start = datetime.combine(today, datetime.min.time(), tzinfo=cfg.tz)
    busy = await repo.busy_between(window_start, window_start + timedelta(days=cfg.horizon_days + 1))
    return available_days(
        today,
        cfg.horizon_days,
        hours_by_weekday=cfg.hours,
        breaks=cfg.breaks,
        duration=service.duration,
        step=cfg.slot_step,
        busy=busy,
        now=now,
        min_lead=cfg.min_lead,
        tz=cfg.tz,
    )


def display_name(first_name: str | None, last_name: str | None, username: str | None) -> str:
    name = " ".join(p for p in (first_name, last_name) if p) or "—"
    return f"{name} (@{username})" if username else name
