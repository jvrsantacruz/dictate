"""Speech to text, through a whisper-server or an OpenAI-compatible endpoint."""

from __future__ import annotations

import http.client
import json
import re
import shlex
import subprocess
import urllib.request
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from dictate.config import Config

TIMEOUT = 300
# Whisper labels non-speech as [BLANK_AUDIO], (wind blowing) and similar. A
# transcript that is nothing but such tags means nothing was said.
# One place for whitespace between tags, so the match cannot backtrack.
NONSPEECH = re.compile(r"^\s*(?:[\[(][^\])]*[\])]\s*)+$")


class TranscribeError(RuntimeError):
    """The backend could not be reached, refused, or answered nonsense."""


def multipart(fields: dict[str, str], audio: bytes) -> tuple[bytes, str]:
    """Encode a form with the audio as `file`. Returns the body and its type."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
        + audio
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def clean(text: str) -> str:
    """One line of text, or empty when it holds no speech.

    Whisper splits a longer utterance into segments on separate lines. Dictated
    speech is one sentence stream, and a newline typed into a chat sends it.
    """
    text = " ".join(text.split())
    return "" if NONSPEECH.match(text) else text


def request(cfg: Config, lang: str, wav: Path) -> tuple[str, dict[str, str], bytes]:
    """The URL, headers and body for this backend."""
    audio = wav.read_bytes()
    if cfg.backend == "local":
        # whisper-server 1.8.x serves /inference only.
        body, ctype = multipart({"language": lang, "response_format": "json"}, audio)
        return f"{cfg.url}/inference", {"Content-Type": ctype}, body
    if cfg.backend == "openai":
        if not cfg.key_cmd:
            msg = "openai backend needs DICTATE_KEY_CMD"
            raise TranscribeError(msg)
        key = subprocess.run(
            shlex.split(cfg.key_cmd), capture_output=True, text=True, check=False
        ).stdout.strip()
        if not key:
            msg = "DICTATE_KEY_CMD printed no key"
            raise TranscribeError(msg)
        fields = {"model": cfg.model, "language": lang, "response_format": "json"}
        body, ctype = multipart(fields, audio)
        headers = {"Content-Type": ctype, "Authorization": f"Bearer {key}"}
        return f"{cfg.url}/v1/audio/transcriptions", headers, body
    msg = f"unknown backend: {cfg.backend}"
    raise TranscribeError(msg)


def transcribe(cfg: Config, lang: str, wav: Path) -> str:
    """Send the capture and return the cleaned text."""
    try:
        url, headers, body = request(cfg, lang, wav)
    except (OSError, ValueError) as err:
        msg = f"could not build the request: {err}"
        raise TranscribeError(msg) from err
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            payload = resp.read()
    except (OSError, http.client.HTTPException) as err:
        msg = f"backend request failed: {err}"
        raise TranscribeError(msg) from err
    try:
        text = json.loads(payload).get("text", "")
    except (ValueError, AttributeError) as err:
        msg = f"bad response: {payload[:120]!r}"
        raise TranscribeError(msg) from err
    return clean(str(text))
