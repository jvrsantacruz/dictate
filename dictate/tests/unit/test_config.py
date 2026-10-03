"""Settings come from a generated file, and the environment overrides them."""

from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to, is_

from dictate import config


def test_the_file_format_strips_quotes_and_skips_comments() -> None:
    text = '# a comment\n\nDICTATE_METHOD="ime"\nDICTATE_LANG=es\n'
    assert_that(
        config.parse_file(text),
        is_(equal_to({"DICTATE_METHOD": "ime", "DICTATE_LANG": "es"})),
    )


def test_defaults_are_the_scripts_old_ones() -> None:
    assert_that(config.build({}), is_(equal_to(config.Config())))


def test_an_unknown_method_is_refused() -> None:
    with pytest.raises(config.ConfigError):
        config.build({"DICTATE_METHOD": "telepathy"})


def test_a_cap_of_zero_seconds_is_refused() -> None:
    with pytest.raises(config.ConfigError):
        config.build({"DICTATE_MAX_SECS": "0"})


def test_an_unknown_key_sender_is_refused() -> None:
    with pytest.raises(config.ConfigError):
        config.build({"DICTATE_KEYS": "xdotool"})


def test_an_unknown_notify_level_reads_as_failures() -> None:
    assert_that(
        config.build({"DICTATE_NOTIFY": "failure"}).notify, is_(equal_to("failures"))
    )


def test_sound_is_on_only_for_true() -> None:
    assert_that(config.build({"DICTATE_SOUND": "yes"}).sound, is_(False))
    assert_that(config.build({"DICTATE_SOUND": "true"}).sound, is_(True))


def test_the_layout_defaults_to_us_intl() -> None:
    assert_that(config.build({}).layout, is_(equal_to("us+intl")))


def test_languages_split_on_spaces() -> None:
    assert_that(
        config.build({"DICTATE_LANGUAGES": "en es fr"}).languages,
        is_(equal_to(("en", "es", "fr"))),
    )


def test_the_environment_wins_over_the_file(tmp_path: Path) -> None:
    (tmp_path / "dictate").mkdir()
    (tmp_path / "dictate" / "config").write_text('DICTATE_METHOD="paste"\n')
    env = {"XDG_CONFIG_HOME": str(tmp_path), "DICTATE_METHOD": "type"}
    assert_that(
        config.load(env, system=tmp_path / "none").method, is_(equal_to("type"))
    )


def test_a_missing_file_gives_defaults(tmp_path: Path) -> None:
    env = {
        "XDG_CONFIG_HOME": str(tmp_path),
        "DICTATE_SYSTEM_CONFIG": str(tmp_path / "no"),
    }
    assert_that(config.load(env), is_(equal_to(config.Config())))


def test_the_user_file_wins_over_the_machines(tmp_path: Path) -> None:
    system = tmp_path / "etc-config"
    system.write_text('DICTATE_METHOD="type"\nDICTATE_NOTIFY="none"\n')
    (tmp_path / "dictate").mkdir()
    (tmp_path / "dictate" / "config").write_text('DICTATE_METHOD="ime"\n')
    cfg = config.load({"XDG_CONFIG_HOME": str(tmp_path)}, system=system)
    assert_that((cfg.method, cfg.notify), is_(equal_to(("ime", "none"))))


def test_without_files_the_defaults_hold(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    assert_that(
        config.load(env, system=tmp_path / "none"), is_(equal_to(config.Config()))
    )


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "file:///etc/passwd", "ftp://127.0.0.1", "not a url"],
)
def test_a_url_that_could_leak_audio_is_refused(url: str) -> None:
    with pytest.raises(config.ConfigError):
        config.build({"DICTATE_URL": url})


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8081", "http://localhost:9000", "https://api.example.com"]
)
def test_loopback_http_and_any_https_are_accepted(url: str) -> None:
    assert_that(config.build({"DICTATE_URL": url}).url, is_(equal_to(url)))
