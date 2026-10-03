# Development

Three applications and their build scripts:

```text
dictate/            the program, its IBus engine and `dictate setup`
dictate-indicator/  the tray icon
dictate-uinput/     the udev rule that grants /dev/uinput, alone
tools/              deb-version, deb-build, deb-check
```

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

## Versions

A release is a tag `vX.Y.Z`. Builds after it carry `+gitN.gSHA`, and uncommitted ones
`.dirtyHASH`, so every build has a version that sorts after the release before it.
