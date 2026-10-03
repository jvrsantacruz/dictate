"""The capture: `pw-record`, started by one press and stopped by the next.

The recorder outlives the process that starts it, so it is found again through
its pidfile rather than as a child.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dictate.state import Paths

# s16, 16 kHz, mono is what whisper wants; anything else makes it resample.
FORMAT = ("--rate", "16000", "--channels", "1", "--format", "s16")
STOP_WAIT = 2.0
# `timeout` sends TERM at the cap, then KILL this much later if pw-record holds.
KILL_AFTER = 3
WRAPPER = "timeout"


def _ours(pid: int) -> bool:
    """Whether `pid` is still the recorder this module started.

    A pid outlives its process and is handed out again, so the pidfile alone
    could name an unrelated process: the wrapper's name is checked first.
    """
    try:
        comm = (Path("/proc") / str(pid) / "comm").read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if comm != WRAPPER:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def running(p: Paths) -> int | None:
    """The live recorder's pid, or None. A stale pidfile is removed."""
    try:
        pid = int(p.pidfile.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if _ours(pid):
        return pid
    p.pidfile.unlink(missing_ok=True)
    return None


def start(p: Paths, max_secs: int) -> int:
    """Start recording into `p.wav`, capped at `max_secs`.

    In its own session, so the shortcut's process group ending does not end it,
    and so the whole group can be killed if it will not stop.
    """
    p.wav.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [
            WRAPPER,
            "-k",
            str(KILL_AFTER),
            str(max_secs),
            "pw-record",
            *FORMAT,
            str(p.wav),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    p.pidfile.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def _wait_gone(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _ours(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not _ours(pid)


def stop(p: Paths, pid: int) -> None:
    """Stop the recorder cleanly: pw-record writes the WAV header on exit.

    INT first, which pw-record finishes on; TERM if it does not; then KILL to
    the whole session, so nothing keeps the microphone open.
    """
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, sig)
        if _wait_gone(pid, STOP_WAIT):
            break
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
    p.pidfile.unlink(missing_ok=True)
