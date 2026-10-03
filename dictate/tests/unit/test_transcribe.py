"""What goes to the backend and what comes back."""

import time
from pathlib import Path

import pytest
from hamcrest import assert_that, contains_string, equal_to, is_

from dictate import config, transcribe


def test_segments_become_one_line() -> None:
    assert_that(
        transcribe.clean(" Hola.\n Vamos a ver. "), is_(equal_to("Hola. Vamos a ver."))
    )


def test_nonspeech_tags_alone_are_empty() -> None:
    assert_that(transcribe.clean("[BLANK_AUDIO] (wind blowing)"), is_(equal_to("")))


def test_many_tags_before_speech_are_quick() -> None:
    start = time.monotonic()
    text = transcribe.clean(" ".join(["[music]"] * 40) + " hello")
    assert_that(time.monotonic() - start < 0.1, is_(True))
    assert_that(text.endswith("hello"), is_(True))


def test_speech_with_a_tag_is_kept() -> None:
    assert_that(transcribe.clean("(laughs) okay"), is_(equal_to("(laughs) okay")))


def test_the_form_carries_the_fields_and_the_audio() -> None:
    body, ctype = transcribe.multipart({"language": "es"}, b"RIFF")
    assert_that(ctype, contains_string("multipart/form-data; boundary="))
    assert_that(body.decode(), contains_string('name="language"\r\n\r\nes\r\n'))
    assert_that(body.decode(), contains_string('filename="audio.wav"'))
    assert_that(body.decode(), contains_string("RIFF"))


def test_the_local_backend_posts_to_inference(tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    url, _, _ = transcribe.request(config.Config(url="http://x:1"), "en", wav)
    assert_that(url, is_(equal_to("http://x:1/inference")))


def test_the_openai_backend_needs_a_key_command(tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(transcribe.TranscribeError):
        transcribe.request(config.Config(backend="openai"), "en", wav)


def test_the_openai_backend_reads_the_key_from_the_command(tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    cfg = config.Config(backend="openai", url="http://x:1", key_cmd="echo sk-test")
    url, headers, _ = transcribe.request(cfg, "en", wav)
    assert_that(url, is_(equal_to("http://x:1/v1/audio/transcriptions")))
    assert_that(headers["Authorization"], is_(equal_to("Bearer sk-test")))
