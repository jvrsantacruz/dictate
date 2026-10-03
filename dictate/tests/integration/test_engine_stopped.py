"""The headless tier's last case, alone: it stops the engine for good.

A module of its own, run after test_headless, with a shell of its own.
"""

import subprocess
import time

import test_headless as h
from test_headless import ENV, Case, _engine_on_bus, _keys, _wait

setUpModule = h.setUpModule
tearDownModule = h.tearDownModule


class EngineStopped(Case):
    def test_typing_still_works_and_dictation_falls_back(self) -> None:
        subprocess.run(["pkill", "-f", f"{ENV['ARTIFACT']} engine"], check=False)
        _wait("the engine to leave the bus", lambda: not _engine_on_bus(), timeout=10)
        self.win.focus("1")
        apostrophe, e = 40, 18
        _keys(30, apostrophe, e)
        time.sleep(0.3)
        # GTK 3 composes dead keys itself, so this holds without the engine.
        self.assertEqual(self.win.texts()[0], "aé")
        self.win.clear()
        result = h.run.dictate("ime")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.win.texts(), ["", ""])
        self.assertIn("focus was unknown", self.failures())
