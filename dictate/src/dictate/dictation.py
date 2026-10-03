"""One press: start a recording, or stop it, transcribe and deliver.

The desktop is passed in, so nothing here knows which one it runs on. The
recorder, the transcriber and the state files are used directly: each is one
module, and the press flow is covered by the headless tier.
"""

from __future__ import annotations

import contextlib
import sys
import time
from typing import TYPE_CHECKING

from dictate import delivery, feedback, recorder, state
from dictate.desktop import DesktopError
from dictate.feedback import FAILURE, START_CUE, STATE, STOP_CUE
from dictate.transcribe import TranscribeError, transcribe

if TYPE_CHECKING:
    from collections.abc import Callable

    from dictate.config import Config
    from dictate.desktop import Desktop
    from dictate.feedback import Feedback


class Failure(Exception):  # noqa: N818 - it is what the person is told
    """Something the person has to be told about."""


class Dictation:
    """The steps of a press, against the files of `state.Paths`."""

    def __init__(
        self,
        cfg: Config,
        paths: state.Paths,
        fb: Feedback,
        desktop: Callable[[], Desktop | None],
    ) -> None:
        """Keep the collaborators. The desktop is built only when needed."""
        self._cfg = cfg
        self._p = paths
        self._fb = fb
        self._desktop = desktop

    def _publish(self, phase: str | None, lang: str = "") -> None:
        state.write_state(self._p, phase, int(time.time()), lang)
        feedback.refresh_tmux()

    def _need_desktop(self) -> Desktop:
        try:
            desktop = self._desktop()
        except DesktopError as err:
            raise Failure(str(err)) from err
        if desktop is None:
            msg = "no desktop adapter for this session"
            raise Failure(msg)
        return desktop

    def _fail(self, err: Failure) -> int:
        self._publish(None)
        self._fb.notify(FAILURE, f"dictate: {err}", 4000)
        print(f"dictate: {err}", file=sys.stderr)
        return 1

    def toggle(self, lang: str) -> int:
        """Start when idle, stop when recording.

        A recording the cap already ended counts as recording: its audio is
        waiting, and this press is the one meant to stop it.
        """
        try:
            if recorder.running(self._p) is not None or self._capped():
                self._stop()
            else:
                self._start(lang)
        except Failure as err:
            return self._fail(err)
        except Exception as err:  # noqa: BLE001 - any error must leave the state idle
            return self._fail(Failure(f"unexpected error: {err!r}"))
        return 0

    def _capped(self) -> bool:
        """The recorder is gone, the state still says capturing, audio is there."""
        wav = self._p.wav
        return (
            state.read_phase(self._p) == state.CAPTURING
            and wav.is_file()
            and wav.stat().st_size > 0
        )

    def cancel(self) -> int:
        """Stop and discard a recording, including one the cap already ended."""
        try:
            pid = recorder.running(self._p)
            if pid is None and not self._capped():
                return self._fail(Failure("not recording"))
            if pid is not None:
                recorder.stop(self._p, pid)
        except Exception as err:  # noqa: BLE001 - any error must leave the state idle
            self._p.wav.unlink(missing_ok=True)
            return self._fail(Failure(f"unexpected error: {err!r}"))
        self._p.wav.unlink(missing_ok=True)
        state.write_press(self._p, None)
        self._fb.cue(STOP_CUE, wait=False)
        self._publish(None)
        self._fb.notify(STATE, "cancelled")
        return 0

    def _rescue(self, text: str) -> None:
        with contextlib.suppress(Exception):
            desktop = self._desktop()
            if desktop is not None:
                desktop.clipboard_write(text)

    def _start(self, lang: str) -> None:
        desktop = self._need_desktop()
        # Taken before anything else happens: this is the input the text is for.
        now = desktop.focus() if self._cfg.method != "clipboard" else None
        state.write_press(self._p, now.token if now else None)
        self._fb.cue(START_CUE, wait=True)
        pid = recorder.start(self._p, self._cfg.max_secs)
        try:
            self._publish(state.CAPTURING, lang)
        except Exception:
            # Never a microphone running while nothing says so.
            recorder.stop(self._p, pid)
            self._p.wav.unlink(missing_ok=True)
            raise
        self._fb.notify(STATE, f"recording ({lang})")

    def _stop(self) -> None:
        lang = state.recording_lang(self._p, self._cfg.default_lang)
        pid = recorder.running(self._p)
        if pid is not None:
            recorder.stop(self._p, pid)
        self._fb.cue(STOP_CUE, wait=False)
        press = state.read_press(self._p)
        state.write_press(self._p, None)
        try:
            if not self._p.wav.is_file() or self._p.wav.stat().st_size == 0:
                msg = "no audio captured"
                raise Failure(msg)
            self._publish(state.TRANSCRIBING, lang)
            self._fb.notify(STATE, "transcribing")
            try:
                text = transcribe(self._cfg, lang, self._p.wav)
            except TranscribeError as err:
                raise Failure(str(err)) from err
        finally:
            # A recording of a voice: gone as soon as it has been read.
            self._p.wav.unlink(missing_ok=True)
        if not text:
            msg = "empty transcript"
            raise Failure(msg)
        try:
            result = delivery.deliver(
                text, self._cfg.method, press, self._need_desktop(), self._cfg.layout
            )
        except Exception:
            # The capture is gone, so the text is the only copy left: kept on
            # the clipboard if anything still can, before the failure is told.
            self._rescue(text)
            raise
        self._publish(None)
        if not result.delivered:
            raise Failure(result.reason)
        if result.clipboard_lost:
            self._fb.notify(
                FAILURE, "dictate: the clipboard held no text and was not restored"
            )
        if self._cfg.method == "clipboard":
            self._fb.notify(STATE, f"copied: {text[:60]}")
