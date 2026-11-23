import itertools
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from booking_bot.config import load_config
from booking_bot.db import Repository
from booking_bot.handlers import admin, client
from booking_bot.texts import T

ROOT = Path(__file__).parent.parent
# Monday 9 March 2026, 08:00 UTC = 09:00 in Europe/Berlin
NOW = datetime(2026, 3, 9, 8, 0, tzinfo=UTC)
ADMIN_ID = 900
CLIENT = User(id=100, is_bot=False, first_name="Ann", username="ann_test")


@pytest.fixture
def cfg():
    with open(ROOT / "config.example.toml", "rb") as f:
        return load_config(tomllib.load(f), admin_ids=frozenset({ADMIN_ID}))


@pytest.fixture
async def repo(tmp_path):
    r = await Repository.open(str(tmp_path / "test.db"))
    yield r
    await r.close()


class Clock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


class RecordingSession(BaseSession):
    """Fake Bot API: records every outgoing method and returns plausible results."""

    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self._ids = itertools.count(1000)

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if type(method).__name__ in ("SendMessage", "SendDocument"):
            return Message(
                message_id=next(self._ids),
                date=NOW,
                chat=Chat(id=method.chat_id, type="private"),
                text=getattr(method, "text", None),
            )
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - not used
        yield b""

    async def close(self):
        pass

    def sent(self, kind: str) -> list[TelegramMethod]:
        return [c for c in self.calls if type(c).__name__ == kind]


_dispatcher: Dispatcher | None = None


def shared_dispatcher() -> Dispatcher:
    """aiogram routers are module-level and can join only one dispatcher, so tests share one
    and swap its injected data (repo, config, clock) per test."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher()
        _dispatcher.include_routers(admin.router, client.router)
    return _dispatcher


class Harness:
    """Feeds real Telegram updates through the real dispatcher and routers."""

    def __init__(self, cfg, repo, clock):
        self.session = RecordingSession()
        self.bot = Bot("42:TEST", session=self.session)
        self.dp = shared_dispatcher()
        self.dp.workflow_data.update(repo=repo, cfg=cfg, t=T(cfg.language), clock=clock)
        self._ids = itertools.count(1)

    async def text(self, text: str, user: User = CLIENT):
        msg = Message(
            message_id=next(self._ids), date=NOW, chat=Chat(id=user.id, type="private"), from_user=user, text=text
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._ids), message=msg))

    async def press(self, data: str, user: User = CLIENT):
        msg = Message(message_id=next(self._ids), date=NOW, chat=Chat(id=user.id, type="private"), text="…")
        cb = CallbackQuery(id=str(next(self._ids)), from_user=user, chat_instance="ci", message=msg, data=data)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._ids), callback_query=cb))

    def last(self, kind: str = "EditMessageText"):
        return self.session.sent(kind)[-1]

    def buttons(self, kind: str = "EditMessageText") -> list[tuple[str, str]]:
        markup = self.last(kind).reply_markup
        return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]

    def alerts(self) -> list[str]:
        return [c.text for c in self.session.sent("AnswerCallbackQuery") if c.text]


@pytest.fixture
def bot_harness(cfg, repo, clock):
    return Harness(cfg, repo, clock)
