"""What both live tiers need: a fake transcriber, test windows, key presses, runs.

Imported by the headless tier, inside its private session, and by the smoke
tier, on the real desktop. Nothing here starts or stops a desktop.
"""

import http.server
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAKES = HERE.parent / "fakes"
SAMPLE = ' ¿Qué tal? It\'s "ñandú". '
EXPECTED = '¿Qué tal? It\'s "ñandú".'


class Transcriber:
    """A whisper-server stand-in on loopback, answering `self.text`."""

    def __init__(self) -> None:
        self.text = SAMPLE
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers["Content-Length"]))
                body = json.dumps({"text": outer.text}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._server.shutdown()


class Window:
    """One test window, GTK 3 or 4, driven over its stdin."""

    def __init__(
        self,
        version: str,
        env: dict[str, str],
        log: Path,
        nudge=None,
    ) -> None:
        self.version = version
        self._log = log.open("ab")
        self._proc = subprocess.Popen(
            ["/usr/bin/python3", str(HERE / "window.py"), version],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
            text=True, env=env,
        )  # fmt: skip
        # One reader for the life of the window, so a wait that times out
        # cannot leave a thread behind to swallow the next line.
        self._lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        line = self._read(timeout=3)
        # A headless shell starts in the overview and focuses no window until
        # a key closes it.
        if line != "ready" and nudge is not None:
            nudge()
            line = self._read(timeout=10)
        if line != "ready":
            msg = f"gtk{version} window did not get focus: {line!r}"
            raise RuntimeError(msg)

    def _pump(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._lines.put(line.strip())

    def _read(self, timeout: float = 5) -> str:
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            return ""

    def ask(self, command: str) -> str:
        assert self._proc.stdin is not None
        self._proc.stdin.write(command + "\n")
        self._proc.stdin.flush()
        return self._read()

    def focus(self, widget: str) -> None:
        self.ask(f"focus {widget}")
        time.sleep(0.3)

    def texts(self) -> list[str]:
        return json.loads(self.ask("texts"))

    def clear(self) -> None:
        self.ask("clear")

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.wait(timeout=5)
        self._log.close()


def clipboard_set(
    env: dict[str, str], data: bytes, mime: str = "text/plain;charset=utf-8"
) -> None:
    subprocess.run(
        ["wl-copy", "--type", mime], input=data, env=env, check=True, timeout=5
    )
    time.sleep(0.3)


def clipboard_get(env: dict[str, str]) -> str:
    out = subprocess.run(
        ["wl-paste", "--no-newline"],
        capture_output=True,
        env=env,
        timeout=5,
        check=False,
    )
    time.sleep(0.3)
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else ""


class Run:
    """Runs of the artifact under test, with the fakes first on PATH."""

    def __init__(
        self,
        artifact: str,
        base: dict[str, str],
        workdir: Path,
        fakes: tuple[str, ...] = ("pw-record", "pw-play", "notify-send", "ydotool"),
    ) -> None:
        self.artifact = artifact
        self.notify_log = workdir / "notify.log"
        self.ydotool_log = workdir / "ydotool.log"
        # Only the fakes asked for: the live tier keeps the real ydotool.
        bindir = workdir / "fakes"
        bindir.mkdir(exist_ok=True)
        for name in fakes:
            link = bindir / name
            if not link.exists():
                link.symlink_to(FAKES / name)
        self.env = dict(base)
        self.env.update(
            PATH=f"{bindir}:{base['PATH']}",
            FAKE_NOTIFY_LOG=str(self.notify_log),
            FAKE_YDOTOOL_LOG=str(self.ydotool_log),
            DICTATE_NOTIFY="failures",
            DICTATE_SOUND="false",
        )

    def reset_logs(self) -> None:
        self.notify_log.write_text("")
        self.ydotool_log.write_text("")

    def notifications(self) -> str:
        return self.notify_log.read_text() if self.notify_log.exists() else ""

    def press(self, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        env = {**self.env, **extra}
        return subprocess.run(
            [self.artifact, *args], env=env, capture_output=True, text=True, timeout=30,
            check=False,
        )  # fmt: skip

    def dictate(self, method: str, **extra: str) -> subprocess.CompletedProcess[str]:
        """A whole dictation: press, half a second of fake audio, press."""
        first = self.press("en", DICTATE_METHOD=method, **extra)
        if first.returncode != 0:
            return first
        time.sleep(0.5)
        return self.press("en", DICTATE_METHOD=method, **extra)
