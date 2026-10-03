"""Text to keystrokes on the two layouts the table knows."""

import pytest
from hamcrest import assert_that, equal_to, is_

from dictate.keymap import ALTGR, SHIFT, SPACE, Chord, UntypableError, plan

A, E, N, APOSTROPHE, GRAVE, SLASH = 30, 18, 49, 40, 41, 53


def test_a_lowercase_letter_is_one_key() -> None:
    assert_that(plan("a", "us"), is_(equal_to([Chord(A)])))


def test_an_uppercase_letter_holds_shift() -> None:
    assert_that(plan("A", "us"), is_(equal_to([Chord(A, (SHIFT,))])))


def test_on_us_an_apostrophe_is_one_key() -> None:
    assert_that(plan("'", "us"), is_(equal_to([Chord(APOSTROPHE)])))


def test_on_us_intl_an_apostrophe_is_the_dead_key_then_space() -> None:
    assert_that(plan("'", "us+intl"), is_(equal_to([Chord(APOSTROPHE), Chord(SPACE)])))


def test_an_acute_vowel_is_the_dead_key_then_the_vowel() -> None:
    assert_that(plan("é", "us+intl"), is_(equal_to([Chord(APOSTROPHE), Chord(E)])))


def test_an_uppercase_acute_vowel_shifts_the_vowel() -> None:
    assert_that(
        plan("É", "us+intl"), is_(equal_to([Chord(APOSTROPHE), Chord(E, (SHIFT,))]))
    )


def test_enye_is_dead_tilde_then_n() -> None:
    assert_that(plan("ñ", "us+intl"), is_(equal_to([Chord(GRAVE, (SHIFT,)), Chord(N)])))


def test_the_inverted_question_mark_is_altgr() -> None:
    assert_that(plan("¿", "us+intl"), is_(equal_to([Chord(SLASH, (ALTGR,))])))


def test_spanish_is_fully_typable_on_us_intl() -> None:
    plan('¿Qué tal? ¡Ñandú, pingüino! It\'s "fine".', "us+intl")


def test_accents_cannot_be_typed_on_us() -> None:
    with pytest.raises(UntypableError):
        plan("é", "us")


def test_a_character_outside_the_table_is_refused_by_name() -> None:
    with pytest.raises(UntypableError) as err:
        plan("10 €", "us+intl")
    assert_that(err.value.char, is_(equal_to("€")))


def test_an_unknown_layout_is_refused() -> None:
    with pytest.raises(UntypableError):
        plan("a", "de")
