"""The files between two presses, and the lock that orders them."""

import os
from pathlib import Path

from hamcrest import assert_that, equal_to, is_, none

from dictate import state


def _paths(tmp_path: Path) -> state.Paths:
    return state.paths({"XDG_RUNTIME_DIR": str(tmp_path)})


def test_the_state_line_keeps_the_shared_format(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    state.write_state(p, state.CAPTURING, 1700000000, "es")
    assert_that(p.statefile.read_text(), is_(equal_to("capturing 1700000000 es\n")))


def test_the_phase_reads_back(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    state.write_state(p, state.CAPTURING, 1, "en")
    assert_that(state.read_phase(p), is_(equal_to(state.CAPTURING)))
    state.write_state(p, None)
    assert_that(state.read_phase(p), is_(none()))


def test_idle_removes_the_state_file(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    state.write_state(p, state.CAPTURING, 1, "en")
    state.write_state(p, None)
    assert_that(p.statefile.exists(), is_(False))


def test_the_recording_language_comes_from_the_state(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    state.write_state(p, state.CAPTURING, 1, "es")
    assert_that(state.recording_lang(p, "en"), is_(equal_to("es")))


def test_without_a_state_the_default_language_is_used(tmp_path: Path) -> None:
    assert_that(state.recording_lang(_paths(tmp_path), "en"), is_(equal_to("en")))


def test_the_press_token_round_trips(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    state.write_press(p, "ab12:7")
    assert_that(state.read_press(p), is_(equal_to("ab12:7")))
    state.write_press(p, None)
    assert_that(state.read_press(p), is_(none()))


def test_a_second_lock_is_refused_while_the_first_is_held(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    first = state.lock(p)
    try:
        assert_that(state.lock(p), is_(none()))
    finally:
        assert first is not None
        os.close(first)
    second = state.lock(p)
    assert second is not None
    os.close(second)


def test_the_lock_is_not_inherited(tmp_path: Path) -> None:
    fd = state.lock(_paths(tmp_path))
    assert fd is not None
    try:
        assert_that(os.get_inheritable(fd), is_(False))
    finally:
        os.close(fd)
