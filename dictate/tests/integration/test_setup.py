"""`dictate setup` in the private shell: settings, IBus, and the layout followed.

A module of its own, run last: it changes the layout, which
every other case assumes is us+intl.
"""

import subprocess
import time

import test_headless as h
from test_headless import ENV, ROOT, Case, _keys

setUpModule = h.setUpModule
tearDownModule = h.tearDownModule


def _setup(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ENV["ARTIFACT"], "setup", "--command", "/usr/bin/dictate", *args],
        capture_output=True, text=True, env=ENV, timeout=60, check=False,
    )  # fmt: skip


def _get(schema: str, key: str) -> str:
    return subprocess.run(
        ["gsettings", "get", schema, key], capture_output=True, text=True, check=True
    ).stdout.strip()


class Setup(Case):
    def test_setup_writes_everything_once_and_the_engine_follows_the_layout(
        self,
    ) -> None:
        first = _setup("--layout", "us", "--method", "ime")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("changed IBus", first.stdout)
        config = (ROOT / "config" / "dictate" / "config").read_text()
        self.assertIn('DICTATE_LAYOUT="us"', config)
        self.assertEqual(
            _get("org.gnome.desktop.input-sources", "sources"),
            "[('ibus', 'dictate'), ('xkb', 'us')]",
        )
        paths = _get(
            "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"
        )
        self.assertIn("dictate-en/", paths)
        self.assertIn("dictate-es/", paths)

        second = _setup("--layout", "us", "--method", "ime")
        self.assertEqual(second.stdout.strip(), "unchanged", second.stdout)

        # IBus restarted, so the window lost its input: a new one, on the new
        # layout, where an apostrophe is a plain key and composes nothing.
        self.win.close()
        type(self).win = h.Window("3", ENV, ROOT / "gtk3-setup.log", nudge=h._escape)  # noqa: SLF001
        self.win.focus("1")
        apostrophe, e = 40, 18
        _keys(apostrophe, e)
        time.sleep(0.3)
        self.assertEqual(self.win.texts()[0], "'e")
