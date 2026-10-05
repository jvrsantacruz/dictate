# Development

Three applications and their build scripts:

```text
dictate/            the program, its IBus engine and `dictate setup`
dictate-indicator/  the tray icon
dictate-uinput/     the udev rule that grants /dev/uinput, alone
tools/              deb-version, deb-build, deb-check, apt-repo, apt-sources,
                    tray-screenshot
```

`docs/tray.png` is made in a private headless GNOME Shell, never this desktop:
`tools/tray-screenshot dictate-indicator/dist/dictate-indicator docs/tray.png`, after
`make -C dictate-indicator build`.

Each application is a zipapp on the system interpreter, packaged with `dpkg-deb`. `gi` comes
from apt, so nothing else is needed at run time.

## dictate

```text
cli.py          wiring only
  dictation.py  one press: start, or stop, transcribe and deliver
  delivery.py   the four methods and the fallback, against the port
  desktop.py    the port, and the choice of its adapter
  gnome/        the one adapter: wl-clipboard, ydotool, the IBus engine, setup
```

The engine counts focus changes; a method inserts the text only if the count is the one taken
when recording started. Otherwise the text goes to the clipboard and a notification says why.

## dictate-indicator

```text
cli.py          argparse, wiring only
  state.py      the state file as a value      pure, tested
  view.py       what to show for a state       pure, tested
  assets.py     unpack the icons to the cache  pure, tested
  indicator.py  AppIndicator and the main loop every GTK call
```

## Tests

| Tier | Runs against | Command |
|---|---|---|
| unit | pure rules, no desktop | `make -C dictate test` |
| headless | a private GNOME Shell on its own session bus, with IBus and a test window | `make -C dictate integration` |
| package | lintian, then upgrade, reinstall and purge in clean Ubuntu containers | `make deb-check` |
| live | your desktop, through ydotool; takes the keyboard for about 20 seconds | `make -C dictate smoke` |

The headless tier never touches your session: it runs its own shell, bus, settings and IBus.

## Hooks

```sh
pre-commit install
```

Installs the checks in `.pre-commit-config.yaml` for commits, commit messages and pushes. Each
runs only when the commit touches what it reads: ruff on Python, shellcheck on shell, actionlint
and zizmor on workflows. A push runs the unit tests and refuses a version tag that
`CHANGELOG.md` does not open with. CI runs every check on every file.

`tools/hooks/private-words` refuses words listed in `~/.config/git/private-words`, a file kept
outside the repository; without it, nothing is checked.

## Versions

A release is a tag `vX.Y.Z`. Builds after it carry `+gitN.gSHA`, and uncommitted ones
`.dirtyHASH`, so every build has a version that sorts after the release before it.
