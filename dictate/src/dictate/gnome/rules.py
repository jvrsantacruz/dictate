"""Per application rules of the GNOME adapter, keyed on the input purpose."""

from __future__ import annotations

from dictate.keymap import SHIFT, Chord

# What an input says it is, as IBus numbers it.
PURPOSE_FREE_FORM = 0
PURPOSE_TERMINAL = 10

CTRL = 29
V = 47
# What wl-paste may offer that is text, in the order it is asked for.
TEXT_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING", "TEXT")


def paste_chord(purpose: int) -> Chord:
    """The paste key for this kind of input. A terminal takes ctrl+shift+v."""
    if purpose == PURPOSE_TERMINAL:
        return Chord(V, (CTRL, SHIFT))
    return Chord(V, (CTRL,))


def text_type(types: list[str]) -> str | None:
    """The text type to read from what the clipboard offers, if any."""
    return next((mime for mime in TEXT_TYPES if mime in types), None)
