"""What the engine knows about focus, kept apart from IBus so it can be tested.

On GNOME on Wayland every application reaches IBus through one input context,
GNOME Shell's, so the engine cannot name an input. What it can tell is whether
focus moved: every focus change bumps a counter, and the counter is prefixed
with a value fresh for each run of the engine, so a restart never makes an old
token look current.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from dictate.gnome.rules import PURPOSE_FREE_FORM


@dataclass
class Tracker:
    """Focus as the engine instances report it."""

    run: str = field(default_factory=lambda: secrets.token_hex(4))
    changes: int = 0
    holder: int | None = None
    purposes: dict[int, int] = field(default_factory=dict)

    def focus_in(self, engine: int) -> None:
        """An engine instance gained focus."""
        self.changes += 1
        self.holder = engine

    def focus_out(self, engine: int) -> None:
        """An engine instance lost focus."""
        self.changes += 1
        if self.holder == engine:
            self.holder = None

    def purpose(self, engine: int, purpose: int) -> None:
        """An input said what it is: free text, a terminal, a password."""
        self.purposes[engine] = purpose

    def disable(self, engine: int) -> None:
        """Another input source was chosen: focus stops being seen.

        The input's purpose is kept: IBus does not repeat an unchanged one when
        the engine comes back, and a terminal must still get its paste key.
        """
        self.changes += 1
        if self.holder == engine:
            self.holder = None

    def forget(self, engine: int) -> None:
        """An engine instance went away."""
        self.purposes.pop(engine, None)
        if self.holder == engine:
            self.changes += 1
            self.holder = None

    @property
    def token(self) -> str:
        """Equal across two reads only if focus never moved between them."""
        return f"{self.run}:{self.changes}"

    def snapshot(self) -> tuple[str, bool, int]:
        """The token, whether an engine holds focus, and its input's purpose."""
        purpose = PURPOSE_FREE_FORM
        if self.holder is not None:
            purpose = self.purposes.get(self.holder, PURPOSE_FREE_FORM)
        return self.token, self.holder is not None, purpose

    def may_commit(self, token: str) -> int | None:
        """The engine to commit through, if focus is still `token`."""
        if token != self.token:
            return None
        return self.holder
