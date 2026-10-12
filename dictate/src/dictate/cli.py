"""Command line. Wiring only: no rules live here.

dictate [LANG]          toggle a recording in LANG
dictate cancel          stop and discard a recording
dictate retry           transcribe the recording a failure kept, to the clipboard
dictate status          print recording or idle
dictate log [N]         print the last N dictated texts, 20 by default
dictate stream LANG     the streaming worker; the first press starts it
dictate engine --ibus   the IBus engine; IBus starts it
dictate engines         the engine's description, on the user's layout; IBus
                        runs it
dictate component PATH [VERSION]  print the IBus component file, PATH the program
dictate setup ...       set up this user: dictate setup --help
"""

from __future__ import annotations

import logging
import os
import sys

from dictate import config, desktop, recorder, state, stream, textlog
from dictate.dictation import Dictation
from dictate.feedback import FAILURE, Feedback

USAGE = "usage: dictate [{langs}|status|cancel|retry|log [N]]"


def _desktop(cfg: config.Config) -> desktop.Desktop | None:
    if desktop.select(os.environ) != desktop.GNOME_WAYLAND:
        return None
    from dictate.gnome.adapter import build  # noqa: PLC0415 - gi only on demand

    return build(cfg.keys)


def _engines() -> int:
    """Describe the engine to IBus, on the user's layout.

    IBus runs this while it builds its registry, so it must answer whatever
    the config holds: a layout that is not an XKB id, or no config at all,
    gives the default rather than an error IBus would swallow.
    """
    from dictate.gnome.component import engines, valid_layout  # noqa: PLC0415

    layout = config.raw().get("DICTATE_LAYOUT", config.Config.layout)
    if not valid_layout(layout):
        layout = config.Config.layout
    print(engines(layout), end="")
    return 0


def _unlocked(
    command: str, args: list[str], cfg: config.Config, paths: state.Paths
) -> int:
    """The commands that never take the press lock.

    `stream` is started by the first press, which holds the lock while it runs.
    """
    if command == "stream":
        lang = args[0] if args else cfg.default_lang
        return stream.main(cfg, paths, lang, os.environ, lambda: _desktop(cfg))
    count = args[0] if args else "20"
    if not count.isdigit():
        print(USAGE.format(langs="|".join(cfg.languages)), file=sys.stderr)
        return 2
    for entry in textlog.tail(os.environ, int(count)):
        print(entry)
    return 0


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911 - one exit per command
    """Entry point."""
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else None
    if command == "engine":
        # IBus discards the engine's output, so a debug log goes to a file.
        debug = os.environ.get("DICTATE_ENGINE_LOG")
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            filename=debug or None,
            format="%(relativeCreated)d %(message)s",
        )
        from dictate.gnome.engine import run  # noqa: PLC0415 - gi only on demand

        return run()
    if command == "component":
        from dictate.gnome.component import xml  # noqa: PLC0415

        program = args[1] if len(args) > 1 else "/usr/bin/dictate"
        version = args[2] if len(args) > 2 else "0"  # noqa: PLR2004
        print(xml(program, version), end="")
        return 0
    if command == "engines":
        return _engines()
    if command == "setup":
        from dictate.gnome.setup import main as setup  # noqa: PLC0415

        return setup(args[1:])

    try:
        cfg = config.load()
    except config.ConfigError as err:
        Feedback("failures", sound=False).notify(FAILURE, f"dictate: {err}", 4000)
        print(f"dictate: {err}", file=sys.stderr)
        return 2
    paths = state.paths(os.environ)
    if command == "status":
        print("recording" if recorder.running(paths) else "idle")
        return 0
    if command in ("log", "stream"):
        return _unlocked(command, args[1:], cfg, paths)
    lang = command or cfg.default_lang
    if command not in ("cancel", "retry") and lang not in cfg.languages:
        # A typo in the shortcut would otherwise reach whisper mid-transcription.
        print(USAGE.format(langs="|".join(cfg.languages)), file=sys.stderr)
        return 2

    # One press at a time; a press that finds the lock taken is dropped.
    held = state.lock(paths)
    if held is None:
        return 0
    try:
        run = Dictation(
            cfg, paths, Feedback(cfg.notify, sound=cfg.sound), lambda: _desktop(cfg)
        )
        actions = {"cancel": run.cancel, "retry": run.retry}
        return actions.get(command or "", lambda: run.toggle(lang))()
    finally:
        os.close(held)
