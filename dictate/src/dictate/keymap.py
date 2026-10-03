"""Text to keystrokes, for the `type` method.

Keystrokes are kernel key codes, so what they produce depends on the layout
the desktop applies. `us+intl` turns ' " ` ~ ^ into dead keys: they compose
with the next key, and a literal one is the dead key then space. A character
this table cannot produce is refused, never approximated: the method falls
back to the clipboard instead.
"""

from __future__ import annotations

from dataclasses import dataclass

SHIFT = 42
ALTGR = 100
SPACE = 57


@dataclass(frozen=True)
class Chord:
    """One key, pressed while `mods` are held."""

    code: int
    mods: tuple[int, ...] = ()


class UntypableError(ValueError):
    """A character the layout cannot produce."""

    def __init__(self, char: str) -> None:
        """Keep the character, for the failure message."""
        super().__init__(f"cannot type {char!r}")
        self.char = char


_LETTERS = "qwertyuiop", "asdfghjkl", "zxcvbnm"
_ROW_START = 16, 30, 44

# Unshifted and shifted symbol on each US key.
_SYMBOLS = {
    2: "1!", 3: "2@", 4: "3#", 5: "4$", 6: "5%", 7: "6^", 8: "7&", 9: "8*",
    10: "9(", 11: "0)", 12: "-_", 13: "=+", 26: "[{", 27: "]}", 39: ";:",
    40: "'\"", 41: "`~", 43: "\\|", 51: ",<", 52: ".>", 53: "/?",
}  # fmt: skip


def _us() -> dict[str, tuple[Chord, ...]]:
    table: dict[str, tuple[Chord, ...]] = {" ": (Chord(SPACE),)}
    for row, start in zip(_LETTERS, _ROW_START, strict=True):
        for offset, letter in enumerate(row):
            table[letter] = (Chord(start + offset),)
            table[letter.upper()] = (Chord(start + offset, (SHIFT,)),)
    for code, (plain, shifted) in _SYMBOLS.items():
        table[plain] = (Chord(code),)
        table[shifted] = (Chord(code, (SHIFT,)),)
    return table


def _us_intl() -> dict[str, tuple[Chord, ...]]:
    us = _us()
    table = dict(us)
    dead = {
        "'": us["'"][0],
        '"': us['"'][0],
        "`": us["`"][0],
        "~": us["~"][0],
        "^": us["^"][0],
    }
    for char, key in dead.items():
        table[char] = (key, Chord(SPACE))
    composed = {
        "'": "aá eé ií oó uú AÁ EÉ IÍ OÓ UÚ",
        '"': "uü UÜ iï IÏ",
        "`": "aà eè oò AÀ EÈ OÒ",
        "~": "nñ NÑ",
    }
    for deadchar, pairs in composed.items():
        for base, result in pairs.split():
            table[result] = (dead[deadchar], *us[base])
    table["¿"] = (Chord(53, (ALTGR,)),)
    table["¡"] = (Chord(2, (ALTGR,)),)
    table["ç"] = (Chord(51, (ALTGR,)),)
    table["Ç"] = (Chord(51, (ALTGR, SHIFT)),)
    return table


LAYOUTS = {"us": _us(), "us+intl": _us_intl()}


def plan(text: str, layout: str) -> list[Chord]:
    """Every chord that types `text` on `layout`, or `UntypableError`."""
    try:
        table = LAYOUTS[layout]
    except KeyError as err:
        raise UntypableError(text[:1]) from err
    chords: list[Chord] = []
    for char in text:
        try:
            chords.extend(table[char])
        except KeyError as err:
            raise UntypableError(char) from err
    return chords
