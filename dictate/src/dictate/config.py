"""Settings, from three places, each over the one before.

    /etc/dictate/config        the machine's defaults, if an admin wrote one
    ~/.config/dictate/config   the user's, written by `dictate setup`
    DICTATE_* in the environment, so `DICTATE_METHOD=type dictate en` changes
    one run without touching either file

Both files are `KEY="value"` lines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping

METHODS = ("paste", "type", "ime", "clipboard")
NOTIFY_LEVELS = ("all", "failures", "none")
KEY_SENDERS = ("ydotool", "remote-desktop")


class ConfigError(ValueError):
    """A setting holds a value nothing here can act on."""


@dataclass(frozen=True)
class Config:
    """Every setting, with its default."""

    backend: str = "local"
    url: str = "http://127.0.0.1:8081"
    model: str = "whisper-1"
    key_cmd: str = ""
    method: str = "ime"
    max_secs: int = 120
    default_lang: str = "en"
    languages: tuple[str, ...] = ("en", "es")
    notify: str = "failures"
    sound: bool = False
    # How the GNOME adapter sends keystrokes. `remote-desktop` is the headless
    # test tier's: ydotool would reach the real desktop.
    keys: str = "ydotool"
    # The XKB layout the engine types with, and the `type` method plans for.
    layout: str = "us+intl"


def parse_file(text: str) -> dict[str, str]:
    """Read `KEY="value"` lines. Comments and blank lines are skipped."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":  # noqa: PLR2004
            value = value[1:-1]
        values[key.strip()] = value
    return values


SYSTEM_PATH = Path("/etc/dictate/config")


def default_path(environ: Mapping[str, str]) -> Path:
    """The user's file, which `dictate setup` writes."""
    base = environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "dictate" / "config"


LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _check_url(url: str) -> None:
    """Allow http or https only, and https off this machine: the audio is a voice."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        msg = f"DICTATE_URL must be an http or https URL: {url}"
        raise ConfigError(msg)
    if parts.scheme == "http" and parts.hostname not in LOOPBACK:
        msg = f"DICTATE_URL must use https off this machine: {url}"
        raise ConfigError(msg)


def build(values: Mapping[str, str]) -> Config:
    """Turn raw values into a `Config`, refusing a method or sender it cannot run.

    An unknown notification level reads as failures, the one that still says
    what went wrong.
    """
    d = Config()
    method = values.get("DICTATE_METHOD", d.method)
    if method not in METHODS:
        msg = f"unknown method: {method}"
        raise ConfigError(msg)
    keys = values.get("DICTATE_KEYS", d.keys)
    if keys not in KEY_SENDERS:
        msg = f"unknown key sender: {keys}"
        raise ConfigError(msg)
    notify = values.get("DICTATE_NOTIFY", d.notify)
    try:
        max_secs = int(values.get("DICTATE_MAX_SECS", d.max_secs))
    except ValueError as err:
        msg = f"DICTATE_MAX_SECS is not a number: {values['DICTATE_MAX_SECS']}"
        raise ConfigError(msg) from err
    url = values.get("DICTATE_URL", d.url)
    _check_url(url)
    if max_secs <= 0:
        # timeout 0 means no limit, which is what the cap is there to prevent.
        msg = f"DICTATE_MAX_SECS must be above 0, not {max_secs}"
        raise ConfigError(msg)
    return Config(
        backend=values.get("DICTATE_BACKEND", d.backend),
        url=url,
        model=values.get("DICTATE_MODEL", d.model),
        key_cmd=values.get("DICTATE_KEY_CMD", d.key_cmd),
        method=method,
        max_secs=max_secs,
        default_lang=values.get("DICTATE_LANG", d.default_lang),
        languages=tuple(values.get("DICTATE_LANGUAGES", " ".join(d.languages)).split()),
        notify=notify if notify in NOTIFY_LEVELS else "failures",
        sound=values.get("DICTATE_SOUND", "false") == "true",
        keys=keys,
        layout=values.get("DICTATE_LAYOUT", d.layout),
    )


def _read(path: Path) -> dict[str, str]:
    try:
        return parse_file(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}


def system_path(environ: Mapping[str, str]) -> Path:
    """The machine's file. DICTATE_SYSTEM_CONFIG moves it, for tests."""
    return Path(environ.get("DICTATE_SYSTEM_CONFIG") or SYSTEM_PATH)


def raw(
    environ: Mapping[str, str] | None = None, system: Path | None = None
) -> dict[str, str]:
    """The machine's values, the user's over them, the environment's over both."""
    env = os.environ if environ is None else environ
    values = _read(system or system_path(env))
    values.update(_read(default_path(env)))
    values.update({k: v for k, v in env.items() if k.startswith("DICTATE_")})
    return values


def load(
    environ: Mapping[str, str] | None = None, system: Path | None = None
) -> Config:
    """Read the files, then let the environment override them."""
    return build(raw(environ, system))
