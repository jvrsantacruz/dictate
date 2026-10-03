"""What the tray shows for a given state.

Separate from the GTK adapter so the rules can be tested without a display.
"""

from __future__ import annotations

from dataclasses import dataclass

from dictate_indicator.state import CAPTURING, TRANSCRIBING, State

ICONS = {CAPTURING: "dictate-recording", TRANSCRIBING: "dictate-transcribing"}
# The other half of the capturing blink: a red ring rather than no icon, so the
# tray slot keeps its width and the panel does not reflow every second.
CAPTURING_DIM = "dictate-recording-dim"

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class Marker:
    """One rendering of the state: an icon name and the text beside it."""

    visible: bool
    icon: str = ""
    label: str = ""


HIDDEN = Marker(visible=False)


def render(state: State, now: float) -> Marker:
    """Build the marker for this state at this moment.

    Both working phases count up, so a recording left running and a
    transcription that has stalled are both obvious rather than merely
    indicated. Capturing also blinks, on odd seconds, because it is the phase
    where a marker left unnoticed records the room.
    """
    if not state.active:
        return HIDDEN
    seconds = state.elapsed(now)
    minutes, rest = divmod(seconds, SECONDS_PER_MINUTE)
    label = f"{state.lang.upper()} {minutes}:{rest:02d}".strip()
    icon = ICONS[state.phase]
    if state.phase == CAPTURING and seconds % 2:
        icon = CAPTURING_DIM
    return Marker(visible=True, icon=icon, label=label)
