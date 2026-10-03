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


def test_control_and_format_characters_are_dropped() -> None:
    assert_that(
        transcribe.clean("ls\x0f -la\x1b[201~ \u202eok"),
        is_(equal_to("ls -la[201~ ok")),
    )


def test_a_multi_line_key_command_gives_its_first_line(tmp_path: Path) -> None:
    script = tmp_path / "key"
    script.write_text("#!/bin/sh\necho sk-good\necho 'user: me'\n")
    script.chmod(0o755)
    cfg = config.Config(backend="openai", url="https://x.example", key_cmd=str(script))
    assert_that(transcribe._key(cfg), is_(equal_to("sk-good")))  # noqa: SLF001


def test_a_failing_key_command_says_so_without_its_output(tmp_path: Path) -> None:
    script = tmp_path / "key"
    script.write_text("#!/bin/sh\necho sk-secret\nexit 3\n")
    script.chmod(0o755)
    cfg = config.Config(backend="openai", url="https://x.example", key_cmd=str(script))
    with pytest.raises(transcribe.TranscribeError) as err:
        transcribe._key(cfg)  # noqa: SLF001
    assert_that("sk-secret" in str(err.value), is_(False))


def test_a_redirect_is_refused() -> None:
    import http.server  # noqa: PLC0415
    import threading  # noqa: PLC0415

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/steal")
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.handle_request, daemon=True).start()
    cfg = config.Config(url=f"http://127.0.0.1:{server.server_address[1]}")
    wav = Path(__file__)
    with pytest.raises(transcribe.TranscribeError) as err:
        transcribe.transcribe(cfg, "en", wav)
    assert_that(str(err.value), contains_string("redirect"))
