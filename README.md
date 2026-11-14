# Mouse & Keyboard Activity Recorder V1.6 · Clara

> A zero-dependency Windows desktop tool built purely on `ctypes`, `tkinter`, and the Python standard library.
> Microsecond-resolution recording, sub-100 µs replay injection.

**English** | [简体中文](README.zh-CN.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

---

## Overview

Clara records global mouse and keyboard activity and replays it with high timing
fidelity. It talks to the operating system exclusively through `ctypes` — no
third-party packages, no service, no network access.

The hard part of an input recorder is not capturing events, it is capturing them
at the *right time*. Windows hook callbacks carry a random 0–several-ms dispatch
delay, and `SendInput` replays are limited by the default timer resolution and
scheduler jitter. Clara attacks both sides: a dual-clock fusion algorithm for
recording, and a safe-sleep + spin hybrid for replay.

## Features

| Feature | Description |
|---|---|
| **Global recording** | Microsecond-resolution capture of mouse movement, button down/up, wheel, and full keyboard events |
| **High-precision replay** | `SendInput` injection with measured wake-up error of ~323 ns average |
| **Speed control** | 0.1×–20× continuous, with modifier-key ordering preserved at every speed |
| **Save / load** | Human-readable JSON recordings with environment metadata |
| **Global hotkeys** | All four actions (start/stop record, start/stop replay) are rebindable |
| **Bilingual UI** | One-click switch between Chinese and English |
| **Auto elevation** | Relaunches itself with administrator rights when needed |
| **Adaptive window** | Sizes itself to its content on first launch, resizable afterwards |

## Quick Start

**Requirements**

- Windows 10 / 11
- Python 3.10 or newer
- Administrator privileges (the app prompts for elevation automatically)
- Optional: `Pillow`, only for the background-image feature

**Run from source**

```bat
run.bat
```

or directly:

```powershell
python -m mkr
```

**Default hotkeys**

| Action | Default |
|---|---|
| Start recording | `F9` |
| Stop recording | `F10` |
| Start replay | `F11` |
| Stop replay | `F12` |

All hotkeys can be changed in the in-app settings window and are stored in
`config.json`.

## Building a Standalone EXE

```powershell
pyinstaller --onefile --windowed --uac-admin ClaraRecorder.spec
```

`installer.py` provides a GUI installer that lets the user choose an install
directory and opt in to desktop / Start Menu shortcuts.

## Project Structure

```
git-practice/
├── run.bat              # Launcher: UAC elevation + detached console
├── entry.py             # PyInstaller entry point
├── installer.py         # GUI installer
├── config.json          # User settings (hotkeys, repeat count, speed)
├── assets/              # Static resources (background image)
├── mkr/                 # Main package
│   ├── winapi.py        # All ctypes / Win32 declarations
│   ├── hooks.py         # Low-level keyboard & mouse hook thread
│   ├── recorder.py      # Recording engine (dual-clock fusion)
│   ├── player.py        # Replay engine (safe sleep + spin + batching)
│   ├── hotkeys.py       # Hotkey parsing and matching
│   ├── config.py        # JSON config I/O with corruption fallback
│   ├── storage.py       # Recording file I/O
│   ├── gui.py           # tkinter UI (i18n, background, auto-sizing)
│   └── app.py           # Assembly: wires every module together
└── tests/               # Unit tests (hooks, recorder, player, hotkeys, config)
```

## How It Works

**Recording — dual-clock fusion** (`recorder.py::_now_ns`)

- `tick` is the millisecond timestamp Windows attaches when the event enters the
  system, which is immune to callback dispatch delay.
- `perf` is taken at the very top of the hook callback, giving sub-millisecond
  resolution inside a single tick.
- Combining them keeps absolute timing accurate while still resolving the order
  of rapid key presses. `timeBeginPeriod(1)` lifts the system timer from ~15.6 ms
  to ~1 ms during recording.

**Replay — safe sleep, then spin** (`player.py::precise_sleep_until`)

- Sleep only to a safety margin (`deadline − 1.5 ms`, then `deadline − 200 µs`)
  and spin for the remainder. Scheduler jitter can only make the last wait
  longer, never late.
- Consecutive events closer than `batch_window_ns` are merged into a single
  `SendInput` call; the window scales with playback speed, so chords such as
  `Ctrl → Shift → A` stay atomic at 20×.
- Garbage collection is disabled and the replay thread is boosted to
  `THREAD_PRIORITY_TIME_CRITICAL` to eliminate random stalls.

**Modifier safety** (`player.py::InjectedState`)

Only keys that this instance injected as *down* but never released are released
on cleanup — never a blanket release that could interfere with keys the user is
physically holding.

## Important Notes

| Item | Reason |
|---|---|
| **Administrator rights are required** | Lower-privilege processes cannot capture input sent to elevated windows, nor inject into them |
| **Recordings are plain JSON** | Readable, editable, portable — but they grow quickly with long sessions |
| **No network access** | Everything stays on the local machine |
| **Injected events are filtered** | `LLKHF_INJECTED` / `LLMHF_INJECTED` prevent the tool from recording its own replay |
| **Kernel-level hooks can block it** | Anti-cheat and similar drivers may refuse or intercept synthetic input |
| **Use responsibly** | Automating input on systems or services you do not own may violate their terms of service |

## Documentation

This file is a concise English summary. The complete technical documentation —
module call graph, startup/record/replay call chains, per-file breakdown, and
the full changelog — is in the Chinese version:

**[完整中文文档 · README.zh-CN.md](README.zh-CN.md)**

## License

Released under the [MIT License](LICENSE).

## Version

Current version: **1.6.0**. See [CHANGELOG](README.zh-CN.md#changelog) for release history.
