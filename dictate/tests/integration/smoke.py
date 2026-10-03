"""The live tier: the installed `dictate` on this desktop, with the real ydotool.

    python3 smoke.py /usr/bin/dictate

Opens a test window, so it takes keyboard focus for about 20 seconds, and the
screen must be unlocked. The microphone, the sound and the notifications are
faked, the transcriber too; the clipboard is saved first and put back after.
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from harness import EXPECTED, Run, Transcriber, Window, clipboard_get, clipboard_set

ARTIFACT = sys.argv.pop(1) if len(sys.argv) > 1 else "/usr/bin/dictate"
ENV = dict(os.environ)
WORK = Path(tempfile.mkdtemp(prefix="dictate-smoke."))
saved = ""
transcriber: Transcriber
run: Run


def _ready() -> str:
    """Why the live tier cannot run here, or empty when it can."""
    locked = subprocess.run(
        ["loginctl", "show-session", "auto", "-p", "LockedHint", "--value"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()  # fmt: skip
    if locked == "yes":
        return "the screen is locked"
    engine = subprocess.run(
        ["ibus", "engine"], capture_output=True, text=True, check=False
    )
    if engine.stdout.strip() != "dictate":
        return f"the input source is {engine.stdout.strip() or 'unknown'}, not dictate"
    return ""


def setUpModule() -> None:
    global saved, transcriber, run  # noqa: PLW0603
    reason = _ready()
    if reason:
        raise unittest.SkipTest(reason)
    saved = clipboard_get(ENV)
    transcriber = Transcriber()
    base = {**ENV, "DICTATE_URL": transcriber.url}
    run = Run(ARTIFACT, base, WORK, fakes=("pw-record", "pw-play", "notify-send"))


def tearDownModule() -> None:
    transcriber.close()
    clipboard_set(ENV, saved.encode())


class Live(unittest.TestCase):
    def test_every_method_in_both_gtk_versions(self) -> None:
        for version in ("3", "4"):
            for method in ("ime", "paste", "type"):
                with self.subTest(gtk=version, method=method):
                    run.reset_logs()
                    clipboard_set(ENV, b"keep me")
                    win = Window(version, ENV, WORK / f"gtk{version}.log")
                    try:
                        result = run.dictate(method)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(win.texts(), [EXPECTED, ""])
                        self.assertEqual(run.notifications(), "")
                    finally:
                        win.close()
                    self.assertEqual(clipboard_get(ENV), "keep me")
                    time.sleep(0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
