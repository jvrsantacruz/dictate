"""Command line. Wiring only: no rules live here.

`argparse` rather than `click`, because click would be the single third party
dependency, and a dependency is what ends the one file install.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from dictate_indicator import assets, state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        prog="dictate-indicator",
        description="Show the dictation state as a tray icon.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=state.default_path(),
        help="the file `dictate` writes (default: %(default)s)",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=assets.default_dir(),
        help="where the packaged icons are unpacked (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="log every state change",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Logs to stderr, which is the journal under systemd."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    assets.install(args.icon_dir)
    # Imported here rather than at the top: GTK costs 150 ms to load and
    # `--help` should not pay it.
    from dictate_indicator.indicator import run  # noqa: PLC0415

    return run(args.state_file, args.icon_dir, time.time)
