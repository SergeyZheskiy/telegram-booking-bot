from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from booking_bot.scheduling import available_days, day_slots, overlaps

TZ = ZoneInfo("Europe/Berlin")
MON = date(2026, 3, 9)


def at(h: int, m: int = 0, day: date = MON) -> datetime:
    return datetime.combine(day, time(h, m), tzinfo=TZ)


def slots(**overrides) -> list[str]:
    kwargs = dict(
        hours=(time(10), time(14)),
        breaks=[(time(12), time(13))],
        duration=timedelta(minutes=60),
        step=timedelta(minutes=30),
        busy=[],
        now=at(0),
        min_lead=timedelta(minutes=60),
        tz=TZ,
    )
    kwargs.update(overrides)
    return [f"{s:%H:%M}" for s in day_slots(kwargs.pop("day", MON), **kwargs)]


def test_slots_respect_hours_break_and_duration():
    # 10:00–14:00 with a 12:00–13:00 break: a 60-min service fits 10:00, 10:30, 11:00 and 13:00
    assert slots() == ["10:00", "10:30", "11:00", "13:00"]


def test_existing_bookings_block_overlapping_slots():
    assert slots(busy=[(at(10, 30), at(11, 0))]) == ["11:00", "13:00"]


def test_adjacent_bookings_do_not_clash():
    assert overlaps((at(10), at(11)), (at(10, 30), at(11, 30)))
    assert not overlaps((at(10), at(11)), (at(11), at(12)))


def test_minimum_lead_time():
    assert slots(now=at(9, 45)) == ["11:00", "13:00"]  # 10:45 is the earliest start


def test_day_off():
    assert slots(hours=None) == []


def test_daylight_saving_day_keeps_wall_clock_slots():
    dst = date(2026, 3, 29)  # clocks jump 02:00 -> 03:00 in Berlin
    result = day_slots(
        dst,
        hours=(time(10), time(12)),
        breaks=[],
        duration=timedelta(minutes=60),
        step=timedelta(minutes=60),
        busy=[],
        now=at(0),
        min_lead=timedelta(0),
        tz=TZ,
    )
    assert [f"{s:%H:%M %z}" for s in result] == ["10:00 +0200", "11:00 +0200"]


def test_available_days_skips_closed_and_full_days():
    hours = (None, (time(10), time(11)), (time(10), time(11)), None, None, None, None)  # Tue, Wed open
    days = available_days(
        MON,
        7,
        hours_by_weekday=hours,
        breaks=[],
        duration=timedelta(minutes=60),
        step=timedelta(minutes=30),
        busy=[(at(10, day=date(2026, 3, 10)), at(11, day=date(2026, 3, 10)))],  # Tuesday fully booked
        now=at(0),
        min_lead=timedelta(0),
        tz=TZ,
    )
    assert list(days) == [date(2026, 3, 11)]
