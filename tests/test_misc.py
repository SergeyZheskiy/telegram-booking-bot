from datetime import datetime

from booking_bot.keyboards import ConfirmCb
from booking_bot.services import display_name
from booking_bot.texts import TEXTS, T


def test_callback_payloads_fit_telegram_64_byte_limit(cfg):
    far_future = int(datetime(2100, 1, 1).timestamp())
    for s in cfg.services:
        assert len(ConfirmCb(service=s.id, ts=far_future).pack().encode()) <= 64
    assert len(ConfirmCb(service="x" * 20, ts=far_future).pack().encode()) <= 64  # longest allowed id


def test_translations_are_complete_and_formatted():
    assert TEXTS["en"].keys() == TEXTS["ru"].keys()
    for lang in TEXTS:
        for key, value in TEXTS[lang].items():
            assert value.count("{") == value.count("}"), (lang, key)
    assert T("ru").day(datetime(2026, 3, 9).date()) == "Пн 09.03"


def test_display_name():
    assert display_name("Ann", None, "ann") == "Ann (@ann)"
    assert display_name(None, None, None) == "—"


def test_russian_flow_texts(cfg):
    t = T("ru")
    assert t("booked", service="Стрижка", day="Пн 09.03", time="10:00").startswith("✅ Вы записаны")
