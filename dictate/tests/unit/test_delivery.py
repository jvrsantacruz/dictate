"""Every method, and every way it falls back, against a fake desktop."""

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest
from hamcrest import assert_that, contains_string, equal_to, is_

from dictate.delivery import Result
from dictate.delivery import deliver as _deliver
from dictate.desktop import Clip, DesktopError, Focus
from dictate.keymap import Chord

TOKEN = "run:3"


@dataclass
class FakeDesktop:
    now: Focus | None = field(default_factory=lambda: Focus(TOKEN, focused=True))
    committed: list[str] = field(default_factory=list)
    commit_ok: bool = True
    typed: list[Chord] = field(default_factory=list)
    clipboard: Clip = field(default_factory=Clip)
    pasted: list[str] = field(default_factory=list)
    paste_ok: bool = True
    restored: list[Clip] = field(default_factory=list)
    broken: str = ""

    def focus(self) -> Focus | None:
        return self.now

    def commit(self, text: str, token: str) -> bool:
        if self.commit_ok and token == TOKEN:
            self.committed.append(text)
            return True
        return False

    def type_chords(self, chords: Sequence[Chord]) -> None:
        if self.broken == "keys":
            msg = "ydotool failed"
            raise DesktopError(msg)
        self.typed.extend(chords)

    def clipboard_read(self) -> Clip:
        return self.clipboard

    def clipboard_write(self, text: str) -> None:
        if self.broken == "clipboard":
            msg = "wl-copy failed"
            raise DesktopError(msg)
        self.clipboard = Clip(text=text)

    def clipboard_restore(self, clip: Clip) -> None:
        self.restored.append(clip)
        self.clipboard = clip

    def paste(self, text: str) -> bool:
        self.pasted.append(text)
        return self.paste_ok


def deliver(text: str, method: str, press: str | None, d: FakeDesktop) -> Result:
    return _deliver(text, method, press, d, "us+intl")


def test_ime_commits_through_the_engine() -> None:
    d = FakeDesktop()
    assert_that(deliver("hola", "ime", TOKEN, d).delivered, is_(True))
    assert_that(d.committed, is_(equal_to(["hola"])))
    assert_that(d.clipboard, is_(equal_to(Clip())))


def test_type_presses_the_planned_keys() -> None:
    d = FakeDesktop()
    assert_that(deliver("a", "type", TOKEN, d).delivered, is_(True))
    assert_that(d.typed, is_(equal_to([Chord(30)])))


def test_paste_puts_the_clipboard_back() -> None:
    d = FakeDesktop(clipboard=Clip(text="keep me"))
    assert_that(deliver("hola", "paste", TOKEN, d).delivered, is_(True))
    assert_that(d.clipboard, is_(equal_to(Clip(text="keep me"))))


def test_paste_reports_a_clipboard_it_could_not_keep() -> None:
    d = FakeDesktop(clipboard=Clip(lost=True))
    assert_that(deliver("hola", "paste", TOKEN, d).clipboard_lost, is_(True))


def test_a_desktop_that_fails_midway_falls_back() -> None:
    d = FakeDesktop(broken="keys")
    result = deliver("hola", "type", TOKEN, d)
    assert_that(result.delivered, is_(False))
    assert_that(result.reason, contains_string("ydotool failed"))
    assert_that(d.clipboard, is_(equal_to(Clip(text="hola"))))


def test_a_clipboard_that_fails_too_is_reported_not_raised() -> None:
    d = FakeDesktop(now=Focus("run:9", focused=True), broken="clipboard")
    result = deliver("hola", "ime", TOKEN, d)
    assert_that(result.delivered, is_(False))
    assert_that(result.reason, contains_string("clipboard failed"))


def test_the_clipboard_method_only_copies() -> None:
    d = FakeDesktop(now=None)
    assert_that(deliver("hola", "clipboard", None, d).delivered, is_(True))
    assert_that(d.clipboard, is_(equal_to(Clip(text="hola"))))


@pytest.mark.parametrize("method", ["ime", "type", "paste"])
def test_focus_moved_since_the_press_falls_back(method: str) -> None:
    d = FakeDesktop(now=Focus("run:5", focused=True))
    result = deliver("hola", method, TOKEN, d)
    assert_that(result.delivered, is_(False))
    assert_that(result.reason, contains_string("focus moved"))
    assert_that(d.clipboard, is_(equal_to(Clip(text="hola"))))
    assert_that((d.committed, d.typed, d.pasted), is_(equal_to(([], [], []))))


@pytest.mark.parametrize("method", ["ime", "type", "paste"])
def test_no_input_focused_falls_back(method: str) -> None:
    d = FakeDesktop(now=Focus(TOKEN, focused=False))
    assert_that(deliver("hola", method, TOKEN, d).reason, contains_string("no input"))


@pytest.mark.parametrize("method", ["ime", "type", "paste"])
def test_an_engine_that_does_not_answer_falls_back(method: str) -> None:
    d = FakeDesktop(now=None)
    assert_that(
        deliver("hola", method, TOKEN, d).reason, contains_string("unknown now")
    )


@pytest.mark.parametrize("method", ["ime", "type", "paste"])
def test_no_engine_at_the_press_falls_back(method: str) -> None:
    d = FakeDesktop()
    assert_that(deliver("hola", method, None, d).reason, contains_string("unknown at"))


def test_a_commit_the_engine_refuses_falls_back() -> None:
    d = FakeDesktop(commit_ok=False)
    result = deliver("hola", "ime", TOKEN, d)
    assert_that(result.delivered, is_(False))
    assert_that(d.clipboard, is_(equal_to(Clip(text="hola"))))


def test_untypable_text_falls_back_naming_the_character() -> None:
    d = FakeDesktop()
    result = deliver("10 €", "type", TOKEN, d)
    assert_that(result.reason, contains_string("€"))
    assert_that(d.typed, is_(equal_to([])))


def test_a_paste_the_application_did_not_take_leaves_the_text_on_the_clipboard() -> (
    None
):
    d = FakeDesktop(paste_ok=False, clipboard=Clip(text="old"))
    result = deliver("hola", "paste", TOKEN, d)
    assert_that(result.delivered, is_(False))
    assert_that(d.clipboard, is_(equal_to(Clip(text="hola"))))
