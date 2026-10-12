"""The transcript log: off by default, the user's alone, and pruned."""

import datetime as dt
from pathlib import Path

from hamcrest import assert_that, equal_to, is_

from dictate import config, textlog

NOW = dt.datetime(2026, 10, 12, 9, 30, tzinfo=dt.UTC)


def _env(tmp_path: Path) -> dict[str, str]:
    return {"XDG_STATE_HOME": str(tmp_path)}


def test_off_by_default_writes_nothing(tmp_path: Path) -> None:
    textlog.append(config.Config(), _env(tmp_path), textlog.DELIVERED, "es", "Hola.")
    assert_that(textlog.path(_env(tmp_path)).exists(), is_(False))


def test_an_entry_is_time_language_outcome_text(tmp_path: Path) -> None:
    env = _env(tmp_path)
    textlog.append(config.Config(log=True), env, textlog.DELIVERED, "es", "Hola.")
    fields = textlog.path(env).read_text().rstrip("\n").split("\t")
    assert_that(fields[1:], is_(equal_to(["es", "delivered", "Hola."])))


def test_the_file_is_the_users_alone(tmp_path: Path) -> None:
    env = _env(tmp_path)
    textlog.append(config.Config(log=True), env, textlog.DELIVERED, "es", "Hola.")
    assert_that(textlog.path(env).stat().st_mode & 0o777, is_(equal_to(0o600)))


def test_old_lines_go_and_unreadable_ones_stay() -> None:
    lines = [
        textlog.line("delivered", "es", "old", NOW - dt.timedelta(days=31)),
        textlog.line("delivered", "es", "new", NOW - dt.timedelta(days=1)),
        "not a date\tes\tdelivered\tkept\n",
    ]
    kept = textlog.keep(lines, 30, NOW)
    texts = [k.rstrip("\n").split("\t")[3] for k in kept]
    assert_that(texts, is_(equal_to(["new", "kept"])))


def test_tail_gives_the_last_entries(tmp_path: Path) -> None:
    env = _env(tmp_path)
    cfg = config.Config(log=True)
    for text in ("one", "two", "three"):
        textlog.append(cfg, env, textlog.DELIVERED, "en", text)
    last = [entry.split("\t")[3] for entry in textlog.tail(env, 2)]
    assert_that(last, is_(equal_to(["two", "three"])))


def test_no_log_has_no_tail(tmp_path: Path) -> None:
    assert_that(textlog.tail(_env(tmp_path), 5), is_(equal_to([])))
