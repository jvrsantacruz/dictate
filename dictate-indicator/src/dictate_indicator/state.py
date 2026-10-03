"""The dictation state file, read as a value.

`dictate` writes `<phase> <epoch> <lang>` while it works and deletes the file
when it goes idle, so a missing file is the idle state and not an error. This
module holds no GTK, which is what makes it testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CAPTURING = "capturing"
TRANSCRIBING = "transcribing"
PHASES = (CAPTURING, TRANSCRIBING)


@dataclass(frozen=True)
class State:
    """What dictation is doing right now."""

    phase: str | None = None
    started: int = 0
    lang: str = ""

    @property
    def active(self) -> bool:
        """Whether there is anything to show."""
        return self.phase is not None

    def elapsed(self, now: float) -> int:
        """Count the seconds since the phase began.

        Never negative: a clock that steps backwards must not print a
        countdown.
        """
        return max(0, int(now) - self.started)


IDLE = State()


def parse(text: str) -> State:
    """Read one state line.

    Anything unexpected reads as idle. The file is written by a shell
    redirection, so a read can land mid-write, and showing nothing is better
    than showing a phase that was never true.
    """
    fields = text.split()
    if len(fields) < 2 or fields[0] not in PHASES:  # noqa: PLR2004
        return IDLE
    try:
        started = int(fields[1])
    except ValueError:
        return IDLE
    lang = fields[2] if len(fields) > 2 else ""  # noqa: PLR2004
    return State(fields[0], started, lang)


def read(path: Path) -> State:
    """Read the state on disk, or idle when the file is absent or unreadable."""
    try:
        return parse(path.read_text(encoding="utf-8"))
    except OSError:
        return IDLE


def default_path() -> Path:
    """Where `dictate` puts the file. Same expression as the shell side."""
    # Never /tmp: a directory there could be another user's, made first.
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "dictate" / "state"
