"""The streaming worker: where it cuts, and what it sends and keeps."""

import array
import io
import os
import wave
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to, is_, none

from dictate import config, state, stream

LOUD = 3000
SILENT = 0


def _frames(seconds: float, amplitude: int) -> bytes:
    """A square wave, loud enough to count as speech, or silence."""
    count = int(seconds * stream.RATE)
    samples = array.array("h", [(-1) ** i * amplitude for i in range(count)])
    return samples.tobytes()


def _wav(pcm: bytes) -> bytes:
    return stream.to_wav(pcm)


def _paths(tmp_path: Path) -> state.Paths:
    return state.paths({"XDG_RUNTIME_DIR": str(tmp_path)})


class _Sent:
    """Stands in for the server: records each piece and answers its length."""

    def __init__(self) -> None:
        self.pieces: list[tuple[float, str]] = []

    def __call__(self, _cfg: object, _lang: str, audio: bytes, prompt: str = "") -> str:
        with wave.open(io.BytesIO(audio)) as w:
            seconds = w.getnframes() / w.getframerate()
        self.pieces.append((round(seconds, 1), prompt))
        return f"piece{len(self.pieces)}"


def _worker(
    tmp_path: Path, monkeypatch: object, **cfg: object
) -> tuple[stream.Worker, _Sent]:
    sent = _Sent()
    monkeypatch.setattr(stream, "transcribe_audio", sent)  # type: ignore[attr-defined]
    p = _paths(tmp_path)
    # The run that owns the files is this process, as the worker sees itself.
    p.stream_pid.write_text(str(os.getpid()))
    env = {"XDG_STATE_HOME": str(tmp_path / "state")}
    worker = stream.Worker(config.Config(**cfg), p, "es", env, lambda: None)
    return worker, sent


def test_the_level_of_silence_is_zero() -> None:
    assert_that(stream.level(_frames(0.03, SILENT)), is_(equal_to(0.0)))


def test_the_samples_start_after_the_data_header() -> None:
    assert_that(stream.data_offset(_wav(b"\0\0" * 10)), is_(equal_to(44)))


def test_no_data_header_yet_is_none() -> None:
    assert_that(stream.data_offset(b"RIFF\0\0\0\0WAVEfmt "), is_(none()))


def test_a_pause_after_two_seconds_cuts_in_its_middle() -> None:
    cutter = stream.Cutter()
    cuts = [cutter.feed(LOUD) for _ in range(stream.MIN_FRAMES)]
    cuts += [cutter.feed(SILENT) for _ in range(stream.PAUSE_FRAMES)]
    expected = stream.MIN_FRAMES + stream.PAUSE_FRAMES - stream.PAUSE_FRAMES // 2
    assert_that([c for c in cuts if c is not None], is_(equal_to([expected])))


def test_a_pause_in_the_first_two_seconds_does_not_cut() -> None:
    cutter = stream.Cutter()
    cuts = [cutter.feed(LOUD) for _ in range(10)]
    cuts += [cutter.feed(SILENT) for _ in range(stream.PAUSE_FRAMES)]
    assert_that([c for c in cuts if c is not None], is_(equal_to([])))


def test_speech_with_no_pause_is_cut_at_fourteen_seconds() -> None:
    cutter = stream.Cutter()
    cuts = [cutter.feed(LOUD) for _ in range(stream.MAX_FRAMES * 2)]
    found = [c for c in cuts if c is not None]
    assert_that(found, is_(equal_to([stream.MAX_FRAMES, stream.MAX_FRAMES * 2])))


def test_the_prompt_is_the_tail_of_the_text() -> None:
    text = stream.prompt(["a" * 150, "b" * 150])
    assert_that(len(text), is_(equal_to(stream.PROMPT_CHARS)))
    assert_that(text.endswith("b"), is_(True))


def test_pieces_are_sent_at_pauses_with_the_text_before(
    tmp_path: Path, monkeypatch: object
) -> None:
    worker, sent = _worker(tmp_path, monkeypatch)
    worker.take(_frames(3, LOUD) + _frames(0.5, SILENT) + _frames(3, LOUD))
    worker.finish()
    assert_that(len(sent.pieces), is_(equal_to(2)))
    assert_that(sent.pieces[0][1], is_(equal_to("")))
    assert_that(sent.pieces[1][1], is_(equal_to("piece1")))
    p = _paths(tmp_path)
    assert_that(p.stream_text.read_text(), is_(equal_to("piece1\npiece2\n")))


def test_a_silent_piece_is_not_sent(tmp_path: Path, monkeypatch: object) -> None:
    worker, sent = _worker(tmp_path, monkeypatch)
    worker.take(_frames(3, LOUD) + _frames(3, SILENT))
    worker.finish()
    assert_that(len(sent.pieces), is_(equal_to(1)))


def test_a_silent_recording_is_still_sent_once(
    tmp_path: Path, monkeypatch: object
) -> None:
    worker, sent = _worker(tmp_path, monkeypatch)
    worker.take(_frames(1, SILENT))
    worker.finish()
    assert_that(len(sent.pieces), is_(equal_to(1)))


def test_pieces_are_not_logged(tmp_path: Path, monkeypatch: object) -> None:
    worker, _ = _worker(tmp_path, monkeypatch, log=True)
    worker.take(_frames(3, LOUD))
    worker.finish()
    assert_that((tmp_path / "state" / "dictate" / "log").exists(), is_(False))


def test_the_worker_follows_a_growing_capture(
    tmp_path: Path, monkeypatch: object
) -> None:
    worker, sent = _worker(tmp_path, monkeypatch)
    p = _paths(tmp_path)
    # The header pw-record writes while recording: a data size of 0.
    p.wav.write_bytes(_wav(b"")[:40] + b"\0\0\0\0" + _frames(3, LOUD))
    worker.finishing = True
    assert_that(worker.run(), is_(equal_to(0)))
    assert_that(len(sent.pieces), is_(equal_to(1)))
    assert_that(stream.text_so_far(p), is_(equal_to("piece1")))


def test_a_deleted_capture_ends_the_worker(tmp_path: Path, monkeypatch: object) -> None:
    worker, _ = _worker(tmp_path, monkeypatch)
    p = _paths(tmp_path)
    p.wav.write_bytes(_wav(_frames(1, LOUD)))
    monkeypatch.setattr(stream, "POLL", 0.01)  # type: ignore[attr-defined]
    real_take = worker.take

    def take_then_delete(data: bytes) -> None:
        real_take(data)
        p.wav.unlink(missing_ok=True)

    worker.take = take_then_delete  # type: ignore[method-assign]
    assert_that(worker.run(), is_(equal_to(1)))


def test_a_worker_another_run_replaced_writes_nothing(
    tmp_path: Path, monkeypatch: object
) -> None:
    worker, _ = _worker(tmp_path, monkeypatch)
    p = _paths(tmp_path)
    p.stream_pid.write_text("1")  # the next run's worker
    worker.take(_frames(3, LOUD))
    with pytest.raises(stream.Orphan):
        worker.finish()
    assert_that(p.stream_text.exists(), is_(False))


def test_a_short_word_after_a_long_pause_is_sent(
    tmp_path: Path, monkeypatch: object
) -> None:
    worker, sent = _worker(tmp_path, monkeypatch)
    worker.take(_frames(8, SILENT) + _frames(0.3, LOUD) + _frames(0.5, SILENT))
    worker.finish()
    assert_that(len(sent.pieces), is_(equal_to(1)))


def test_a_failed_piece_ends_the_worker(tmp_path: Path, monkeypatch: object) -> None:
    worker, _ = _worker(tmp_path, monkeypatch)

    def refuse(*_args: object, **_kwargs: object) -> str:
        msg = "down"
        raise stream.TranscribeError(msg)

    monkeypatch.setattr(stream, "transcribe_audio", refuse)  # type: ignore[attr-defined]
    p = _paths(tmp_path)
    p.wav.write_bytes(_wav(_frames(3, LOUD)))
    worker.finishing = True
    assert_that(worker.run(), is_(equal_to(1)))


def test_the_text_so_far_joins_the_pieces(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    p.stream_text.write_text("Hola.\nQué tal.\n")
    assert_that(stream.text_so_far(p), is_(equal_to("Hola. Qué tal.")))


def test_no_pieces_is_no_text(tmp_path: Path) -> None:
    assert_that(stream.text_so_far(_paths(tmp_path)), is_(equal_to("")))


def test_cleanup_deletes_the_words(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    p.stream_text.write_text("Hola.\n")
    stream.cleanup(p)
    assert_that(p.stream_text.exists(), is_(False))
