"""The headless tier: every case of docs/development.md, in a private GNOME Shell.

Run by `run`, which has already isolated the bus, the settings and the runtime
directory. Keys are pressed through the shell's remote desktop interface.
"""

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

# The artifact under test is a zip, and Python imports from a zip on its path.
sys.path.insert(0, os.environ["ARTIFACT"])

from gi.repository import Gio, GLib
from harness import (
    EXPECTED,
    SAMPLE,
    Run,
    Transcriber,
    Window,
    clipboard_get,
    clipboard_set,
)

from dictate.gnome import bus as engine_bus

ROOT = Path(os.environ["IT_ROOT"])
ENV = dict(os.environ)
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01"
    b"\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

SETTINGS = (
    ("org.gnome.desktop.input-sources", "sources", "[('ibus', 'dictate')]"),
    # No lock screen, which would take focus from every window.
    ("org.gnome.desktop.screensaver", "lock-enabled", "false"),
    ("org.gnome.desktop.lockdown", "disable-lock-screen", "true"),
    ("org.gnome.desktop.session", "idle-delay", "uint32 0"),
    # A fresh profile gets the welcome tour, a dialog that holds focus.
    ("org.gnome.shell", "welcome-dialog-last-shown-version", "'999'"),
)

shell: subprocess.Popen[bytes]
keyboard: subprocess.Popen[str]
transcriber: Transcriber
run: Run


def _wait(what: str, check, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    msg = f"timed out waiting for {what}"
    raise RuntimeError(msg)


def _engine_on_bus() -> bool:
    return _has(engine_bus.NAME)


def _keys(*codes: int) -> None:
    """Press keys as a person would, on the keyboard the seat already has."""
    assert keyboard.stdin is not None
    assert keyboard.stdout is not None
    keyboard.stdin.write(" ".join(map(str, codes)) + "\n")
    keyboard.stdin.flush()
    keyboard.stdout.readline()


def _locked(path: Path) -> bool:
    if not path.exists():
        return False
    probe = subprocess.run(["flock", "-n", str(path), "true"], check=False)
    return probe.returncode != 0


def _recorders() -> int:
    """Fake recorders writing into this run's directory, and nothing else."""
    found = subprocess.run(
        ["pgrep", "-c", "-f", f"fakes/pw-record .*{ROOT}/"],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(found.stdout.strip() or 0)


def _escape() -> None:
    """Close the overview GNOME starts in: no window is focused while it shows."""
    _keys(1)


def setUpModule() -> None:
    global shell, keyboard, transcriber, run  # noqa: PLW0603
    for schema, key, value in SETTINGS:
        subprocess.run(["gsettings", "set", schema, key, value], check=True)
    # A session id logind does not know, or the shell would find the real
    # login session and follow its lock state.
    shell_env = {**ENV, "WAYLAND_DISPLAY": ""}
    shell = subprocess.Popen(
        ["gnome-shell", "--headless", "--virtual-monitor", "1280x800",
         "--wayland-display", ENV["WAYLAND_DISPLAY"], "--no-x11"],
        env=shell_env, stdout=(ROOT / "shell.log").open("wb"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    socket = ROOT / "run" / ENV["WAYLAND_DISPLAY"]
    _wait("the Wayland socket", socket.exists)
    _wait(
        "the remote desktop interface", lambda: _has("org.gnome.Mutter.RemoteDesktop")
    )
    keyboard = subprocess.Popen(
        ["/usr/bin/python3", str(Path(__file__).parent / "keyboard.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    assert keyboard.stdout is not None
    keyboard.stdout.readline()
    _wait("the dictate engine", _engine_on_bus, timeout=30)
    transcriber = Transcriber()
    run = Run(ENV["ARTIFACT"], {**ENV, "DICTATE_URL": transcriber.url,
                                "DICTATE_KEYS": "remote-desktop"}, ROOT)  # fmt: skip


def _has(name: str) -> bool:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    reply = bus.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", (name,)), None,
        Gio.DBusCallFlags.NONE, 1000, None,
    )  # fmt: skip
    return reply.unpack()[0]


def tearDownModule() -> None:
    transcriber.close()
    if keyboard.stdin:
        keyboard.stdin.close()
    keyboard.wait(timeout=5)
    shell.terminate()
    shell.wait(timeout=15)


class Case(unittest.TestCase):
    """One window per class: only the newest window is sure to hold focus."""

    window = "3"
    win: Window

    @classmethod
    def setUpClass(cls) -> None:
        cls.win = Window(cls.window, ENV, ROOT / f"gtk{cls.window}.log", nudge=_escape)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.win.close()
        time.sleep(0.5)

    def setUp(self) -> None:
        with (ROOT / "engine.log").open("a") as log:
            log.write(f"== {self.id()}\n")
        run.reset_logs()
        transcriber.text = SAMPLE
        self.win.clear()
        clipboard_set(ENV, b"keep me")
        self.win.focus("1")

    def tearDown(self) -> None:
        run.press("cancel")
        self.assertEqual(run.ydotool_log.read_text(), "", "ydotool used headless")
        time.sleep(0.3)
        self.assertEqual(_recorders(), 0, "a recorder outlived its dictation")

    def failures(self) -> str:
        return run.notifications()


class Delivered:
    """Mixed into one case per window and method."""

    method = ""

    def test_focus_unchanged_puts_the_text_in_the_input(self) -> None:
        result = run.dictate(self.method)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.win.texts(), [EXPECTED, ""])
        self.assertEqual(self.failures(), "")

    def test_the_clipboard_is_left_as_it_was(self) -> None:
        run.dictate(self.method)
        self.assertEqual(clipboard_get(ENV), "keep me")

    def test_focus_moved_falls_back_to_the_clipboard(self) -> None:
        run.press("en", DICTATE_METHOD=self.method)
        self.win.focus("2")
        result = run.press("en", DICTATE_METHOD=self.method)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.win.texts(), ["", ""])
        self.assertIn("focus moved", self.failures())
        self.assertEqual(clipboard_get(ENV), EXPECTED)


class Gtk3Ime(Delivered, Case):
    method = "ime"


class Gtk3Paste(Delivered, Case):
    method = "paste"


class Gtk3Type(Delivered, Case):
    method = "type"


class Gtk4Ime(Delivered, Case):
    window, method = "4", "ime"


class Gtk4Paste(Delivered, Case):
    window, method = "4", "paste"


class Gtk4Type(Delivered, Case):
    window, method = "4", "type"


class Keys:
    """Typing through the engine must be typing without it."""

    def test_keys_pass_through_with_the_dead_keys_of_us_intl(self) -> None:
        apostrophe, e, space, a = 40, 18, 57, 30
        _keys(a, apostrophe, e, apostrophe, space)
        time.sleep(0.3)
        self.assertEqual(self.win.texts()[0], "aé'")


class Gtk3Keys(Keys, Case):
    pass


class Gtk4Keys(Keys, Case):
    window = "4"


class Others(Case):
    def test_an_image_on_the_clipboard_is_reported_lost(self) -> None:
        clipboard_set(ENV, PNG, "image/png")
        self.win.focus("1")
        result = run.dictate("paste")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.win.texts()[0], EXPECTED)
        self.assertIn("clipboard held no text", self.failures())

    def test_a_session_without_an_adapter_fails_before_recording(self) -> None:
        result = run.press("en", DICTATE_METHOD="ime", XDG_CURRENT_DESKTOP="KDE")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no desktop adapter", self.failures())
        self.assertEqual(run.press("status").stdout.strip(), "idle")

    def test_text_the_layout_cannot_type_falls_back(self) -> None:
        transcriber.text = "10 €"
        result = run.dictate("type")
        self.assertEqual(result.returncode, 1)
        self.assertIn("€", self.failures())
        self.assertEqual(self.win.texts(), ["", ""])
        self.assertEqual(clipboard_get(ENV), "10 €")

    def test_a_second_press_during_the_start_cue_is_dropped(self) -> None:
        slow = {
            "DICTATE_METHOD": "ime",
            "DICTATE_SOUND": "true",
            "FAKE_CUE_SECS": "0.6",
        }
        env = {**run.env, **slow}
        first = subprocess.Popen([run.artifact, "en"], env=env)
        lock = ROOT / "run" / "dictate" / "lock"
        _wait("the first press to hold the lock", lambda: _locked(lock), timeout=5)
        second = run.press("en", **slow)
        first.wait(timeout=10)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(_recorders(), 1)

    def test_a_recording_the_cap_ended_is_delivered_by_the_next_press(self) -> None:
        capped = {"DICTATE_METHOD": "ime", "DICTATE_MAX_SECS": "1"}
        self.assertEqual(run.press("en", **capped).returncode, 0)
        time.sleep(2)
        self.assertEqual(_recorders(), 0)
        result = run.press("en", **capped)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.win.texts()[0], EXPECTED)
        self.assertEqual(run.press("status").stdout.strip(), "idle")

    def test_a_press_after_a_paste_is_accepted(self) -> None:
        run.dictate("paste")
        self.win.focus("1")
        self.assertEqual(run.press("en", DICTATE_METHOD="paste").returncode, 0)
        self.assertEqual(run.press("status").stdout.strip(), "recording")


if __name__ == "__main__":
    unittest.main()
