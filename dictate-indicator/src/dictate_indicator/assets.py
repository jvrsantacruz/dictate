"""The icons, unpacked where the tray can find them.

AppIndicator takes a directory and an icon name, and a file inside a zipapp has
no path on disk, so the SVGs are written out on start. They are full colour on
purpose: a `-symbolic` icon is recoloured to the panel foreground by contract
and could never be red.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

NAMES = ("dictate-recording", "dictate-recording-dim", "dictate-transcribing")


def default_dir() -> Path:
    """Cache, not data: every file here is reproducible from the artifact."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "dictate-indicator" / "icons"


def install(target: Path) -> Path:
    """Write the packaged icons into `target` and return it.

    Only when the bytes differ, so a new version takes effect while a restart
    leaves the disk alone.
    """
    target.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        data = resources.files(__package__).joinpath(f"icons/{name}.svg").read_bytes()
        path = target / f"{name}.svg"
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    return target
