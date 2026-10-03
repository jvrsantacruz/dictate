"""GNOME on Wayland: the clipboard through wl-clipboard, keys, and the engine.

What the engine cannot tell: IBus reaches applications through GNOME Shell,
which follows every focus out with a focus in, its own when no window is
left, and does so whether the widget that gained focus takes text or not. So
"focused" is always true here, and only a change of focus can be seen: a
button focused in the same window looks like an input.

GNOME offers no clipboard protocol to a program without a window, so
`wl-copy` and `wl-paste` each map a surface for a moment to take focus. Every
check of focus therefore happens before the clipboard is touched, and a paste
waits for focus to come back before it presses anything.
"""

from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING

from gi.repository import Gio, GLib

from dictate.desktop import Clip, DesktopError, Focus
from dictate.gnome import bus as engine_bus
from dictate.gnome.rules import paste_chord, text_type

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dictate.gnome.keys import KeySender
    from dictate.keymap import Chord

CALL_MS = 500
CLIPBOARD_WAIT = 2.0
FOCUS_BACK = 1.0
PASTE_SETTLE = 0.5
POLL = 0.02
SETTLED = 0.1


def _run(
    argv: list[str], data: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run a tool, turning every way it can fail into `DesktopError`."""
    try:
        return subprocess.run(
            argv, input=data, capture_output=True, timeout=CLIPBOARD_WAIT, check=False
        )
    except (OSError, subprocess.SubprocessError) as err:
        msg = f"{argv[0]} failed: {err}"
        raise DesktopError(msg) from err


class GnomeWayland:
    """The `Desktop` port on GNOME on Wayland."""

    def __init__(self, keys: KeySender) -> None:
        """Connect to the session bus, where the engine answers."""
        self._keys = keys
        self._purpose = 0
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        except GLib.Error as err:
            msg = f"no session bus: {err.message}"
            raise DesktopError(msg) from err

    def _call(self, method: str, args: GLib.Variant | None = None) -> tuple | None:
        try:
            reply = self._bus.call_sync(
                engine_bus.NAME, engine_bus.PATH, engine_bus.INTERFACE, method,
                args, None, Gio.DBusCallFlags.NO_AUTO_START, CALL_MS, None,
            )  # fmt: skip
        except GLib.Error:
            return None
        return reply.unpack()

    def _engine_focus(self) -> tuple[str, bool, int] | None:
        """The engine's answer whole: token, focused, and the input's purpose."""
        reply = self._call("Focus")
        return None if reply is None else (reply[0], reply[1], reply[2])

    def focus(self) -> Focus | None:
        """Ask the engine. The input's purpose is kept for the paste key.

        Kept from here because delivery asks before it touches the clipboard,
        and wl-paste moves focus: asked later, the purpose could be another's.
        """
        reply = self._engine_focus()
        if reply is None:
            return None
        self._purpose = reply[2]
        return Focus(reply[0], focused=reply[1])

    def commit(self, text: str, token: str) -> bool:
        """The engine checks the token and inserts, in one step."""
        reply = self._call("Commit", GLib.Variant("(ss)", (text, token)))
        return bool(reply and reply[0])

    def type_chords(self, chords: Sequence[Chord]) -> None:
        """Press the keys."""
        self._keys.send(chords)

    def clipboard_read(self) -> Clip:
        """The text on the clipboard, or whether something else is lost."""
        listed = _run(["wl-paste", "--list-types"])
        types = listed.stdout.decode().split() if listed.returncode == 0 else []
        mime = text_type(types)
        if mime is None:
            return Clip(lost=bool(types))
        data = _run(["wl-paste", "--no-newline", "--type", mime])
        if data.returncode != 0:
            msg = f"wl-paste could not read {mime}"
            raise DesktopError(msg)
        return Clip(text=data.stdout.decode("utf-8", "replace"))

    def clipboard_write(self, text: str) -> None:
        """wl-copy forks a process that serves the text until it is replaced.

        Its output is not captured: the forked child would hold the pipe open
        and the wait would last as long as the clipboard does.
        """
        try:
            proc = subprocess.run(
                ["wl-copy"], input=text.encode(), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=CLIPBOARD_WAIT, check=False,
            )  # fmt: skip
        except (OSError, subprocess.SubprocessError) as err:
            msg = f"wl-copy failed: {err}"
            raise DesktopError(msg) from err
        if proc.returncode != 0:
            msg = f"wl-copy exited {proc.returncode}"
            raise DesktopError(msg)

    def clipboard_restore(self, clip: Clip) -> None:
        """Put the text back, or clear what the paste left, or leave the loss."""
        if clip.text is not None:
            self.clipboard_write(clip.text)
        elif not clip.lost:
            _run(["wl-copy", "--clear"])

    def _focus_back(self, before: tuple[str, bool, int] | None) -> bool:
        """Wait for focus to leave for wl-copy's surface and come back.

        Back means the token moved and then held still for a moment: wl-copy
        moves focus out and in, and the first change is only the way out.
        Gives up waiting after a second, and goes on if an input holds focus:
        a desktop that hands wl-copy the clipboard without a surface would
        never move focus at all.
        """
        deadline = time.monotonic() + FOCUS_BACK
        seen, since = None, 0.0
        while time.monotonic() < deadline:
            now = self._engine_focus()
            moved = now and now[1] and (before is None or now[0] != before[0])
            if moved and now[0] == seen:
                if time.monotonic() - since >= SETTLED:
                    return True
            elif moved:
                seen, since = now[0], time.monotonic()
            time.sleep(POLL)
        now = self._engine_focus()
        return bool(now and now[1])

    def paste(self, text: str) -> bool:
        """Copy, wait for focus to come back from wl-copy, press the paste key.

        The key is the one the input's purpose asks for. Whether the
        application took the text cannot be seen: GTK reads the clipboard as
        soon as it changes, paste or not, so `--paste-once` exits either way.
        The wait after the key gives the application time to read before
        delivery puts the old clipboard back.
        """
        before = self._engine_focus()
        self.clipboard_write(text)
        if not self._focus_back(before):
            return False
        self._keys.send([paste_chord(self._purpose)])
        time.sleep(PASTE_SETTLE)
        return True


def build(keys: str) -> GnomeWayland:
    """The adapter with the key sender the settings name."""
    from dictate.gnome.keys import RemoteDesktop, Ydotool  # noqa: PLC0415

    return GnomeWayland(RemoteDesktop() if keys == "remote-desktop" else Ydotool())
