# Changelog

## Unreleased

- Install with one file: `dictate.sources` on the site names the apt repository and holds its
  key. Existing installs keep working; the old keyring file and sources stay valid.

## 0.1.1

- The apt repository is signed by a new key,
  `0236 18A8 42F3 2549 E1A7  A820 2AB0 8318 A522 3B11`. 0.1.0 was never served from it.

## 0.1.0

First public release.

- Dictation into the focused input on GNOME on Wayland, through an IBus engine.
- Four delivery methods: `ime`, `paste`, `type`, `clipboard`; text goes to the clipboard when
  focus moved since the press.
- `dictate setup` sets up a user: config, input source, shortcuts, tray icon.
- A tray icon that blinks while recording, and a tmux status segment.
- Packages for Ubuntu 24.04 and later: `dictate`, `dictate-indicator`, `dictate-uinput`.
