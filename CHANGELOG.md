# Changelog

## 0.1.0

First public release.

- Dictation into the focused input on GNOME on Wayland, through an IBus engine.
- Four delivery methods: `ime`, `paste`, `type`, `clipboard`; text goes to the clipboard when
  focus moved since the press.
- `dictate setup` sets up a user: config, input source, shortcuts, tray icon.
- A tray icon that blinks while recording, and a tmux status segment.
- Packages for Ubuntu 24.04 and later: `dictate`, `dictate-indicator`, `dictate-uinput`.
