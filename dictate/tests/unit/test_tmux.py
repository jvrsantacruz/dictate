"""The tmux plugin and the segment it draws, against a private tmux server."""

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to, is_, starts_with

DATA = Path(__file__).parents[2] / "data"


@pytest.fixture
def server(tmp_path: Path) -> Iterator[dict[str, str]]:
    """A tmux server of its own, and the environment that reaches it."""
    sock = tmp_path / "sock"
    subprocess.run(
        ["tmux", "-S", sock, "-f", "/dev/null", "new-session", "-d"], check=True
    )
    yield {"TMUX": f"{sock},0,0"}
    subprocess.run(["tmux", "-S", sock, "kill-server"], check=False)


def _bin(tmp_path: Path, *, dictate: bool) -> str:
    """A PATH holding only what the plugin runs, with or without dictate."""
    path = tmp_path / "bin"
    path.mkdir()
    for tool in ("bash", "tmux"):
        (path / tool).symlink_to(shutil.which(tool))
    if dictate:
        (path / "dictate-status").symlink_to(DATA / "dictate-status")
    return str(path)


def _tmux(env: dict[str, str], *args: str) -> str:
    run = subprocess.run(
        ["tmux", *args],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return run.stdout.strip()


def _plugin(env: dict[str, str], path: str) -> None:
    subprocess.run([DATA / "dictate.tmux"], env={**env, "PATH": path}, check=True)


def test_the_placeholder_becomes_the_segment(
    server: dict[str, str], tmp_path: Path
) -> None:
    _tmux(server, "set-option", "-g", "status-left", "#{dictate_status} #S ")
    _plugin(server, _bin(tmp_path, dictate=True))
    assert_that(
        _tmux(server, "show-option", "-gqv", "status-left"),
        is_(equal_to("#(dictate-status) #S")),
    )


def test_without_dictate_the_placeholder_goes(
    server: dict[str, str], tmp_path: Path
) -> None:
    _tmux(server, "set-option", "-g", "status-right", "#{dictate_status}%H:%M")
    _plugin(server, _bin(tmp_path, dictate=False))
    assert_that(
        _tmux(server, "show-option", "-gqv", "status-right"), is_(equal_to("%H:%M"))
    )


def test_a_second_run_changes_nothing(server: dict[str, str], tmp_path: Path) -> None:
    _tmux(server, "set-option", "-g", "status-left", "[#{dictate_status}]")
    _tmux(server, "set-option", "-g", "status-right", "untouched")
    path = _bin(tmp_path, dictate=True)
    _plugin(server, path)
    _plugin(server, path)
    assert_that(
        _tmux(server, "show-option", "-gqv", "status-left"),
        is_(equal_to("[#(dictate-status)]")),
    )
    assert_that(
        _tmux(server, "show-option", "-gqv", "status-right"), is_(equal_to("untouched"))
    )


def _segment(tmp_path: Path, phase: str | None, env: dict[str, str]) -> str:
    runtime = tmp_path / "run"
    (runtime / "dictate").mkdir(parents=True)
    if phase:
        (runtime / "dictate" / "state").write_text(f"{phase} {int(time.time())} en\n")
    run = subprocess.run(
        [DATA / "dictate-status"],
        env={**os.environ, **env, "XDG_RUNTIME_DIR": str(runtime)},
        capture_output=True,
        text=True,
        check=True,
    )
    return run.stdout


def test_recording_takes_the_users_style(
    server: dict[str, str], tmp_path: Path
) -> None:
    _tmux(server, "set-option", "-g", "@dictate-rec-style", "fg=blue")
    assert_that(
        _segment(tmp_path, "capturing", server), starts_with("#[fg=blue] REC EN 0:0")
    )


def test_transcribing_keeps_the_default_style_outside_tmux(tmp_path: Path) -> None:
    out = _segment(tmp_path, "transcribing", {"TMUX": ""})
    assert_that(out, starts_with("#[fg=#1c1c1e,bg=#ff9500,bold] "))


def test_idle_draws_nothing(server: dict[str, str], tmp_path: Path) -> None:
    assert_that(_segment(tmp_path, None, server), is_(equal_to("")))
