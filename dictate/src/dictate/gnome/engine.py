"""The IBus engine: types like the plain layout, reports focus, commits text.

Started by IBus as `dictate engine --ibus`. It is the permanent input source,
so typing through it must be what it is without it. It is built on IBus's
simple engine, the one behind GNOME's plain layouts, because a GTK 4
application leaves dead keys to the input method: an engine that passed them
through would lose every accent there.
"""

from __future__ import annotations

import logging
import signal

import gi

gi.require_version("IBus", "1.0")

from gi.repository import Gio, GLib, GObject, IBus  # noqa: E402

from dictate.gnome import bus as engine_bus  # noqa: E402
from dictate.gnome.component import ENGINE  # noqa: E402
from dictate.gnome.focus import Tracker  # noqa: E402

log = logging.getLogger(__name__)

tracker = Tracker()
engines: dict[int, Engine] = {}


class Engine(IBus.EngineSimple):
    """One instance per input context. On GNOME on Wayland there is one."""

    __gtype_name__ = "DictateEngine"

    # IBus builds the instance from C, so `__init__` never runs: the instance
    # is registered where it first matters, when it gains focus.
    def do_focus_in(self) -> None:
        """An input gained focus."""
        engines[id(self)] = self
        tracker.focus_in(id(self))
        log.debug("focus in %s", tracker.token)
        IBus.EngineSimple.do_focus_in(self)

    def do_focus_in_id(self, _object_path: str, _client: str) -> None:
        """The newer form of focus in, which IBus calls when the client has it."""
        engines[id(self)] = self
        tracker.focus_in(id(self))
        log.debug("focus in id %s", tracker.token)

    def do_focus_out(self) -> None:
        """The input lost focus."""
        tracker.focus_out(id(self))
        log.debug("focus out %s", tracker.token)
        IBus.EngineSimple.do_focus_out(self)

    def do_focus_out_id(self, _object_path: str) -> None:
        """The newer form of focus out."""
        tracker.focus_out(id(self))
        log.debug("focus out id %s", tracker.token)

    def do_disable(self) -> None:
        """Another input source was chosen: from here on, focus is not seen.

        Counted as focus leaving, so a dictation started before the switch
        falls back rather than trusting a token nothing updates any more.
        """
        tracker.disable(id(self))
        log.debug("disable %s", tracker.token)
        IBus.EngineSimple.do_disable(self)

    def do_set_content_type(self, purpose: int, _hints: int) -> None:
        """The input said what it is."""
        tracker.purpose(id(self), purpose)
        log.debug("purpose %s", purpose)

    def do_destroy(self) -> None:
        """The input context went away."""
        tracker.forget(id(self))
        engines.pop(id(self), None)
        IBus.EngineSimple.do_destroy(self)


def _on_call(
    _conn: Gio.DBusConnection,
    _sender: str,
    _path: str,
    _iface: str,
    method: str,
    params: GLib.Variant,
    invocation: Gio.DBusMethodInvocation,
) -> None:
    if method == "Focus":
        invocation.return_value(GLib.Variant("(sbu)", tracker.snapshot()))
        return
    if method == "Commit":
        text, token = params.unpack()
        holder = tracker.may_commit(token)
        engine = engines.get(holder) if holder is not None else None
        if engine is not None:
            engine.commit_text(IBus.Text.new_from_string(text))
        log.debug("commit %s", "done" if engine else "refused")
        invocation.return_value(GLib.Variant("(b)", (engine is not None,)))
        return
    invocation.return_dbus_error(f"{engine_bus.INTERFACE}.Unknown", method)


def _on_bus(conn: Gio.DBusConnection, _name: str) -> None:
    node = Gio.DBusNodeInfo.new_for_xml(engine_bus.INTROSPECTION)
    conn.register_object(engine_bus.PATH, node.interfaces[0], _on_call, None, None)


def run() -> int:
    """Serve IBus and the session bus until IBus stops the engine."""
    IBus.init()
    ibus = IBus.Bus()
    if not ibus.is_connected():
        log.error("engine: not connected to IBus")
        return 1
    loop = GLib.MainLoop()
    ibus.connect("disconnected", lambda _bus: loop.quit())
    factory = IBus.Factory.new(ibus.get_connection())
    factory.add_engine(ENGINE, GObject.type_from_name("DictateEngine"))
    ibus.request_name(engine_bus.NAME, 0)
    Gio.bus_own_name(
        Gio.BusType.SESSION,
        engine_bus.NAME,
        Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
        _on_bus,
        None,
        None,
    )
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, loop.quit)
    loop.run()
    return 0
