<p align="center"><img src="docs/logo.svg" width="120" alt="dictate logo"></p>

<h1 align="center">dictate</h1>

<p align="center">
Speak into any text field on GNOME.
</p>

<p align="center">
<a href="https://github.com/jvrsantacruz/dictate/actions/workflows/ci.yml"><img src="https://github.com/jvrsantacruz/dictate/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://github.com/jvrsantacruz/dictate/releases/latest"><img src="https://img.shields.io/github/v/release/jvrsantacruz/dictate" alt="Latest release"></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/jvrsantacruz/dictate" alt="License: GPL-3.0-or-later"></a>
</p>

- **Local.** Speech is transcribed on your machine by [whisper.cpp](https://github.com/ggml-org/whisper.cpp).
- **Into the right field.** An IBus input method inserts the text into the input that had focus when you started. When nothing is in focus the text is saved in the clipboard.
- **Status at a glance**: a tray icon that blinks while recording, and an optional tmux segment.

Runs on Ubuntu 24.04 or later, GNOME on Wayland.

## Install

From the apt repository, which keeps it up to date with the rest of the system, upgrades by
unattended-upgrades included:

```sh
sudo curl -fsSLo /etc/apt/sources.list.d/dictate.sources \
  https://jvrsantacruz.github.io/dictate/dictate.sources
sudo apt update && sudo apt install dictate dictate-indicator
```

The file names the repository and holds its signing key, fingerprint
`0236 18A8 42F3 2549 E1A7  A820 2AB0 8318 A522 3B11`. Check it with:

```sh
sed -n '/BEGIN PGP/,/END PGP/s/^ \.\{0,1\}//p' /etc/apt/sources.list.d/dictate.sources | gpg --show-keys
```

Or download the `.deb` files from the
[latest release](https://github.com/jvrsantacruz/dictate/releases/latest) and
`sudo apt install ./dictate_*.deb ./dictate-indicator_*.deb`.

### A transcriber

dictate sends audio to a whisper server on `http://127.0.0.1:8081`. Ubuntu 26.04 packages one:

```sh
sudo apt install whisper.cpp
mkdir -p ~/.local/share/whisper ~/.config/systemd/user
curl -fsSLo ~/.local/share/whisper/ggml-base-q5_1.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin
tee ~/.config/systemd/user/whisper-server.service >/dev/null <<'UNIT'
[Unit]
Description=whisper.cpp transcription server for dictate

[Service]
ExecStart=/usr/bin/whisper-server -m %h/.local/share/whisper/ggml-base-q5_1.bin --host 127.0.0.1 --port 8081
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
systemctl --user enable --now whisper-server
```

Ubuntu 24.04 has no whisper.cpp package: [build it](https://github.com/ggml-org/whisper.cpp#quick-start),
or use any OpenAI-compatible transcription endpoint, see [Configure](#configure).

## Configure

Once per user, from your desktop session:

```sh
dictate setup
```

It adds the input method, binds <kbd>Super</kbd>+<kbd>I</kbd> to English and <kbd>Super</kbd>+<kbd>E</kbd> to Spanish, writes `~/.config/dictate/config`, and starts the tray icon. It only changes what differs, so run it again after an upgrade or to change a setting. `dictate setup --help` lists every option; `--dry-run` shows the changes without making them.

| Option | Key | Values | Default |
|---|---|---|---|
| `--method` | `DICTATE_METHOD` | `ime` inserts through the input method; `paste` and `type` press keys; `clipboard` only copies | `ime` |
| `--languages` | `DICTATE_LANGUAGES` | whisper language codes, space separated | `en es` |
| `--shortcut LANG=KEYS` | `DICTATE_SHORTCUT_<LANG>` | a GNOME accelerator, such as `<Super>f` | `<Super>i`, `<Super>e` |
| `--notify` | `DICTATE_NOTIFY` | `all`, `failures`, `none` | `failures` |
| `--sound` | `DICTATE_SOUND` | a cue before and after recording, `true` or `false` | `false` |
| `--backend` | `DICTATE_BACKEND` | `local` whisper-server, or `openai` | `local` |
| `--url` | `DICTATE_URL` | the server; `https` unless it is on this machine | `http://127.0.0.1:8081` |
| `--key-cmd` | `DICTATE_KEY_CMD` | a command printing the API key on its first line, for `openai` | none |
| `--max-secs` | `DICTATE_MAX_SECS` | the longest recording | `120` |

Settings are read from three places, each over the one before: `/etc/dictate/config`, which an
admin may write for every user and the package never ships; `~/.config/dictate/config`, which
`dictate setup` writes; and `DICTATE_*` variables in the environment. Both files are
`KEY="value"` lines with the keys above. Running `dictate setup` again keeps what you set before.

`paste` and `type` press keys through [ydotool](https://github.com/ReimuNotMoe/ydotool) 1.0 or
later, which needs write access to `/dev/uinput`. Installing `dictate-uinput` grants it to the
user at the seat. It is a package of its own because that access is a choice: it is a virtual
keyboard for every program that user runs, and it outlasts a switch to another user, so it is not
for a machine people share. `ime`, the default, needs none of it.

### tmux

A notification does not draw over a fullscreen terminal; a tmux segment does. With
[TPM](https://github.com/tmux-plugins/tpm), in `~/.tmux.conf`:

```tmux
set -g @plugin 'jvrsantacruz/dictate'
set -g status-left '#{dictate_status}[#S] '
```

Without TPM, the package ships the same plugin:

```tmux
set -g status-left '#{dictate_status}[#S] '
run-shell /usr/share/dictate/dictate.tmux
```

`#{dictate_status}` works in `status-left` or `status-right`. It is empty when idle, a red
`REC EN 0:07` while recording and an amber spinner while transcribing. Change the colours with
`set -g @dictate-rec-style 'fg=white,bg=red'` and `@dictate-busy-style`. The counter ticks at
your `status-interval`.

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
