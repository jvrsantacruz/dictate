"""The merge rules of `dictate setup`, without a desktop."""

import pytest
from hamcrest import assert_that, equal_to, is_

from dictate.gnome import setup

BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


def test_gsettings_lists_read_back() -> None:
    assert_that(setup.parse_variant("@a(ss) []"), is_(equal_to([])))
    assert_that(setup.parse_variant("@as []"), is_(equal_to([])))
    assert_that(
        setup.parse_variant("[('xkb', 'us+intl'), ('ibus', 'dictate')]"),
        is_(equal_to([("xkb", "us+intl"), ("ibus", "dictate")])),
    )


def test_sources_and_paths_format_for_gsettings() -> None:
    assert_that(
        setup.format_sources([("ibus", "dictate"), ("xkb", "us")]),
        is_(equal_to("[('ibus', 'dictate'), ('xkb', 'us')]")),
    )
    assert_that(setup.format_sources([]), is_(equal_to("@a(ss) []")))
    assert_that(setup.format_paths([]), is_(equal_to("@as []")))


def test_auto_takes_the_users_first_plain_layout() -> None:
    sources = [("ibus", "mozc-jp"), ("xkb", "es"), ("xkb", "us")]
    assert_that(setup.pick_layout(sources, "auto"), is_(equal_to("es")))


def test_auto_without_a_plain_layout_is_us() -> None:
    assert_that(setup.pick_layout([], "auto"), is_(equal_to("us")))


def test_a_given_layout_wins() -> None:
    assert_that(setup.pick_layout([("xkb", "es")], "us+intl"), is_(equal_to("us+intl")))


def test_the_engine_goes_first_and_the_users_sources_stay() -> None:
    sources = [("xkb", "es"), ("ibus", "mozc-jp")]
    assert_that(
        setup.merge_sources(sources, "es"),
        is_(equal_to([("ibus", "dictate"), ("xkb", "es"), ("ibus", "mozc-jp")])),
    )


def test_the_layout_is_added_when_the_user_lacks_it() -> None:
    assert_that(
        setup.merge_sources([("xkb", "us")], "us+intl"),
        is_(equal_to([("ibus", "dictate"), ("xkb", "us+intl"), ("xkb", "us")])),
    )


def test_merging_sources_twice_changes_nothing() -> None:
    once = setup.merge_sources([("xkb", "us+intl")], "us+intl")
    assert_that(setup.merge_sources(once, "us+intl"), is_(equal_to(once)))


def test_other_shortcuts_are_kept_and_stale_ones_found() -> None:
    paths = [f"{BASE}custom0/", f"{BASE}dictate/", f"{BASE}dictate-fr/"]
    wanted, stale = setup.merge_paths(paths, ["en", "es"])
    assert_that(
        wanted,
        is_(equal_to([f"{BASE}custom0/", f"{BASE}dictate-en/", f"{BASE}dictate-es/"])),
    )
    assert_that(stale, is_(equal_to([f"{BASE}dictate/", f"{BASE}dictate-fr/"])))


def test_shortcuts_default_and_can_be_given() -> None:
    assert_that(
        setup.shortcuts(["en", "es"], ["es=<Super>s"]),
        is_(equal_to({"en": "<Super>i", "es": "<Super>s"})),
    )


def test_a_language_without_a_default_needs_a_shortcut() -> None:
    with pytest.raises(setup.SetupError):
        setup.shortcuts(["fr"], [])


def test_a_shortcut_for_an_unknown_language_is_refused() -> None:
    with pytest.raises(setup.SetupError):
        setup.shortcuts(["en"], ["fr=<Super>f"])


def test_the_config_is_sorted_and_quoted() -> None:
    text = setup.render_config({"DICTATE_METHOD": "ime", "DICTATE_LAYOUT": "us"})
    assert_that(
        text.splitlines()[-2:],
        is_(equal_to(['DICTATE_LAYOUT="us"', 'DICTATE_METHOD="ime"'])),
    )


def test_a_dry_run_removes_no_stale_shortcut(monkeypatch) -> None:  # noqa: ANN001
    ran: list[tuple[str, ...]] = []
    s = setup.Session(dry_run=True, out=lambda _line: None)
    paths = f"['{BASE}dictate/']"
    values = {
        "custom-keybindings": paths,
        "name": "''",
        "command": "''",
        "binding": "''",
    }

    def fake_run(*argv: str, check: bool = True) -> object:  # noqa: ARG001
        ran.append(argv)

        class Done:
            returncode = 0
            stdout = values.get(argv[-1], "''")
            stderr = ""

        return Done()

    monkeypatch.setattr(s, "run", fake_run)
    setup._shortcuts(s, {"en": "<Super>i"}, "/usr/bin/dictate")  # noqa: SLF001
    assert_that([a for a in ran if a[1] != "get"], is_(equal_to([])))
    assert_that(any("removed" in c for c in s.changes), is_(True))
