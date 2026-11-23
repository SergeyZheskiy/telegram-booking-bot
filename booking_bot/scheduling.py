"""Pure slot calculation — no Telegram, no database. This is where the business rules live."""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

Span = tuple[datetime, datetime]


def overlaps(a: Span, b: Span) -> bool:
    """Half-open intervals: a booking ending at 11:00 does not clash with one starting at 11:00."""
    return a[0] < b[1] and b[0] < a[1]


def day_slots(
    day: date,
    *,
    hours: tuple[time, time] | None,
    breaks: Iterable[tuple[time, time]],
    duration: timedelta,
    step: timedelta,
    busy: Iterable[Span],
    now: datetime,
    min_lead: timedelta,
    tz: ZoneInfo,
) -> list[datetime]:
    """Start times (aware, in the business time zone) at which `duration` fits on `day`."""
    if hours is None:
        return []
    opening = datetime.combine(day, hours[0], tzinfo=tz)
    closing = datetime.combine(day, hours[1], tzinfo=tz)
    blocked = [*busy, *((datetime.combine(day, s, tzinfo=tz), datetime.combine(day, e, tzinfo=tz)) for s, e in breaks)]
    earliest = now + min_lead

    slots = []
    start = opening
    while start + duration <= closing:
        candidate = (start, start + duration)
        if start >= earliest and not any(overlaps(candidate, b) for b in blocked):
            slots.append(start)
        start += step
    return slots


def available_days(
    today: date,
    horizon_days: int,
    *,
    hours_by_weekday: tuple[tuple[time, time] | None, ...],
    **slot_kwargs,
) -> dict[date, list[datetime]]:
    """Days within the horizon that still have at least one free slot, mapped to those slots."""
    result: dict[date, list[datetime]] = {}
    for offset in range(horizon_days):
        day = today + timedelta(days=offset)
        slots = day_slots(day, hours=hours_by_weekday[day.weekday()], **slot_kwargs)
        if slots:
            result[day] = slots
    return result
