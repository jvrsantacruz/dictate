<p align="center"><img src="docs/logo.svg" width="120" alt="dictate logo"></p>

<h1 align="center">dictate</h1>

<p align="center">
Speak into any text field on GNOME. Press a shortcut, talk, press it again: the text appears where your cursor was.
</p>

<p align="center">
<a href="https://github.com/jvrsantacruz/dictate/actions/workflows/ci.yml"><img src="https://github.com/jvrsantacruz/dictate/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://github.com/jvrsantacruz/dictate/releases/latest"><img src="https://img.shields.io/github/v/release/jvrsantacruz/dictate" alt="Latest release"></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/jvrsantacruz/dictate" alt="License: GPL-3.0-or-later"></a>
</p>

- **Local.** Speech is transcribed on your machine by [whisper.cpp](https://github.com/ggml-org/whisper.cpp); nothing leaves it unless you point it elsewhere.
- **Into the right field.** An IBus input method inserts the text into the input that had focus when you started. If you moved away, the text waits on the clipboard instead of landing somewhere else.
- **Any language whisper knows**, one shortcut each. English and Spanish out of the box.
- **Status at a glance**: a tray icon that blinks while recording, and an optional tmux segment.

Runs on Ubuntu 24.04 or later, GNOME on Wayland.

## Install

From the apt repository, which keeps it up to date with the rest of the system:

```sh
sudo curl -fsSLo /usr/share/keyrings/dictate-archive-keyring.gpg \
  https://jvrsantacruz.github.io/dictate/dictate-archive-keyring.gpg
printf 'Types: deb\nURIs: https://jvrsantacruz.github.io/dictate/apt\nSuites: stable\nComponents: main\nSigned-By: /usr/share/keyrings/dictate-archive-keyring.gpg\n' \
  | sudo tee /etc/apt/sources.list.d/dictate.sources
sudo apt update && sudo apt install dictate dictate-indicator
```

Or from the PPA:

```sh
sudo add-apt-repository ppa:jvrsantacruz/dictate
sudo apt install dictate dictate-indicator
```

Or download the `.deb` files from the [latest release](https://github.com/jvrsantacruz/dictate/releases/latest) and `sudo apt install ./dictate_*.deb ./dictate-indicator_*.deb`.

### A transcriber

dictate sends audio to a whisper server on `http://127.0.0.1:8081`. On Ubuntu 26.04:

```sh
sudo apt install whisper.cpp
mkdir -p ~/.local/share/whisper
curl -fsSLo ~/.local/share/whisper/ggml-base-q5_1.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin
whisper-server -m ~/.local/share/whisper/ggml-base-q5_1.bin --host 127.0.0.1 --port 8081
```

Any OpenAI-compatible transcription endpoint works too: see [Configure](#configure).

## Configure

Once per user, from your desktop session:

```sh
dictate setup
```

It adds the input method, binds <kbd>Super</kbd>+<kbd>I</kbd> to English and <kbd>Super</kbd>+<kbd>E</kbd> to Spanish, writes `~/.config/dictate/config`, and starts the tray icon. It only changes what differs, so run it again after an upgrade or to change a setting. `dictate setup --help` lists every option; `--dry-run` shows the changes without making them.

| Setting | Values | Default |
|---|---|---|
| `--method` | `ime` inserts through the input method; `paste` and `type` press keys; `clipboard` only copies | `ime` |
| `--languages`, `--shortcut LANG=KEYS` | whisper language codes and their shortcuts | `en es` |
| `--notify` | `all`, `failures`, `none` | `failures` |
| `--sound` | a cue before and after recording | `false` |
| `--backend`, `--url`, `--key-cmd` | `local` whisper-server, or `openai` with a command that prints the key | `local` |

An admin can set defaults for every user in `/etc/dictate/config`, the same `KEY="value"` lines as the user's file, which wins over it.

`paste` and `type` press keys through [ydotool](https://github.com/ReimuNotMoe/ydotool) 1.0 or later, which needs write access to `/dev/uinput`. Installing `dictate-uinput` grants it to the user at the seat; it is separate because that access is a choice.

## Use

Press your language's shortcut, speak, press it again. The tray icon is red while recording and amber while transcribing. `dictate cancel` stops without transcribing.

## Build from source

```sh
make lint test   # linters and unit tests
make deb         # the three packages, into each app's dist/
make deb-check   # lintian, then install, upgrade and purge in Ubuntu containers
```

How the code is laid out and tested: [docs/development.md](docs/development.md).

## License

[GPL-3.0-or-later](LICENSE).
