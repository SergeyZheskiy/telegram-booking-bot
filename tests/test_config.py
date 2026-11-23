import tomllib

import pytest

from booking_bot.config import ConfigError, load_config, parse_admin_ids

from .conftest import ROOT


def base() -> dict:
    with open(ROOT / "config.example.toml", "rb") as f:
        return tomllib.load(f)


def test_example_config_is_valid(cfg):
    assert cfg.hours[6] is None  # Sunday closed
    assert [s.id for s in cfg.services] == ["haircut", "beard", "combo"]
    assert cfg.service("beard").duration.total_seconds() == 30 * 60
    assert cfg.service("nope") is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["schedule"]["hours"].update(mon="20:00-10:00"), "schedule.hours.mon"),
        (lambda d: d["schedule"]["hours"].update(funday="10:00-12:00"), "unknown weekday"),
        (lambda d: d["schedule"].update(hours={}), "at least one day"),
        (lambda d: d["schedule"]["hours"].update(tue="10-20"), "HH:MM-HH:MM"),
        (lambda d: d["services"][0].update(id="Hair Cut!"), "services[0].id"),
        (lambda d: d["services"][1].update(id="haircut"), "unique"),
        (lambda d: d["services"][0].update(duration=0), "duration"),
        (lambda d: d["business"].update(timezone="Mars/Olympus"), "time zone"),
        (lambda d: d["business"].update(language="de"), "language"),
        (lambda d: d.pop("services"), "[services]"),
    ],
)
def test_invalid_config_explains_what_is_wrong(mutate, message):
    data = base()
    mutate(data)
    with pytest.raises(ConfigError, match=message.replace("[", r"\[").replace("]", r"\]")):
        load_config(data)


def test_admin_ids():
    assert parse_admin_ids("1, 2 3") == {1, 2, 3}
    assert parse_admin_ids("") == frozenset()
    with pytest.raises(ConfigError):
        parse_admin_ids("@someone")
