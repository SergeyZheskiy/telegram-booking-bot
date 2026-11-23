import asyncio
from datetime import timedelta

import pytest

from booking_bot.db import Repository, SlotTaken, TooManyBookings

from .conftest import NOW

H = timedelta(hours=1)


def booking(user_id=1, start=NOW + 5 * H, length=H, max_active=3):
    return dict(
        user_id=user_id,
        user_name=f"user{user_id}",
        service_id="haircut",
        starts_at=start,
        ends_at=start + length,
        now=NOW,
        max_active=max_active,
    )


async def test_create_and_read_back(repo):
    b = await repo.create_booking(**booking())
    assert b.id == 1 and b.status == "active" and b.starts_at == NOW + 5 * H
    assert await repo.busy_between(NOW, NOW + 24 * H) == [(b.starts_at, b.ends_at)]


async def test_overlap_is_rejected_but_adjacent_is_fine(repo):
    await repo.create_booking(**booking())
    with pytest.raises(SlotTaken):
        await repo.create_booking(**booking(user_id=2, start=NOW + 5.5 * H))
    await repo.create_booking(**booking(user_id=2, start=NOW + 6 * H))  # starts when the first ends


async def test_concurrent_confirmations_from_two_connections(tmp_path):
    """Two bot processes confirm the same slot at once: exactly one wins."""
    path = str(tmp_path / "race.db")
    a, b = await Repository.open(path), await Repository.open(path)
    try:
        results = await asyncio.gather(
            a.create_booking(**booking(user_id=1)), b.create_booking(**booking(user_id=2)), return_exceptions=True
        )
        assert sum(isinstance(r, SlotTaken) for r in results) == 1
        assert len(await a.all()) == 1
    finally:
        await a.close()
        await b.close()


async def test_per_user_limit(repo):
    for i in range(2):
        await repo.create_booking(**booking(start=NOW + (i + 1) * 2 * H, max_active=2))
    with pytest.raises(TooManyBookings):
        await repo.create_booking(**booking(start=NOW + 10 * H, max_active=2))
    assert len(await repo.all()) == 2  # the failed attempt was rolled back


async def test_only_owner_can_cancel(repo):
    b = await repo.create_booking(**booking(user_id=1))
    assert await repo.cancel(b.id, user_id=2) is None
    cancelled = await repo.cancel(b.id, user_id=1)
    assert cancelled.status == "cancelled"
    assert await repo.cancel(b.id) is None  # already cancelled
    await repo.create_booking(**booking(user_id=3))  # the slot is free again


async def test_due_reminders(repo):
    soon = await repo.create_booking(**booking(start=NOW + H))
    await repo.create_booking(**booking(user_id=2, start=NOW + 5 * H))
    assert [b.id for b in await repo.due_reminders(NOW, NOW + 2 * H)] == [soon.id]
    await repo.mark_reminded(soon.id)
    assert await repo.due_reminders(NOW, NOW + 2 * H) == []


async def test_open_creates_missing_parent_folder(tmp_path):
    path = tmp_path / "data" / "bookings.db"
    repo = await Repository.open(str(path))
    await repo.close()
    assert path.exists()
