"""The transcript log: every dictated text, kept so none is lost.

Off unless `DICTATE_LOG="true"`. One line per text, tab separated:

    2026-10-12T09:30:00+02:00   es   delivered   the text

One entry per dictation, with its final text: `delivered` went into the
input, `clipboard` went to the clipboard instead. Streamed pieces are not
written: the text shown while speaking may differ from the final one. The
file is the user's alone, and lines older than `DICTATE_LOG_DAYS` go at the
end of a dictation.
Nothing typed into a password or PIN field is written.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dictate.config import Config

DELIVERED = "delivered"
CLIPBOARD = "clipboard"


def path(environ: Mapping[str, str]) -> Path:
    """`$XDG_STATE_HOME/dictate/log`: kept across reboots, unlike the runtime files."""
    base = environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "dictate" / "log"


def line(outcome: str, lang: str, text: str, now: dt.datetime) -> str:
    """One entry. The text is already one line with no control characters."""
    return f"{now.isoformat(timespec='seconds')}\t{lang}\t{outcome}\t{text}\n"


def append(
    cfg: Config, environ: Mapping[str, str], outcome: str, lang: str, text: str
) -> None:
    """Add one entry, when the log is on. A log that cannot be written is skipped.

    The text is already delivered or on the clipboard by then, so a full disk
    must not turn it into a failure.
    """
    if not cfg.log or not text:
        return
    target = path(environ)
    with contextlib.suppress(OSError):
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)  # a file made before, by hand, is the user's alone too
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(line(outcome, lang, text, dt.datetime.now().astimezone()))


def keep(lines: list[str], days: int, now: dt.datetime) -> list[str]:
    """The lines younger than `days`. A line whose time cannot be read is kept."""
    oldest = now - dt.timedelta(days=days)
    kept = []
    for entry in lines:
        try:
            when = dt.datetime.fromisoformat(entry.split("\t", 1)[0])
        except ValueError:
            kept.append(entry)
            continue
        if when.tzinfo is None or when >= oldest:
            # A time with no zone cannot be compared: kept, like an unreadable one.
            kept.append(entry)
    return kept


def prune(cfg: Config, environ: Mapping[str, str]) -> None:
    """Drop the lines past `DICTATE_LOG_DAYS`, rewriting the file only if any go."""
    if not cfg.log:
        return
    target = path(environ)
    with contextlib.suppress(OSError, UnicodeDecodeError):
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = keep(lines, cfg.log_days, dt.datetime.now().astimezone())
        if len(kept) == len(lines):
            return
        tmp = target.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(kept)
        tmp.replace(target)


def capture_path(environ: Mapping[str, str], lang: str) -> Path:
    """Where a recording no transcriber took waits for `dictate retry`."""
    return path(environ).with_name(f"failed.{lang}.wav")


def kept_capture(environ: Mapping[str, str]) -> tuple[Path, str] | None:
    """The kept recording and its language, or None."""
    for found in sorted(path(environ).parent.glob("failed.*.wav")):
        return found, found.name.split(".")[1]
    return None


def keep_capture(environ: Mapping[str, str], wav: Path, lang: str) -> Path | None:
    """Move a recording no transcriber took out of the runtime directory.

    One at a time, the user's alone: the next failure replaces it, and a retry
    that transcribes it deletes it. None when it cannot be kept.
    """
    target = capture_path(environ, lang)
    try:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for old in target.parent.glob("failed.*.wav"):
            old.unlink(missing_ok=True)
        data = wav.read_bytes()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except OSError:
        return None
    return target


def tail(environ: Mapping[str, str], count: int) -> list[str]:
    """The last `count` entries, oldest first; none when there is no log."""
    try:
        lines = path(environ).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return lines[-count:]
