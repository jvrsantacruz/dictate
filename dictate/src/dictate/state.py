"""The files under `$XDG_RUNTIME_DIR/dictate`, and the lock that orders presses.

`state` is `<phase> <epoch> <lang>` while dictation works and absent when
idle. The tray icon and the tmux segment read it, so its format is a contract
with both and does not change here. `press` holds the focus token taken at the
press that started the recording.
"""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

CAPTURING = "capturing"
TRANSCRIBING = "transcribing"


@dataclass(frozen=True)
class Paths:
    """Every file dictation keeps between two presses."""

    root: Path

    @property
    def wav(self) -> Path:
        """The capture. Deleted as soon as it has been turned into text."""
        return self.root / "audio.wav"

    @property
    def pidfile(self) -> Path:
        """The recorder, so the second press can stop what the first started."""
        return self.root / "recorder.pid"

    @property
    def statefile(self) -> Path:
        """What the tray icon and the tmux segment read."""
        return self.root / "state"

    @property
    def press(self) -> Path:
        """The focus token taken at the press."""
        return self.root / "press"

    @property
    def lock(self) -> Path:
        """Held for the whole of one press."""
        return self.root / "lock"


def paths(environ: Mapping[str, str]) -> Paths:
    """Where the files live, made if missing."""
    # Never /tmp: a directory there could be another user's, made first.
    runtime = environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    root = Path(runtime) / "dictate"
    root.mkdir(parents=True, exist_ok=True)
    return Paths(root)


def format_state(phase: str, started: int, lang: str) -> str:
    """One state line."""
    return f"{phase} {started} {lang}\n"


def write_state(p: Paths, phase: str | None, started: int = 0, lang: str = "") -> None:
    """Publish a phase, or idle when `phase` is None.

    Written to a temporary file and renamed, so a reader never sees half a line.
    """
    if phase is None:
        p.statefile.unlink(missing_ok=True)
        return
    tmp = p.statefile.with_suffix(".tmp")
    tmp.write_text(format_state(phase, started, lang), encoding="utf-8")
    tmp.replace(p.statefile)


def read_phase(p: Paths) -> str | None:
    """The published phase, or None when idle."""
    try:
        fields = p.statefile.read_text(encoding="utf-8").split()
    except OSError:
        return None
    return fields[0] if fields else None


def recording_lang(p: Paths, default: str) -> str:
    """The language the first press chose, so either shortcut can stop it."""
    try:
        fields = p.statefile.read_text(encoding="utf-8").split()
    except OSError:
        return default
    return fields[2] if len(fields) > 2 else default  # noqa: PLR2004


def write_press(p: Paths, token: str | None) -> None:
    """Keep the focus token of the press, or nothing when there was none."""
    if token is None:
        p.press.unlink(missing_ok=True)
    else:
        p.press.write_text(token, encoding="utf-8")


def read_press(p: Paths) -> str | None:
    """The token kept at the press, or None."""
    try:
        token = p.press.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def lock(p: Paths) -> int | None:
    """Take the press lock, or return None when another press holds it.

    The descriptor is not inherited, which is Python's default, so neither the
    recorder nor `wl-copy`'s clipboard daemon can keep it after this process
    has gone. That is the bug the shell version had.
    """
    fd = os.open(p.lock, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd
