"""The streaming worker: transcribes a recording while it is still being made.

The first press starts `dictate stream LANG` beside the recorder. It reads the
WAV as pw-record writes it, cuts it at pauses, and sends each piece as soon as
it is cut. Each piece goes to a file and, with the `ime` method, shows in the
input before anything is typed.

    press 1   recorder ──> audio.wav, growing
              worker   ──> cut at a pause ──> whisper ──> stream.txt, preedit
    press 2   recorder stopped, the worker ended; the whole capture is sent,
              and its text is the one typed

Whisper punctuates each piece as a sentence of its own, so the pieces are
shown, never typed: they stand in only when the whole capture fails.
"""

from __future__ import annotations

import array
import contextlib
import dataclasses
import io
import os
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from dictate import state
from dictate.transcribe import TranscribeError, transcribe_audio

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from dictate.config import Config
    from dictate.desktop import Desktop

RATE = 16000
FRAME = RATE * 30 // 1000  # samples in 30 ms
FRAME_BYTES = FRAME * 2
# A pause long enough to cut at, and the shortest and longest piece. 14 s keeps
# a piece inside the 15 s audio window the dictate-whisper server is started with.
PAUSE_FRAMES = 10
MIN_FRAMES = 2 * RATE // FRAME
MAX_FRAMES = 14 * RATE // FRAME
SPEECH_FRAMES = 5
# Below the floor a frame is quiet whatever the room, and above the ceiling it is
# never quiet: speech from the first frame would otherwise set the noise floor.
# 16 bit samples; the ceiling is about -30 dBFS, so a louder room cuts at 14 s.
QUIET_FLOOR = 300
QUIET_CEILING = 1000
POLL = 0.1
# whisper reads at most 224 tokens of prompt; the tail of the text is enough.
PROMPT_CHARS = 200
# How long the first press's worker waits for pw-record to create the file.
OPEN_WAIT = 5.0
# Past the recording cap, a worker no press came for finishes on its own.
CAP_MARGIN = 10


class Orphan(Exception):  # noqa: N818 - a state, not an error to report
    """Another run owns the files now: this worker leaves without a word."""


class Cutter:
    """Where to cut, from the level of each 30 ms frame.

    A frame is quiet below three times the noise floor, the tenth percentile of
    the levels so far, kept between `QUIET_FLOOR` and `QUIET_CEILING`. A piece
    ends in the middle of a pause of 300 ms once it holds 2 s, or at 14 s
    whatever is said.
    """

    def __init__(self) -> None:
        """Nothing heard yet."""
        self.levels: list[float] = []
        self.start = 0
        self._quiet_run = 0

    def threshold(self) -> float:
        """The level under which a frame counts as quiet."""
        if not self.levels:
            return QUIET_FLOOR
        floor = sorted(self.levels)[len(self.levels) // 10]
        return min(max(floor * 3, QUIET_FLOOR), QUIET_CEILING)

    def feed(self, level: float) -> int | None:
        """Take the next frame's level; the frame index to cut before, or None."""
        quiet = level < self.threshold()
        self.levels.append(level)
        self._quiet_run = self._quiet_run + 1 if quiet else 0
        end = len(self.levels)
        length = end - self.start
        if self._quiet_run == PAUSE_FRAMES and length >= MIN_FRAMES:
            self.start = end - PAUSE_FRAMES // 2
            return self.start
        if length >= MAX_FRAMES:
            self.start = end
            return end
        return None

    def speech(self, first: int, last: int) -> bool:
        """Whether frames `first` to `last` hold speech: 150 ms of loud frames.

        A count, not a share: one short word after a long pause is still speech.
        The server's own voice activity model drops what is not.
        """
        threshold = self.threshold()
        loud = sum(level >= threshold for level in self.levels[first:last])
        return loud >= SPEECH_FRAMES


def level(frame: bytes) -> float:
    """The root mean square of 16 bit little endian samples."""
    samples = array.array("h", frame)
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def data_offset(head: bytes) -> int | None:
    """Where the samples start, after the data chunk header; None if not written yet."""
    at = head.find(b"data", 12)
    return None if at < 0 else at + 8


def to_wav(pcm: bytes) -> bytes:
    """A WAV file around samples in dictate's format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def trimmed(wav: bytes) -> bytes:
    """The capture without its silence before the first and after the last word.

    Whisper given silence at either end invents a closing line, "Gracias.", and
    a hosted backend bills it. 300 ms is kept on each side; a capture with no
    speech, or that cannot be read, is returned as it is.
    """
    offset = data_offset(wav[:4096])
    if offset is None:
        return wav
    # A recorder stopped mid-write can leave half a sample, which no 16 bit
    # frame holds.
    pcm = wav[offset:]
    pcm = pcm[: len(pcm) - len(pcm) % 2]
    cutter = Cutter()
    levels = [level(pcm[i : i + FRAME_BYTES]) for i in range(0, len(pcm), FRAME_BYTES)]
    cutter.levels = levels
    threshold = cutter.threshold()
    loud = [i for i, value in enumerate(levels) if value >= threshold]
    if len(loud) < SPEECH_FRAMES:
        return wav
    first = max(loud[0] - PAUSE_FRAMES, 0)
    last = min(loud[-1] + PAUSE_FRAMES + 1, len(levels))
    return to_wav(pcm[first * FRAME_BYTES : last * FRAME_BYTES])


def prompt(texts: list[str]) -> str:
    """The text said before the next piece, trimmed to what whisper reads."""
    return " ".join(texts)[-PROMPT_CHARS:]


class Worker:
    """One recording's pieces: read, cut, send, write."""

    def __init__(
        self,
        cfg: Config,
        p: state.Paths,
        lang: str,
        environ: Mapping[str, str],
        desktop: Callable[[], Desktop | None],
    ) -> None:
        """Keep the collaborators; the desktop is built only to show text."""
        self._cfg = cfg
        self._p = p
        self._lang = lang
        self._environ = environ
        self._desktop = desktop
        self._shown: Desktop | None = None
        self._token = state.read_press(p)
        self._secret = p.secret.exists()
        self._pid = os.getpid()
        self._deadline = time.monotonic() + cfg.max_secs + CAP_MARGIN
        self.cutter = Cutter()
        self.texts: list[str] = []
        self._pending = bytearray()  # read, not yet a whole frame
        self._pcm = bytearray()  # the frames of the piece being cut
        self._first = 0  # frame index where that piece starts
        self.finishing = False

    def _fell_back(self, _reason: str) -> None:
        """The backend failed once: the rest of this recording goes to the fallback.

        Each piece would otherwise wait the hosted timeout again, and the text
        shown would fall further behind the voice.
        """
        self._cfg = dataclasses.replace(
            self._cfg, backend="local", url=self._cfg.fallback_url
        )

    def _mine(self) -> bool:
        """Whether the pidfile still names this worker, not a later run's."""
        try:
            return int(self._p.stream_pid.read_text(encoding="utf-8")) == self._pid
        except (OSError, ValueError):
            return False

    def _show(self) -> None:
        """The text so far, as preedit, with the `ime` method only."""
        if self._cfg.method != "ime" or self._token is None or self._secret:
            return
        with contextlib.suppress(Exception):
            if self._shown is None:
                self._shown = self._desktop()
            if self._shown is not None:
                self._shown.show(" ".join(self.texts), self._token)

    def send(self, pcm: bytes, last: int, *, final: bool) -> None:
        """Transcribe one piece, frames `self._first` to `last`.

        A piece with no speech is dropped, except the last one when nothing has
        been said yet: the server is the judge of a recording too quiet to cut.
        """
        first, self._first = self._first, last
        if not self.cutter.speech(first, last) and not (final and not self.texts):
            return
        text = transcribe_audio(
            self._cfg, self._lang, to_wav(pcm), prompt(self.texts), self._fell_back
        )
        if not self._mine():
            raise Orphan
        if not text or (self.texts and text == self.texts[-1]):
            # Noise sent with the text before as prompt comes back as that text.
            return
        self.texts.append(text)
        with self._p.stream_text.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
        self._show()

    def take(self, data: bytes) -> None:
        """Add samples; send every piece they complete."""
        self._pending += data
        while len(self._pending) >= FRAME_BYTES:
            frame = bytes(self._pending[:FRAME_BYTES])
            del self._pending[:FRAME_BYTES]
            self._pcm += frame
            cut = self.cutter.feed(level(frame))
            if cut is not None:
                size = (cut - self._first) * FRAME_BYTES
                piece = bytes(self._pcm[:size])
                del self._pcm[:size]
                self.send(piece, cut, final=False)

    def finish(self) -> None:
        """Send what is left after the recorder stopped."""
        rest = bytes(self._pcm + self._pending)
        self._pcm.clear()
        self._pending.clear()
        self.send(rest, len(self.cutter.levels), final=True)

    def run(self) -> int:
        """Follow the capture until told to finish; 0 when every piece went through."""
        try:
            self._follow()
        except Orphan:
            return 1
        except (TranscribeError, OSError, wave.Error):
            # The second press transcribes the whole capture anyway.
            return 1
        return 0

    def _follow(self) -> None:
        deadline = time.monotonic() + OPEN_WAIT
        offset = None
        while offset is None:
            with contextlib.suppress(FileNotFoundError), self._p.wav.open("rb") as f:
                offset = data_offset(f.read(4096))
            if offset is None:
                if self.finishing or time.monotonic() > deadline:
                    msg = "no capture to follow"
                    raise OSError(msg)
                time.sleep(POLL)
        with self._p.wav.open("rb") as f:
            f.seek(offset)
            while True:
                # Read after the flag: the recorder is stopped before the
                # worker is told, so this read reaches the end of the capture.
                last = self.finishing
                self.take(f.read())
                if last:
                    self.finish()
                    return
                if os.fstat(f.fileno()).st_nlink == 0 or not self._mine():
                    # The capture was deleted or another run took over: a
                    # cancel, or a press that did not know of this worker.
                    raise Orphan
                if time.monotonic() > self._deadline:
                    # The cap ended the recording and no press came: finish, so
                    # the next press finds the text rather than a worker polling.
                    self.finishing = True
                time.sleep(POLL)


def _ours(pid: int) -> bool:
    """Whether `pid` is still a streaming worker, not a pid handed out again."""
    try:
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    return b"stream" in cmdline


def running(p: state.Paths) -> int | None:
    """The live worker's pid, or None."""
    try:
        pid = int(p.stream_pid.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return pid if _ours(pid) else None


def start(p: state.Paths, lang: str) -> int:
    """Start the worker beside the recorder, in its own session as the recorder is."""
    cleanup(p)
    program = Path(sys.argv[0]).resolve()
    # The zipapp runs itself; `python -m dictate` runs the module again.
    command = (
        [sys.executable, "-m", "dictate"]
        if program.name == "__main__.py"
        else [sys.executable, str(program)]
    )
    proc = subprocess.Popen(
        [*command, "stream", lang],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    p.stream_pid.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def text_so_far(p: state.Paths) -> str:
    """The pieces transcribed until now, joined; empty when there are none."""
    try:
        return " ".join(p.stream_text.read_text(encoding="utf-8").split())
    except OSError:
        return ""


def stop(p: state.Paths) -> None:
    """End the worker without its text, for cancel and a worker that hangs."""
    pid = running(p)
    if pid is not None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)


def cleanup(p: state.Paths) -> None:
    """End the worker and delete its files: its text is a voice's words."""
    stop(p)
    for f in (p.stream_pid, p.stream_text):
        f.unlink(missing_ok=True)


def main(
    cfg: Config,
    p: state.Paths,
    lang: str,
    environ: Mapping[str, str],
    desktop: Callable[[], Desktop | None],
) -> int:
    """`dictate stream LANG`: runs until the press ends it, or the cap does."""
    return Worker(cfg, p, lang, environ, desktop).run()
