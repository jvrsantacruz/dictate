"""Put the text into the input that had focus at the press, by one method.

When that cannot be done safely, the text goes to the clipboard and the result
says why. It is never inserted into an input the person did not start in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dictate import keymap
from dictate.desktop import DesktopError

if TYPE_CHECKING:
    from dictate.desktop import Desktop


@dataclass(frozen=True)
class Result:
    """How delivery ended."""

    delivered: bool
    reason: str = ""
    clipboard_lost: bool = False


def _fallback(desktop: Desktop, text: str, reason: str) -> Result:
    try:
        desktop.clipboard_write(text)
    except DesktopError as err:
        return Result(
            delivered=False, reason=f"{reason}, and the clipboard failed: {err}"
        )
    return Result(delivered=False, reason=f"{reason}: the text is on the clipboard")


def deliver(
    text: str, method: str, press: str | None, desktop: Desktop, layout: str
) -> Result:
    """Deliver `text` by `method`, if focus is where it was at the press.

    A desktop that fails midway falls back like any other refusal, so the text
    is never lost to an error.
    """
    try:
        return _deliver(text, method, press, desktop, layout)
    except DesktopError as err:
        return _fallback(desktop, text, str(err))


def _deliver(  # noqa: C901, PLR0911 - one guard per way delivery can be unsafe
    text: str, method: str, press: str | None, desktop: Desktop, layout: str
) -> Result:
    if method == "clipboard":
        desktop.clipboard_write(text)
        return Result(delivered=True)
    if press is None:
        return _fallback(desktop, text, "focus was unknown at the press")
    now = desktop.focus()
    if now is None:
        return _fallback(desktop, text, "focus is unknown now")
    if not now.focused:
        return _fallback(desktop, text, "no input has focus")
    if now.token != press:
        return _fallback(desktop, text, "focus moved since the press")
    if method == "ime":
        if desktop.commit(text, press):
            return Result(delivered=True)
        return _fallback(desktop, text, "focus moved before the text was inserted")
    if method == "type":
        try:
            chords = keymap.plan(text, layout)
        except keymap.UntypableError as err:
            return _fallback(desktop, text, str(err))
        desktop.type_chords(chords)
        return Result(delivered=True)
    if method == "paste":
        saved = desktop.clipboard_read()
        if not desktop.paste(text):
            return _fallback(desktop, text, "focus did not come back after the copy")
        desktop.clipboard_restore(saved)
        return Result(delivered=True, clipboard_lost=saved.lost)
    msg = f"unknown method: {method}"
    raise ValueError(msg)
