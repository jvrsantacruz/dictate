"""The tray side. Every GTK call lives here and nothing else does."""

from __future__ import annotations

import logging
import signal
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from dictate_indicator import state as state_module  # noqa: E402
from dictate_indicator.view import Marker, render  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

log = logging.getLogger(__name__)

# The widest label the tray must reserve room for, so the panel does not
# reflow every time the timer crosses a digit.
LABEL_GUIDE = "ES 00:00"


class Tray:
    """An indicator that follows the dictation state file."""

    def __init__(
        self,
        state_path: Path,
        icon_dir: Path,
        clock: Callable[[], float],
    ) -> None:
        """Build the indicator and start following the state file."""
        self._path = state_path
        self._clock = clock
        self._timer: int | None = None
        self._phase: str | None = None

        self._indicator = AppIndicator.Indicator.new(
            "dictate-indicator",
            "",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(str(icon_dir))
        self._indicator.set_menu(self._menu())

        # The file is created and deleted rather than edited, so the directory
        # is what has to be watched: a monitor on a path that does not exist
        # yet never fires.
        self._monitor = Gio.File.new_for_path(str(state_path.parent)).monitor_directory(
            Gio.FileMonitorFlags.NONE,
            None,
        )
        self._monitor.connect("changed", self._on_change)
        self.refresh()

    def _menu(self) -> Gtk.Menu:
        # AppIndicator refuses to appear without a menu, so there is one, and
        # the only thing worth putting in it is a way out.
        menu = Gtk.Menu()
        item = Gtk.MenuItem(label="Quit")
        item.connect("activate", lambda _item: Gtk.main_quit())
        menu.append(item)
        menu.show_all()
        return menu

    def _on_change(
        self,
        _monitor: Gio.FileMonitor,
        changed: Gio.File,
        _other: Gio.File | None,
        _event: Gio.FileMonitorEvent,
    ) -> None:
        if changed.get_basename() == self._path.name:
            self.refresh()

    def _apply(self) -> Marker:
        current = state_module.read(self._path)
        marker = render(current, self._clock())
        if marker.visible:
            self._indicator.set_icon_full(marker.icon, marker.label)
            self._indicator.set_label(marker.label, LABEL_GUIDE)
            self._indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        else:
            self._indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
        # By phase, not by icon: the icon changes every second while capturing.
        if current.phase != self._phase:
            log.debug("indicator: %s", current.phase or "idle")
        self._phase = current.phase
        return marker

    def refresh(self) -> None:
        """Redraw now, and start the timer if there is something to count."""
        if self._apply().visible and self._timer is None:
            self._timer = GLib.timeout_add_seconds(1, self._tick)

    def _tick(self) -> bool:
        # The label counts seconds, so it needs a tick of its own. It runs only
        # while a phase is running, so an idle desktop is left alone.
        if self._apply().visible:
            return GLib.SOURCE_CONTINUE
        self._timer = None
        return GLib.SOURCE_REMOVE


def run(state_path: Path, icon_dir: Path, clock: Callable[[], float]) -> int:
    """Hold a tray on screen until the session or a signal ends it."""
    # The directory has to exist before it can be watched. `dictate` makes it
    # too, and whichever runs first wins.
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tray = Tray(state_path, icon_dir, clock)
    for sig in (signal.SIGINT, signal.SIGTERM):
        # GTK installs its own handlers, so the default ones never run and the
        # process would ignore a plain Ctrl-C.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    Gtk.main()
    del tray
    return 0
