"""Two ways to press keys on GNOME: ydotool on the desktop, remote desktop in tests.

ydotool writes to the kernel input layer, so its keys reach whatever desktop
runs on this seat, and that is why the headless tests cannot use it. GNOME's
remote desktop interface presses keys inside the shell it belongs to, which in
the tests is the private one.
"""

from __future__ import annotations

import contextlib
import subprocess
import time
from typing import TYPE_CHECKING, Protocol

from dictate.desktop import DesktopError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dictate.keymap import Chord


# ydotool waits between events; the timeout grows with the text, so a long
# dictation is not cut off partway with a key still held down.
KEY_DELAY_MS = 12
SEND_SLACK = 5
# Released after a failed send: a modifier left down holds for the desktop.
MODIFIERS = (42, 54, 29, 97, 56, 100)


def presses(chords: Sequence[Chord]) -> list[tuple[int, bool]]:
    """Every key down and up, modifiers around each chord."""
    events: list[tuple[int, bool]] = []
    for chord in chords:
        events.extend((mod, True) for mod in chord.mods)
        events.extend(((chord.code, True), (chord.code, False)))
        events.extend((mod, False) for mod in reversed(chord.mods))
    return events


class KeySender(Protocol):
    """Presses keys."""

    def send(self, chords: Sequence[Chord]) -> None:
        """Press `chords` in order."""
        ...


class Ydotool:
    """Keys through ydotoold and /dev/uinput."""

    def send(self, chords: Sequence[Chord]) -> None:
        """One ydotool call for the whole sequence."""
        events = presses(chords)
        args = [f"{code}:{int(down)}" for code, down in events]
        wait = len(events) * KEY_DELAY_MS / 1000 + SEND_SLACK
        try:
            subprocess.run(
                ["ydotool", "key", "-d", str(KEY_DELAY_MS), *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=wait,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as err:
            self._release({code for code, _ in events})
            msg = f"ydotool stopped, part of the text may be typed: {err}"
            raise DesktopError(msg) from err

    @staticmethod
    def _release(codes: set[int]) -> None:
        """Let go of every key the failed send used, and every modifier.

        A send killed between a key's down and up leaves it held for the whole
        desktop, and a held letter repeats.
        """
        ups = [f"{code}:0" for code in sorted(codes | set(MODIFIERS))]
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["ydotool", "key", *ups],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=SEND_SLACK,
                check=False,
            )


class RemoteDesktop:
    """Keys through org.gnome.Mutter.RemoteDesktop, in the shell on this bus."""

    _NAME = "org.gnome.Mutter.RemoteDesktop"
    _SESSION = "org.gnome.Mutter.RemoteDesktop.Session"
    # A virtual keyboard drops the first key it is given while it is still
    # being set up, so a modifier is pressed first and the rest waits.
    _WARMUP = 0.1
    _GAP = 0.01

    def send(self, chords: Sequence[Chord]) -> None:
        """Open a session, press, close it."""
        from gi.repository import Gio, GLib  # noqa: PLC0415 - gi only on demand

        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION)
        except GLib.Error as err:
            msg = f"no session bus: {err.message}"
            raise DesktopError(msg) from err

        def call(
            path: str, iface: str, method: str, args: GLib.Variant | None = None
        ) -> GLib.Variant:
            return conn.call_sync(
                self._NAME,
                path,
                iface,
                method,
                args,
                None,
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )

        try:
            self._press(call, chords)
        except GLib.Error as err:
            msg = f"remote desktop failed: {err.message}"
            raise DesktopError(msg) from err

    def _press(self, call, chords: Sequence[Chord]) -> None:  # noqa: ANN001
        from gi.repository import GLib  # noqa: PLC0415

        (path,) = call(
            "/org/gnome/Mutter/RemoteDesktop", self._NAME, "CreateSession"
        ).unpack()
        call(path, self._SESSION, "Start")
        try:
            for code, down in [(29, True), (29, False)]:
                call(
                    path,
                    self._SESSION,
                    "NotifyKeyboardKeycode",
                    GLib.Variant("(ub)", (code, down)),
                )
            time.sleep(self._WARMUP)
            for code, down in presses(chords):
                call(
                    path,
                    self._SESSION,
                    "NotifyKeyboardKeycode",
                    GLib.Variant("(ub)", (code, down)),
                )
                time.sleep(self._GAP)
        finally:
            call(path, self._SESSION, "Stop")
