"""Hold a remote desktop session open, so the headless seat has a keyboard.

A headless shell's seat has no keyboard of its own, and without one no window
holds focus and wl-copy refuses to run. A new window is only focused once this
keyboard has pressed a key, so each line on stdin is key codes to press.
Runs until stdin closes.
"""

import sys
import time

from gi.repository import Gio, GLib

NAME = "org.gnome.Mutter.RemoteDesktop"
SESSION = f"{NAME}.Session"
bus = Gio.bus_get_sync(Gio.BusType.SESSION)


def call(
    path: str, iface: str, method: str, args: GLib.Variant | None = None
) -> GLib.Variant:
    return bus.call_sync(
        NAME, path, iface, method, args, None, Gio.DBusCallFlags.NONE, 5000, None
    )


path = call("/org/gnome/Mutter/RemoteDesktop", NAME, "CreateSession").unpack()[0]
call(path, SESSION, "Start")
print("ready", flush=True)
for line in sys.stdin:
    for code in map(int, line.split()):
        for down in (True, False):
            call(
                path,
                SESSION,
                "NotifyKeyboardKeycode",
                GLib.Variant("(ub)", (code, down)),
            )
            time.sleep(0.02)
    print("sent", flush=True)
