"""The state file is written by a shell script, so it can be anything."""

import os
import time
from pathlib import Path

from hamcrest import assert_that, equal_to, is_

from dictate_indicator import state


def test_a_full_line_reads_as_a_phase() -> None:
    assert_that(
        state.parse("capturing 1700000000 en"),
        is_(equal_to(state.State("capturing", 1700000000, "en"))),
    )


def test_a_missing_language_is_allowed() -> None:
    assert_that(state.parse("transcribing 1700000000").lang, is_(equal_to("")))


def test_a_half_written_line_reads_as_idle() -> None:
    assert_that(state.parse("captur"), is_(equal_to(state.IDLE)))


def test_an_unknown_phase_reads_as_idle() -> None:
    assert_that(state.parse("exploding 1700000000 en"), is_(equal_to(state.IDLE)))


def test_a_non_numeric_start_reads_as_idle() -> None:
    assert_that(state.parse("capturing soon en"), is_(equal_to(state.IDLE)))


def test_an_empty_file_reads_as_idle() -> None:
    assert_that(state.parse(""), is_(equal_to(state.IDLE)))


def test_a_missing_file_reads_as_idle(tmp_path: Path) -> None:
    assert_that(state.read(tmp_path / "absent"), is_(equal_to(state.IDLE)))


def test_a_directory_in_place_of_the_file_reads_as_idle(tmp_path: Path) -> None:
    assert_that(state.read(tmp_path), is_(equal_to(state.IDLE)))


def test_a_written_file_reads_back(tmp_path: Path) -> None:
    path = tmp_path / "state"
    path.write_text("capturing 1700000000 es\n")
    assert_that(state.read(path).lang, is_(equal_to("es")))


def test_idle_is_not_active() -> None:
    assert_that(state.IDLE.active, is_(False))


def test_elapsed_counts_forward() -> None:
    assert_that(state.State("capturing", 100, "en").elapsed(107.9), is_(equal_to(7)))


def test_a_clock_that_stepped_back_does_not_count_down() -> None:
    assert_that(state.State("capturing", 200, "en").elapsed(100), is_(equal_to(0)))


def test_the_default_path_sits_under_the_runtime_directory(monkeypatch: object) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    assert_that(
        state.default_path(), is_(equal_to(Path("/run/user/1000/dictate/state")))
    )


def test_the_default_path_falls_back_to_the_users_run_directory_not_tmp(
    monkeypatch: object,
) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    expected = Path(f"/run/user/{os.getuid()}/dictate/state")
    assert_that(state.default_path(), is_(equal_to(expected)))


def test_the_clock_is_not_consulted_by_parsing() -> None:
    before = time.time()
    state.parse("capturing 1 en")
    assert_that(time.time() >= before, is_(True))
