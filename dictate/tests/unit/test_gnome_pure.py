"""The parts of the GNOME adapter that need no desktop."""

from hamcrest import assert_that, contains_string, equal_to, is_, none

from dictate import desktop
from dictate.gnome import component, rules
from dictate.gnome.focus import Tracker
from dictate.gnome.keys import presses
from dictate.gnome.rules import PURPOSE_FREE_FORM, PURPOSE_TERMINAL
from dictate.keymap import SHIFT, Chord


def test_gnome_on_wayland_gets_the_adapter() -> None:
    env = {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}
    assert_that(desktop.select(env), is_(equal_to(desktop.GNOME_WAYLAND)))


def test_another_desktop_gets_none() -> None:
    env = {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"}
    assert_that(desktop.select(env), is_(none()))


def test_gnome_on_x11_gets_none() -> None:
    env = {"XDG_SESSION_TYPE": "x11", "XDG_CURRENT_DESKTOP": "GNOME"}
    assert_that(desktop.select(env), is_(none()))


def test_a_terminal_pastes_with_shift() -> None:
    assert_that(
        rules.paste_chord(PURPOSE_TERMINAL), is_(equal_to(Chord(47, (29, SHIFT))))
    )


def test_anything_else_pastes_with_ctrl_v() -> None:
    assert_that(rules.paste_chord(PURPOSE_FREE_FORM), is_(equal_to(Chord(47, (29,)))))


def test_utf8_text_is_preferred() -> None:
    types = ["text/html", "text/plain", "text/plain;charset=utf-8"]
    assert_that(rules.text_type(types), is_(equal_to("text/plain;charset=utf-8")))


def test_an_image_has_no_text_type() -> None:
    assert_that(rules.text_type(["image/png"]), is_(none()))


def test_modifiers_wrap_each_chord() -> None:
    assert_that(
        presses([Chord(30, (SHIFT,)), Chord(48)]),
        is_(
            equal_to(
                [
                    (42, True),
                    (30, True),
                    (30, False),
                    (42, False),
                    (48, True),
                    (48, False),
                ]
            )
        ),
    )


def test_the_token_is_stable_while_focus_stays() -> None:
    t = Tracker()
    t.focus_in(1)
    before = t.token
    t.purpose(1, PURPOSE_TERMINAL)
    assert_that(t.snapshot(), is_(equal_to((before, True, PURPOSE_TERMINAL))))


def test_any_focus_change_changes_the_token() -> None:
    t = Tracker()
    t.focus_in(1)
    before = t.token
    t.focus_out(1)
    t.focus_in(1)
    assert_that(t.token == before, is_(False))


def test_two_runs_never_share_a_token() -> None:
    assert_that(Tracker().token == Tracker().token, is_(False))


def test_commit_needs_the_same_token_and_a_holder() -> None:
    t = Tracker()
    t.focus_in(7)
    assert_that(t.may_commit(t.token), is_(equal_to(7)))
    assert_that(t.may_commit("other:0"), is_(none()))
    t.focus_out(7)
    assert_that(t.may_commit(t.token), is_(none()))


def test_disabling_moves_focus_but_keeps_the_purpose() -> None:
    t = Tracker()
    t.focus_in(7)
    t.purpose(7, PURPOSE_TERMINAL)
    before = t.token
    t.disable(7)
    assert_that(t.token == before, is_(False))
    t.focus_in(7)
    assert_that(t.snapshot()[2], is_(equal_to(PURPOSE_TERMINAL)))


def test_a_destroyed_holder_drops_focus() -> None:
    t = Tracker()
    t.focus_in(7)
    t.forget(7)
    assert_that(t.snapshot()[1], is_(False))


def test_the_component_runs_the_program_as_engine_and_describer() -> None:
    text = component.xml("/usr/bin/dictate")
    assert_that(text, contains_string("<exec>/usr/bin/dictate engine --ibus</exec>"))
    assert_that(text, contains_string('<engines exec="/usr/bin/dictate engines"/>'))


def test_the_engine_carries_the_full_layout() -> None:
    text = component.engines("us+intl")
    assert_that(text, contains_string("<name>dictate</name>"))
    assert_that(text, contains_string("<layout>us+intl</layout>"))


def test_only_xkb_shaped_layouts_are_written() -> None:
    assert_that(component.valid_layout("us+intl"), is_(True))
    assert_that(component.valid_layout("de"), is_(True))
    assert_that(component.valid_layout("us</layout><x>"), is_(False))
