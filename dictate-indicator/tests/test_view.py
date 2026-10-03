"""What the tray shows, decided without a display."""

from hamcrest import assert_that, equal_to, is_

from dictate_indicator import state, view


def test_idle_shows_nothing() -> None:
    assert_that(view.render(state.IDLE, 0), is_(equal_to(view.HIDDEN)))


def test_capturing_shows_the_red_icon() -> None:
    marker = view.render(state.State("capturing", 100, "en"), 108)
    assert_that(marker.icon, is_(equal_to("dictate-recording")))


def test_capturing_blinks_to_the_ring_on_odd_seconds() -> None:
    marker = view.render(state.State("capturing", 100, "en"), 101)
    assert_that(marker.icon, is_(equal_to("dictate-recording-dim")))


def test_transcribing_does_not_blink() -> None:
    marker = view.render(state.State("transcribing", 100, "es"), 101)
    assert_that(marker.icon, is_(equal_to("dictate-transcribing")))


def test_transcribing_shows_the_amber_icon() -> None:
    marker = view.render(state.State("transcribing", 100, "es"), 100)
    assert_that(marker.icon, is_(equal_to("dictate-transcribing")))


def test_the_label_carries_the_language_and_the_timer() -> None:
    marker = view.render(state.State("capturing", 100, "en"), 107)
    assert_that(marker.label, is_(equal_to("EN 0:07")))


def test_the_timer_rolls_into_minutes() -> None:
    marker = view.render(state.State("capturing", 0, "es"), 125)
    assert_that(marker.label, is_(equal_to("ES 2:05")))


def test_the_timer_keeps_two_digits_of_seconds() -> None:
    marker = view.render(state.State("capturing", 0, "en"), 60)
    assert_that(marker.label, is_(equal_to("EN 1:00")))


def test_a_missing_language_leaves_no_leading_space() -> None:
    marker = view.render(state.State("capturing", 0, ""), 5)
    assert_that(marker.label, is_(equal_to("0:05")))
