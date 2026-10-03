"""A test window: two text inputs and a button, driven over stdin.

    python3 window.py 3|4

Prints `ready` once it holds focus, then answers one line per command:

    focus 1|2|button    give focus to that widget        -> ok
    texts               the text of both inputs, as JSON -> ["...", "..."]
    clear               empty both inputs                -> ok
"""

import json
import sys

import gi

VERSION = sys.argv[1]
gi.require_version("Gtk", f"{VERSION}.0")

from gi.repository import GLib, Gtk  # noqa: E402

window = Gtk.Window(title=f"dictate-test-gtk{VERSION}")
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
first, second, button = Gtk.Entry(), Gtk.Entry(), Gtk.Button(label="no text here")
for widget in (first, second, button):
    if VERSION == "3":
        box.add(widget)
    else:
        box.append(widget)
if VERSION == "3":
    window.add(box)
    window.show_all()
else:
    window.set_child(box)
window.present()
loop = GLib.MainLoop()
widgets = {"1": first, "2": second, "button": button}
announced = False


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def on_active(*_args: object) -> None:
    global announced  # noqa: PLW0603
    if window.is_active() and not announced:
        announced = True
        first.grab_focus()
        say("ready")


def on_line(channel: GLib.IOChannel, condition: GLib.IOCondition) -> bool:
    if condition & (GLib.IOCondition.HUP | GLib.IOCondition.ERR):
        loop.quit()
        return False
    line = channel.readline().strip()
    if not line:
        loop.quit()
        return False
    command, _, arg = line.partition(" ")
    if command == "focus":
        widgets[arg].grab_focus()
        say("ok")
    elif command == "texts":
        say(json.dumps([first.get_text(), second.get_text()], ensure_ascii=False))
    elif command == "clear":
        first.set_text("")
        second.set_text("")
        say("ok")
    else:
        say(f"error: {line}")
    return True


window.connect("notify::is-active", on_active)
window.connect("destroy" if VERSION == "3" else "close-request", lambda *_: loop.quit())
channel = GLib.IOChannel.unix_new(sys.stdin.fileno())
GLib.io_add_watch(
    channel, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN | GLib.IOCondition.HUP, on_line
)
loop.run()
