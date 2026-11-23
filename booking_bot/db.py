"""Async SQLite repository. Double booking is prevented inside a write transaction, not just in the UI."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    user_name   TEXT NOT NULL,
    service_id  TEXT NOT NULL,
    starts_at   TEXT NOT NULL,   -- UTC ISO-8601, so string order == time order
    ends_at     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | cancelled
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_bookings_time ON bookings (status, starts_at);
CREATE INDEX IF NOT EXISTS ix_bookings_user ON bookings (user_id, status);
"""


class SlotTaken(Exception):
    """Someone else booked an overlapping slot first."""


class TooManyBookings(Exception):
    """The user already has the maximum number of upcoming bookings."""


def to_db(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetimes are not allowed")
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True, slots=True)
class Booking:
    id: int
    user_id: int
    user_name: str
    service_id: str
    starts_at: datetime
    ends_at: datetime
    status: str
    reminded: bool
    created_at: datetime

    @classmethod
    def from_row(cls, r: aiosqlite.Row) -> "Booking":
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            user_name=r["user_name"],
            service_id=r["service_id"],
            starts_at=from_db(r["starts_at"]),
            ends_at=from_db(r["ends_at"]),
            status=r["status"],
            reminded=bool(r["reminded"]),
            created_at=from_db(r["created_at"]),
        )


class Repository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    @classmethod
    async def open(cls, path: str) -> "Repository":
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)  # SQLite creates the file, not its folder
        # isolation_level=None: we issue BEGIN ourselves, so the transaction boundaries are explicit
        conn = await aiosqlite.connect(path, isolation_level=None)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.executescript(SCHEMA)
        return cls(conn)

    async def close(self) -> None:
        await self.conn.close()

    async def create_booking(
        self,
        *,
        user_id: int,
        user_name: str,
        service_id: str,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
        max_active: int,
    ) -> Booking:
        # BEGIN IMMEDIATE takes the write lock up front: two users confirming the same slot at the
        # same moment are serialised, and the second one sees the first one's row and gets SlotTaken.
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            clash = await self.conn.execute_fetchall(
                "SELECT 1 FROM bookings WHERE status = 'active' AND starts_at < ? AND ends_at > ? LIMIT 1",
                (to_db(ends_at), to_db(starts_at)),
            )
            if clash:
                raise SlotTaken
            (active,) = (
                await self.conn.execute_fetchall(
                    "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND status = 'active' AND starts_at > ?",
                    (user_id, to_db(now)),
                )
            )[0]
            if active >= max_active:
                raise TooManyBookings
            cursor = await self.conn.execute(
                "INSERT INTO bookings (user_id, user_name, service_id, starts_at, ends_at, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, user_name, service_id, to_db(starts_at), to_db(ends_at), to_db(now)),
            )
            booking_id = cursor.lastrowid
            await self.conn.execute("COMMIT")
        except BaseException:
            await self.conn.execute("ROLLBACK")
            raise
        booking = await self.get(booking_id)
        assert booking is not None
        return booking

    async def get(self, booking_id: int) -> Booking | None:
        rows = await self.conn.execute_fetchall("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        return Booking.from_row(rows[0]) if rows else None

    async def busy_between(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        rows = await self.conn.execute_fetchall(
            "SELECT starts_at, ends_at FROM bookings WHERE status = 'active' AND starts_at < ? AND ends_at > ?",
            (to_db(end), to_db(start)),
        )
        return [(from_db(r["starts_at"]), from_db(r["ends_at"])) for r in rows]

    async def between(self, start: datetime, end: datetime) -> list[Booking]:
        rows = await self.conn.execute_fetchall(
            "SELECT * FROM bookings WHERE status = 'active' AND starts_at >= ? AND starts_at < ? ORDER BY starts_at",
            (to_db(start), to_db(end)),
        )
        return [Booking.from_row(r) for r in rows]

    async def upcoming_for_user(self, user_id: int, now: datetime) -> list[Booking]:
        rows = await self.conn.execute_fetchall(
            "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' AND starts_at > ? ORDER BY starts_at",
            (user_id, to_db(now)),
        )
        return [Booking.from_row(r) for r in rows]

    async def cancel(self, booking_id: int, *, user_id: int | None = None) -> Booking | None:
        """Cancel an active booking. With `user_id`, only the owner may cancel it."""
        sql = "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'"
        args: tuple = (booking_id,)
        if user_id is not None:
            sql += " AND user_id = ?"
            args += (user_id,)
        cursor = await self.conn.execute(sql, args)
        return await self.get(booking_id) if cursor.rowcount else None

    async def due_reminders(self, now: datetime, before: datetime) -> list[Booking]:
        rows = await self.conn.execute_fetchall(
            "SELECT * FROM bookings WHERE status = 'active' AND reminded = 0 AND starts_at > ? AND starts_at <= ?",
            (to_db(now), to_db(before)),
        )
        return [Booking.from_row(r) for r in rows]

    async def mark_reminded(self, booking_id: int) -> None:
        await self.conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))

    async def all(self) -> list[Booking]:
        rows = await self.conn.execute_fetchall("SELECT * FROM bookings ORDER BY starts_at")
        return [Booking.from_row(r) for r in rows]
