"""Desktop notifications and sound cues, each as the machine's settings say."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from pathlib import Path

STATE = "state"
FAILURE = "failure"
SOUNDS = Path("/usr/share/sounds/freedesktop/stereo")
START_CUE = "device-added"
STOP_CUE = "device-removed"
CUE_WAIT = 2


def should_notify(level: str, kind: str) -> bool:
    """`all` sends everything, `failures` only failures, `none` nothing."""
    if level == "none":
        return False
    return level == "all" or kind == FAILURE


class Feedback:
    """What the person at the desktop sees and hears."""

    def __init__(self, level: str, *, sound: bool) -> None:
        """Remember the two settings."""
        self._level = level
        self._sound = sound

    def notify(self, kind: str, message: str, ms: int = 2000) -> None:
        """A transient notification: shown, then dropped, never kept in the list."""
        if not should_notify(self._level, kind) or not shutil.which("notify-send"):
            return
        subprocess.run(
            ["notify-send", "-a", "dictate", "-e", "-t", str(ms), message],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def cue(self, name: str, *, wait: bool) -> None:
        """Play a theme sound when sound is on.

        The start cue is waited for, so the microphone does not record it. It
        is bounded, so a stuck audio server delays the start rather than eats
        it. The stop cue plays in the background: nothing is listening by then.
        """
        sound = SOUNDS / f"{name}.oga"
        if not self._sound or not sound.is_file():
            return
        cmd = ["pw-play", str(sound)]
        quiet = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if wait:
            with contextlib.suppress(subprocess.TimeoutExpired):
                subprocess.run(cmd, timeout=CUE_WAIT, check=False, **quiet)
        else:
            subprocess.Popen(cmd, start_new_session=True, **quiet)


def refresh_tmux() -> None:
    """Repaint the tmux segment now rather than up to a second later."""
    if shutil.which("tmux"):
        subprocess.run(
            ["tmux", "refresh-client", "-S"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
