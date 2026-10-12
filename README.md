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

- **Local, or hosted if you choose.** Speech is transcribed on your machine by [whisper.cpp](https://github.com/ggml-org/whisper.cpp), or by an OpenAI-compatible service you configure, with the local server as fallback when it fails. See [Hosted transcription](#hosted-transcription).
- **Into the right field.** An IBus input method inserts the text into the input that had focus when you started. When nothing is in focus the text is saved in the clipboard.
- **Text while you speak.** The recording is transcribed piece by piece at each pause, and each piece shows in the field, underlined, until you stop. Then the whole recording is transcribed once more, so the text typed reads as one stream.
- **Nothing lost.** An optional log keeps every dictated text on your machine, readable with `dictate log`.
- GNOME tray icon and status.

<p align="center"><img src="docs/tray.png" width="330" alt="The GNOME top bar while recording: a red dot, EN and 0:12"></p>

Runs on Ubuntu 24.04 or later, GNOME on Wayland.

## Install

From the apt repository, which keeps it up to date with the rest of the system, upgrades by
unattended-upgrades included. On Ubuntu 26.04 or later, with a local transcriber:

```sh
sudo curl -fsSLo /etc/apt/sources.list.d/dictate.sources https://jvrsantacruz.github.io/dictate/dictate.sources && sudo apt update && sudo apt install dictate dictate-indicator dictate-whisper && dictate setup
```

`dictate-whisper` runs [whisper.cpp](https://github.com/ggml-org/whisper.cpp)'s server on
`127.0.0.1:8081` with the multilingual base model and a voice activity model, as a user service
that `dictate setup` enables. It is optional: leave it out on Ubuntu 24.04, which has no whisper.cpp package, or to
use a transcriber of your own, any whisper server or OpenAI-compatible endpoint, see
[Configure](#configure):

```sh
sudo curl -fsSLo /etc/apt/sources.list.d/dictate.sources https://jvrsantacruz.github.io/dictate/dictate.sources && sudo apt update && sudo apt install dictate dictate-indicator && dictate setup
```

Or download the `.deb` files from the
[latest release](https://github.com/jvrsantacruz/dictate/releases/latest) and
`sudo apt install ./dictate_*.deb ./dictate-indicator_*.deb`.

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
| `--url` | `DICTATE_URL` | the server; for `openai`, the API's base URL; `https` unless it is on this machine | `http://127.0.0.1:8081` |
| `--model` | `DICTATE_MODEL` | the model, for `openai` | `whisper-1` |
| `--key-cmd` | `DICTATE_KEY_CMD` | a command printing the API key on its first line, for `openai` | none |
| `--fallback-url` | `DICTATE_FALLBACK_URL` | a whisper-server to use when the backend fails or is slow | none |
| `--max-secs` | `DICTATE_MAX_SECS` | the longest recording | `120` |
| `--stream` | `DICTATE_STREAM` | transcribe at each pause while recording, shown as you speak; `true` or `false` | `true` |
| `--log` | `DICTATE_LOG` | keep every dictated text in `~/.local/state/dictate/log`, `true` or `false` | `false` |
| `--log-days` | `DICTATE_LOG_DAYS` | days the log keeps a text | `30` |

Settings are read from three places, each over the one before: `/etc/dictate/config`, which an
admin may write for every user and the package never ships; `~/.config/dictate/config`, which
`dictate setup` writes; and `DICTATE_*` variables in the environment. Both files are
`KEY="value"` lines with the keys above. Running `dictate setup` again keeps what you set before.

An upgrade restarts what runs for every user: the input method, the tray icon and the
`dictate-whisper` server, never one that was stopped. `DICTATE_RESTART="false"` in
`/etc/dictate/config` leaves the new version for the next login instead.

The log is yours alone (mode 0600). One line per dictation with its final text: time, language, outcome and text, where the
outcome is `delivered`, or `clipboard` when focus moved. Dictation never records
while a password or PIN field has focus, so nothing from one is sent, logged or shown.

`paste` and `type` press keys through [ydotool](https://github.com/ReimuNotMoe/ydotool) 1.0 or
later, which needs write access to `/dev/uinput`. Installing `dictate-uinput` grants it to the
user at the seat. It is a package of its own because that access is a choice: it is a virtual
keyboard for every program that user runs, and it outlasts a switch to another user, so it is not
for a machine people share. `ime`, the default, needs none of it.

### Hosted transcription

A hosted model can be more accurate and faster than the local one. Your voice is then sent to
that service, so choose one whose data policy you accept. For example, whisper-large-v3-turbo on
[DeepInfra](https://deepinfra.com), with the local server as fallback:

```sh
dictate setup --backend openai --url https://api.deepinfra.com/v1/openai \
  --model openai/whisper-large-v3-turbo --key-cmd "head -1 $HOME/.config/dictate/deepinfra.key" \
  --fallback-url http://127.0.0.1:8081
```

`--url` is the API's base URL, as OpenAI's own clients take it: `https://api.openai.com/v1`
works the same way. The key is never written to the config: the command prints it, once per
dictation. A request that fails, or that waits on the network longer than 5 s plus a quarter of
the recording's length, goes to the fallback server instead, and a notification says why.

Silence before and after speech is cut before sending, so whisper does not turn it into words.
With streaming on, each piece is sent while you speak and the whole recording again at the end,
so the service bills about twice your speaking time; `--stream false` sends it once.

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

Press your language's shortcut, speak, press it again. The tray icon is red while recording and amber while transcribing. With the `ime` method the text shows in the field as you speak, underlined until you stop; typing a key or moving focus takes it off. `dictate cancel` stops without transcribing. `dictate log` prints the last 20 texts, `dictate log 50` the last 50.

If no transcriber can be reached, the recording is not lost: it is kept in
`~/.local/state/dictate/`, readable only by you, and `dictate retry` transcribes it later and puts
the text on the clipboard. Only the last failed recording is kept, and a successful retry deletes
it.

## Build from source

```sh
make lint test   # linters and unit tests
make deb         # the four packages, into each app's dist/
make deb-check   # lintian, then install, upgrade and purge in Ubuntu containers
```

How the code is laid out and tested: [docs/development.md](docs/development.md).

## License

[GPL-3.0-or-later](LICENSE).
