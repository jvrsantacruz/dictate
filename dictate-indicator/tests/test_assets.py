"""The icons have to reach the disk, because AppIndicator reads a path."""

from pathlib import Path

from hamcrest import assert_that, equal_to, is_

from dictate_indicator import assets, view


def test_every_icon_is_written(tmp_path: Path) -> None:
    assets.install(tmp_path / "icons")
    written = sorted(p.name for p in (tmp_path / "icons").iterdir())
    assert_that(written, is_(equal_to(sorted(f"{name}.svg" for name in assets.NAMES))))


def test_the_icons_are_not_empty(tmp_path: Path) -> None:
    target = assets.install(tmp_path / "icons")
    assert_that(
        all((target / f"{n}.svg").stat().st_size > 0 for n in assets.NAMES), is_(True)
    )


def test_a_second_install_leaves_the_file_alone(tmp_path: Path) -> None:
    target = assets.install(tmp_path / "icons")
    path = target / "dictate-recording.svg"
    before = path.stat().st_mtime_ns
    assets.install(target)
    assert_that(path.stat().st_mtime_ns, is_(equal_to(before)))


def test_a_changed_file_is_rewritten(tmp_path: Path) -> None:
    target = assets.install(tmp_path / "icons")
    path = target / "dictate-recording.svg"
    path.write_text("stale")
    assets.install(target)
    assert_that(path.read_text() != "stale", is_(True))


def test_the_cache_directory_follows_the_environment(monkeypatch: object) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/cache")
    assert_that(
        assets.default_dir(), is_(equal_to(Path("/tmp/cache/dictate-indicator/icons")))
    )


def test_every_icon_the_view_names_is_unpacked() -> None:
    named = {*view.ICONS.values(), view.CAPTURING_DIM}
    assert_that(named - set(assets.NAMES), is_(equal_to(set())))
