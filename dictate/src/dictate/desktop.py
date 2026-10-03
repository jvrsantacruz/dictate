"""The port every delivery method talks to, and the choice of its adapter.

The methods know nothing of GNOME; an adapter knows nothing of methods. One
adapter exists, for GNOME on Wayland. A session no adapter covers gets none,
and delivery then fails with a notification rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from dictate.keymap import Chord

GNOME_WAYLAND = "gnome-wayland"


class DesktopError(RuntimeError):
    """The desktop refused or failed an operation: a tool failed or timed out."""


@dataclass(frozen=True)
class Focus:
    """Which input holds focus, as far as the desktop says.

    `token` changes on every focus change, and two tokens are equal only when
    focus never moved between them.
    """

    token: str
    focused: bool


@dataclass(frozen=True)
class Clip:
    """What the clipboard held before delivery.

    `text` is None when it held no text. `lost` is true when it held something
    that cannot be put back, such as an image or files.
    """

    text: str | None = None
    lost: bool = False


class Desktop(Protocol):
    """What delivery needs from a desktop.

    Every method but `focus` and `commit` raises `DesktopError` when it fails;
    those two answer None and False instead, since both are questions.
    """

    def focus(self) -> Focus | None:
        """The current focus, or None when the desktop cannot tell."""
        ...

    def commit(self, text: str, token: str) -> bool:
        """Insert the text, only if focus is still `token`."""
        ...

    def type_chords(self, chords: Sequence[Chord]) -> None:
        """Press keys."""
        ...

    def clipboard_read(self) -> Clip:
        """What the clipboard holds now."""
        ...

    def clipboard_write(self, text: str) -> None:
        """Put text on the clipboard, to stay."""
        ...

    def clipboard_restore(self, clip: Clip) -> None:
        """Put back what `clipboard_read` found."""
        ...

    def paste(self, text: str) -> bool:
        """Copy and press the paste key the focused input takes.

        The input is the one the last `focus()` reported, so delivery asks
        first. False when it could not press the key. The clipboard holds
        `text` after.
        """
        ...


def select(environ: Mapping[str, str]) -> str | None:
    """The adapter for this session, or None when none covers it."""
    desktops = environ.get("XDG_CURRENT_DESKTOP", "").split(":")
    if environ.get("XDG_SESSION_TYPE") == "wayland" and "GNOME" in desktops:
        return GNOME_WAYLAND
    return None
