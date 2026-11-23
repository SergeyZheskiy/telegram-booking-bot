"""End-to-end: real Telegram updates -> real dispatcher, routers, filters, keyboards and DB.

Only the network is fake (RecordingSession), so these tests exercise exactly what users would.
"""

from datetime import timedelta

from aiogram.types import User

from booking_bot.keyboards import ConfirmCb, DayCb, ServiceCb, TimeCb

from .conftest import ADMIN_ID, CLIENT, NOW

OTHER = User(id=200, is_bot=False, first_name="Bob")
ADMIN = User(id=ADMIN_ID, is_bot=False, first_name="Boss")


async def test_full_booking_conversation(bot_harness, repo):
    h = bot_harness
    await h.text("/start")
    assert "Demo Barbershop" in h.last("SendMessage").text

    await h.text("📅 Book")
    services = h.buttons("SendMessage")
    assert services[0] == ("Haircut · 45 min · 30 EUR", ServiceCb(service="haircut").pack())

    await h.press(services[0][1])
    days = h.buttons()
    # NOW is Monday 09:00 local; Sunday is closed, so 14 days ahead give 12 working days
    assert days[0][0] == "Mon 09.03" and len(days) == 12 + 1  # + back button
    assert all("Sun" not in label for label, _ in days)

    await h.press(days[0][1])
    times = h.buttons()
    assert times[0][0] == "10:00"  # 09:00 now + 60 min lead time
    assert "14:00" not in [label for label, _ in times]  # lunch break
    assert "13:30" not in [label for label, _ in times]  # 45 min would overlap the break

    await h.press(times[0][1])
    assert "Please confirm" in h.last().text and "30 EUR" in h.last().text

    await h.press(h.buttons()[0][1])  # ✅ Confirm
    assert "You're booked" in h.last().text
    admin_note = h.session.sent("SendMessage")[-1]
    assert admin_note.chat_id == ADMIN_ID and "New booking #1" in admin_note.text and "@ann_test" in admin_note.text

    [booking] = await repo.all()
    assert booking.user_id == CLIENT.id and booking.starts_at == NOW + timedelta(hours=1)


async def test_taken_slot_disappears_and_stale_confirm_is_refused(bot_harness, repo):
    h = bot_harness
    await h.press(DayCb(service="haircut", day="20260309").pack())
    ten = next(data for label, data in h.buttons() if label == "10:00")
    ts = TimeCb.unpack(ten).ts

    await h.press(ConfirmCb(service="haircut", ts=ts).pack(), user=OTHER)  # Bob is faster
    await h.press(ConfirmCb(service="haircut", ts=ts).pack())  # Ann's button is now stale
    assert h.alerts()[-1].startswith("That time is no longer available")
    assert len(await repo.all()) == 1

    await h.press(DayCb(service="haircut", day="20260309").pack())
    assert "10:00" not in [label for label, _ in h.buttons()]


async def test_forged_callback_outside_working_hours_is_refused(bot_harness, repo):
    h = bot_harness
    sunday_noon = int((NOW + timedelta(days=6, hours=3)).timestamp())
    await h.press(ConfirmCb(service="haircut", ts=sunday_noon).pack())
    await h.press(ConfirmCb(service="nope", ts=sunday_noon).pack())
    assert await repo.all() == []


async def test_my_bookings_and_cancel(bot_harness, repo):
    h = bot_harness
    await h.press(ConfirmCb(service="beard", ts=int((NOW + timedelta(hours=3)).timestamp())).pack())
    await h.text("🗂 My bookings")
    msg = h.last("SendMessage")
    assert "Beard trim" in msg.text and "Mon 09.03, 12:00" in msg.text
    cancel = h.buttons("SendMessage")[0][1]

    await h.press(cancel, user=OTHER)  # not Bob's booking
    assert h.alerts()[-1].startswith("This booking is already cancelled")

    await h.press(cancel)
    assert "cancelled" in h.last().text
    assert "cancelled by the client" in h.session.sent("SendMessage")[-1].text
    await h.text("🗂 My bookings")
    assert h.last("SendMessage").text == "You have no upcoming bookings."


async def test_admin_commands_are_admin_only(bot_harness):
    h = bot_harness
    await h.press(ConfirmCb(service="haircut", ts=int((NOW + timedelta(hours=2)).timestamp())).pack())

    await h.text("/today", user=CLIENT)
    assert "didn't get that" in h.last("SendMessage").text  # falls through to the client fallback

    await h.text("/today", user=ADMIN)
    agenda = h.last("SendMessage").text
    assert "#1 11:00 — Haircut" in agenda and "tg://user?id=100" in agenda

    await h.text("/export", user=ADMIN)
    doc = h.last("SendDocument").document
    assert doc.filename == "bookings-20260309.csv"
    assert b"Haircut,2026-03-09 11:00" in doc.data

    await h.text("/cancel 1", user=ADMIN)
    client_note, admin_note = h.session.sent("SendMessage")[-2:]
    assert client_note.chat_id == CLIENT.id and "was cancelled" in client_note.text
    assert admin_note.text == "Booking #1 cancelled; the client has been notified."
