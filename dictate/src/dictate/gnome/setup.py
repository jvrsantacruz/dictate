"""`dictate setup`: everything one user needs, so a package touches no user setting.

Each step reads what is there, works out what should be, and changes only the
difference. Every change prints one `changed ...` line, so configuration
management can tell a run that changed something from one that did not;
`--dry-run` prints them and changes nothing. GNOME's settings are read
and written through `gsettings`, so this module needs no `gi`.
"""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from dictate import config
from dictate.gnome.component import ENGINE, valid_layout

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SOURCES = ("org.gnome.desktop.input-sources", "sources")
MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
KEYBINDINGS = (MEDIA_KEYS, "custom-keybindings")
KEYBINDING_SCHEMA = f"{MEDIA_KEYS}.custom-keybinding"
KEYBINDING_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
OURS = f"{KEYBINDING_BASE}dictate"
IBUS_UNIT = "org.freedesktop.IBus.session.GNOME.service"
TRAY_UNIT = "dictate-indicator.service"
# ydotoold only for the methods that press keys.
KEY_UNIT = "ydotool.service"
ENGINE_WAIT = 15.0
DEFAULT_SHORTCUTS = {"en": "<Super>i", "es": "<Super>e"}
LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German"}
FLAGS = {
    "method": "DICTATE_METHOD",
    "notify": "DICTATE_NOTIFY",
    "backend": "DICTATE_BACKEND",
    "url": "DICTATE_URL",
    "model": "DICTATE_MODEL",
    "key_cmd": "DICTATE_KEY_CMD",
    "max_secs": "DICTATE_MAX_SECS",
    "default_lang": "DICTATE_LANG",
}


class SetupError(RuntimeError):
    """A step could not read or write what it needs."""


# --- pure rules -------------------------------------------------------------


def parse_variant(text: str) -> object:
    """Read what `gsettings get` prints for a list of strings or of pairs."""
    text = text.strip().removeprefix("@a(ss) ").removeprefix("@as ")
    return ast.literal_eval(text)


def format_sources(sources: Sequence[tuple[str, str]]) -> str:
    """The text `gsettings set` takes for input sources."""
    return (
        "[" + ", ".join(f"({a!r}, {b!r})" for a, b in sources) + "]"
        if sources
        else "@a(ss) []"
    )


def format_paths(paths: Sequence[str]) -> str:
    """The text `gsettings set` takes for a list of paths."""
    return "[" + ", ".join(repr(p) for p in paths) + "]" if paths else "@as []"


def pick_layout(sources: Sequence[tuple[str, str]], given: str) -> str:
    """The layout asked for, or the user's first plain one, or `us`."""
    if given != "auto":
        return given
    return next((name for kind, name in sources if kind == "xkb"), "us")


def merge_sources(
    sources: Sequence[tuple[str, str]], layout: str
) -> list[tuple[str, str]]:
    """The engine first, the user's own sources after it, the layout among them.

    The plain layout stays as the way out: if the engine ever hangs, every key
    waits on it, and Super+Space has something to switch to.
    """
    rest = [s for s in sources if s != ("ibus", ENGINE)]
    if ("xkb", layout) not in rest:
        rest.insert(0, ("xkb", layout))
    return [("ibus", ENGINE), *rest]


def keybinding_path(lang: str) -> str:
    """Where one language's shortcut lives."""
    return f"{OURS}-{lang}/"


def merge_paths(
    paths: Sequence[str], langs: Sequence[str]
) -> tuple[list[str], list[str]]:
    """The user's shortcuts kept, ours as `langs` says; and ours to remove."""
    mine = [keybinding_path(lang) for lang in langs]
    stale = [p for p in paths if p.startswith(OURS) and p not in mine]
    kept = [p for p in paths if not p.startswith(OURS)]
    return kept + mine, stale


def shortcuts(langs: Sequence[str], given: Sequence[str]) -> dict[str, str]:
    """Each language's key, from `LANG=KEYS` arguments over the defaults."""
    keys = {lang: DEFAULT_SHORTCUTS.get(lang, "") for lang in langs}
    for item in given:
        lang, sep, binding = item.partition("=")
        if not sep or lang not in keys or not binding:
            msg = f"--shortcut wants LANG=KEYS for one of {' '.join(langs)}: {item}"
            raise SetupError(msg)
        keys[lang] = binding
    missing = [lang for lang, binding in keys.items() if not binding]
    if missing:
        msg = f"no shortcut for {' '.join(missing)}: give --shortcut LANG=KEYS"
        raise SetupError(msg)
    return keys


def render_config(values: dict[str, str]) -> str:
    """The config file, one sorted `KEY="value"` line each."""
    lines = [
        "# Written by `dictate setup`. A value in the environment wins over this",
        "# file, so `DICTATE_METHOD=type dictate en` changes one run.",
    ]
    lines += [f'{key}="{values[key]}"' for key in sorted(values)]
    return "\n".join(lines) + "\n"


# --- the machine ------------------------------------------------------------


@dataclass
class Session:
    """The commands setup runs, and what it has changed."""

    dry_run: bool
    out: Callable[[str], None] = print
    changes: list[str] = field(default_factory=list)

    def run(self, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a tool, reading only."""
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=30, check=False
            )
        except (OSError, subprocess.SubprocessError) as err:
            msg = f"{argv[0]}: {err}"
            raise SetupError(msg) from err
        if check and proc.returncode != 0:
            msg = f"{' '.join(argv)}: {proc.stderr.strip() or proc.returncode}"
            raise SetupError(msg)
        return proc

    def change(self, what: str, *argv: str) -> None:
        """Report a change, and make it unless this is a dry run."""
        self.changes.append(what)
        self.out(f"changed {what}")
        if not self.dry_run and argv:
            self.run(*argv)

    def get(self, schema: str, key: str) -> str:
        """One GNOME setting, as gsettings prints it."""
        return self.run("gsettings", "get", schema, key).stdout.strip()


def _read(path: Path) -> str | None:
    """A text file, or None when it is missing or not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _config(s: Session, args: argparse.Namespace, layout: str) -> config.Config:
    """Write the config file; return what it now holds, checked."""
    path = config.default_path(os.environ)
    before = config.parse_file(_read(path) or "")
    values = dict(before)
    for flag, key in FLAGS.items():
        value = getattr(args, flag)
        if value is not None:
            values[key] = str(value)
    values["DICTATE_LAYOUT"] = layout
    values["DICTATE_LANGUAGES"] = " ".join(args.languages)
    if args.sound is not None:
        values["DICTATE_SOUND"] = "true" if args.sound == "true" else "false"
    for key, value in values.items():
        if '"' in value or "\n" in value:
            msg = f"{key} cannot hold a double quote or a newline"
            raise SetupError(msg)
    try:
        checked = config.build(values)
    except config.ConfigError as err:
        raise SetupError(str(err)) from err
    text = render_config(values)
    if _read(path) != text:
        s.change(f"config {path}")
        if not s.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
    return checked


def _engine_listed(s: Session) -> bool:
    proc = s.run("ibus", "list-engine", "--name-only", check=False)
    return proc.returncode == 0 and ENGINE in proc.stdout.split()


def engine_stale(program: str) -> bool:
    """Whether a running engine started before `program` was last replaced.

    IBus keeps the engine process it started, so after an upgrade the old
    code goes on running until IBus starts it again.
    """
    return stale(program, b"engine")


def stale(program: str, word: bytes | None = None) -> bool:
    """Whether a process of this user runs `program` from before it was replaced.

    `word`, when given, must also be one of its arguments.
    """
    try:
        # The change time, not the modification time: a package keeps the
        # build's fixed mtime, while the change time is the install's.
        changed = Path(program).stat().st_ctime
        boot = time.time() - float(Path("/proc/uptime").read_text().split()[0])
        ticks = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError):
        return False
    me = os.getuid()
    target = os.fsencode(os.path.realpath(program))
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != me:
                continue
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            # This very program only: another copy, such as a test's or
            # another session's, is not the one running here.
            if target not in argv or (word is not None and word not in argv):
                continue
            # Field 22 of stat, counted after the parenthesised command name.
            fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            started = boot + int(fields[19]) / ticks
        except (OSError, ValueError, IndexError):
            continue
        if started < changed:
            return True
    return False


def _cache() -> Path:
    """IBus's registry cache, which holds the engine's description."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ibus/bus/registry"


def _marker() -> Path:
    """The layout IBus was last seen to load, kept by setup alone.

    Not the config's layout: that is written first, so a restart that failed,
    or IBus not running, would leave a config that already says the new layout
    and nothing to say IBus never read it.
    """
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(base) / "dictate" / "engine-layout"


def _loaded(s: Session, layout: str) -> None:
    if s.dry_run:
        return
    marker = _marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(layout + "\n", encoding="utf-8")


def _ibus(s: Session, layout: str, program: str) -> bool:
    """Have IBus know the engine on the right layout. True when it does.

    IBus keeps the engine's description in its registry cache, so a new layout
    needs the cache gone and IBus restarted to ask the engine again. A program
    replaced since the engine started needs the restart too.
    """
    loaded = (_read(_marker()) or "").strip()
    reachable = s.run("ibus", "address", check=False).stdout.strip() not in {
        "",
        "(null)",
    }
    running = s.run("pgrep", "-u", str(os.getuid()), "-x", "ibus-daemon", check=False)
    if not reachable and running.returncode == 0:
        # ibus finds its daemon through the display: without one it says
        # "(null)" for a daemon that runs. Taking that for stopped would
        # record a layout the running IBus never loaded.
        msg = "IBus runs but cannot be reached: DISPLAY and WAYLAND_DISPLAY are unset"
        raise SetupError(msg)
    if not reachable:
        if loaded != layout:
            # The next IBus to start then builds its registry afresh.
            s.change("IBus registry cache cleared for the next login")
            if not s.dry_run:
                _cache().unlink(missing_ok=True)
                _loaded(s, layout)
        s.out("skipped IBus: not running, so the input source waits for a login")
        return False
    if _engine_listed(s) and loaded == layout and not engine_stale(program):
        return True
    s.change("IBus: restarted to read the engine")
    if s.dry_run:
        return True
    _cache().unlink(missing_ok=True)
    if s.run("systemctl", "--user", "cat", IBUS_UNIT, check=False).returncode == 0:
        s.run("systemctl", "--user", "restart", IBUS_UNIT)
    else:
        s.run("ibus", "restart")
    deadline = time.monotonic() + ENGINE_WAIT
    while time.monotonic() < deadline:
        if _engine_listed(s):
            _loaded(s, layout)
            return True
        time.sleep(0.5)
    s.out("warning IBus does not list the dictate engine; input sources left alone")
    return False


def _sources(s: Session, layout: str) -> None:
    current = parse_variant(s.get(*SOURCES))
    wanted = merge_sources(current, layout)
    if list(current) != wanted:
        s.change(
            f"input sources: {format_sources(wanted)}",
            "gsettings", "set", *SOURCES, format_sources(wanted),
        )  # fmt: skip


def _shortcuts(s: Session, keys: dict[str, str], command: str) -> None:
    current = parse_variant(s.get(*KEYBINDINGS))
    wanted, stale = merge_paths(current, list(keys))
    for path in stale:
        s.change(f"shortcut removed: {path}")
        if not s.dry_run:
            for key in ("name", "command", "binding"):
                s.run("gsettings", "reset", f"{KEYBINDING_SCHEMA}:{path}", key)
    if list(current) != wanted:
        s.change(
            "shortcut list", "gsettings", "set", *KEYBINDINGS, format_paths(wanted)
        )
    for lang, binding in keys.items():
        schema = f"{KEYBINDING_SCHEMA}:{keybinding_path(lang)}"
        values = {
            "name": f"Dictate {LANGUAGE_NAMES.get(lang, lang)}",
            "command": f"{command} {lang}",
            "binding": binding,
        }
        for key, value in values.items():
            if parse_variant(s.get(schema, key)) != value:
                s.change(
                    f"shortcut {lang} {key}: {value}",
                    "gsettings", "set", schema, key, repr(value),
                )  # fmt: skip


TRAY_PROGRAM = "/usr/bin/dictate-indicator"


def _tray_restart(s: Session) -> None:
    """Restart the tray icon if it runs code an upgrade has since replaced.

    `try-restart` touches only a running unit, so a tray stopped on purpose
    stays stopped.
    """
    if Path(TRAY_PROGRAM).exists() and stale(TRAY_PROGRAM):
        s.change(
            f"restarted {TRAY_UNIT}: the package replaced it",
            "systemctl", "--user", "try-restart", TRAY_UNIT,
        )  # fmt: skip


def _units(s: Session, method: str) -> None:
    live = s.run(
        "systemctl", "--user", "is-active", "graphical-session.target", check=False
    )
    units = [TRAY_UNIT, *([KEY_UNIT] if method in {"paste", "type"} else [])]
    for unit in units:
        if s.run("systemctl", "--user", "cat", unit, check=False).returncode != 0:
            continue
        enabled = s.run(
            "systemctl", "--user", "is-enabled", unit, check=False
        ).stdout.strip()
        # static, indirect, linked and the like need no enabling; masked is
        # the user's choice. Only a unit that says disabled is enabled here.
        if enabled != "disabled":
            continue
        now = ("--now",) if live.stdout.strip() == "active" else ()
        s.change(f"enabled {unit}")
        if s.dry_run:
            continue
        # A warning, not a failure: ydotoold cannot open /dev/uinput until the
        # login that reads the input group, and that is no reason to stop.
        done = s.run("systemctl", "--user", "enable", *now, unit, check=False)
        if done.returncode != 0:
            s.out(f"warning {unit} enabled but did not start: {done.stderr.strip()}")


UINPUT = Path("/dev/uinput")


def _uinput_warning(s: Session, method: str) -> None:
    """Warn that paste and type cannot press keys without /dev/uinput."""
    if method in {"paste", "type"} and not os.access(UINPUT, os.W_OK):
        s.out(
            f"warning {method} cannot write to {UINPUT}: install dictate-uinput, "
            "or log in again after joining the input group"
        )


def _ydotool_warning(s: Session, method: str) -> None:
    """Warn that paste and type need ydotool 1.0: older ones take other arguments."""
    if method not in {"paste", "type"} or not shutil.which("dpkg-query"):
        return
    version = s.run("dpkg-query", "-W", "-f=${Version}", "ydotool", check=False).stdout
    if not version:
        s.out(f"warning {method} needs ydotool 1.0 or later, which is not installed")
        return
    if (
        s.run(
            "dpkg", "--compare-versions", version, "lt", "1.0", check=False
        ).returncode
        == 0
    ):
        s.out(f"warning {method} needs ydotool 1.0 or later, this is {version}")


def _layout(s: Session, given: str) -> str:
    layout = pick_layout(parse_variant(s.get(*SOURCES)), given)
    if not valid_layout(layout):
        msg = f"not an XKB layout id: {layout}"
        raise SetupError(msg)
    return layout


def parser() -> argparse.ArgumentParser:
    """The command line of `dictate setup`."""
    p = argparse.ArgumentParser(
        prog="dictate setup", description=__doc__.splitlines()[0]
    )
    p.add_argument("--method", choices=config.METHODS)
    p.add_argument("--layout", default="auto", help="XKB id, or auto: the user's first")
    p.add_argument("--languages", nargs="+", default=["en", "es"], metavar="LANG")
    p.add_argument("--shortcut", action="append", default=[], metavar="LANG=KEYS")
    p.add_argument("--notify", choices=config.NOTIFY_LEVELS)
    p.add_argument("--sound", choices=("true", "false"))
    p.add_argument("--backend", choices=("local", "openai"))
    p.add_argument("--url")
    p.add_argument("--model")
    p.add_argument("--key-cmd", dest="key_cmd")
    p.add_argument("--max-secs", dest="max_secs", type=int)
    p.add_argument("--default-lang", dest="default_lang")
    p.add_argument("--command", help="what the shortcuts run (default: this program)")
    p.add_argument(
        "--dry-run", action="store_true", help="print the changes, make none"
    )
    return p


def _session() -> None:
    """Refuse a context where per user settings would land nowhere, or on root.

    Without a session bus gsettings writes to a throwaway backend and setup
    would report changes that never happened.
    """
    if os.getuid() == 0:
        msg = "run as the user to set up, not as root"
        raise SetupError(msg)
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    has_bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS") or (
        runtime and Path(runtime, "bus").exists()
    )
    if not has_bus:
        msg = "no session bus: run it from the user's desktop session"
        raise SetupError(msg)


def main(argv: Sequence[str]) -> int:
    """Set this user up. Exit 1 on a step that could not be done."""
    args = parser().parse_args(argv)
    s = Session(dry_run=args.dry_run)
    command = args.command or os.path.realpath(sys.argv[0])
    try:
        _session()
        keys = shortcuts(args.languages, args.shortcut)
        layout = _layout(s, args.layout)
        cfg = _config(s, args, layout)
        # The engine is this program, whatever the shortcuts are told to run.
        if _ibus(s, layout, program=os.path.realpath(sys.argv[0])):
            _sources(s, layout)
        _shortcuts(s, keys, command)
        _units(s, cfg.method)
        _tray_restart(s)
        _ydotool_warning(s, cfg.method)
        _uinput_warning(s, cfg.method)
    except SetupError as err:
        print(f"dictate setup: {err}", file=sys.stderr)
        return 1
    if not s.changes:
        s.out("unchanged")
    return 0
