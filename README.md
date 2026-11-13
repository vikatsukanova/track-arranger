# Track Arranger

A free, open-source, local desktop app for drum & bass producers stuck on an 8-bar loop. Bring your loops, shape a suggested arrangement, and finish in your DAW. No AI, accounts, paid APIs, or runtime network services.

## Features

- Drop WAV, AIFF or MP3 loops; detect and edit BPM, key and length in 4/4 bars. Detection is approximate, especially for percussion and half-time loops.
- Start from Intro → Build → Drop 1 → Breakdown → Build 2 → Drop 2 → Outro, with section tips.
- Reorder sections, resize in 8-bar steps, add/remove sections, and place loops on lanes. Keyboard controls offer the same edits. Loops repeat to fill their section.
- Accept, modify or skip rule-based suggestions. Nothing fills your song automatically.
- Export an Ableton `.als` project with copied, tempo-aligned samples and section locators; Logic gets full-length stereo lane WAVs and section MIDI. Plain MIDI export remains available.
- Dark UI; the current workspace saves on this device. Imported audio stays in the app cache. Export projects to keep durable copies.

> Screenshot placeholder — desktop arrangement workspace.

## Install (macOS 12+)

Download the `.dmg` from [Releases](https://github.com/vikatsukanova/track-arranger/releases): **arm64** for Apple Silicon, **x64** for Intel. Open it and drag Track Arranger into Applications.

Builds are ad-hoc signed, not notarized. On first launch use **Control-click > Open**, or **System Settings > Privacy & Security > Open Anyway**. Windows packaging is planned later. Release artifacts are built on `v*` tags; native macOS and DAW opening checks still require a Mac.

## Development

Requires Python 3.12, Node 22+, Rust stable and [Tauri 2 prerequisites](https://v2.tauri.app/start/prerequisites/). From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[desktop,dev]'
npm ci --prefix app
python scripts/build_sidecar.py
cd app
npm run tauri dev
```

Rebuild the sidecar after Python changes. For browser-only development, run `TRACK_ARRANGER_TOKEN=dev-local TRACK_ARRANGER_PORT=8765 python -m track_arranger.api`, then `VITE_BACKEND_TOKEN=dev-local npm run dev --prefix app` in another terminal. Use loop files of at most 120 seconds / 100 MB. BPM edits recalculate loop bars; bar edits control stretching to the project tempo. Key is informational; no pitch shifting is applied.

```sh
pytest -q
npm test --prefix app
npm run build --prefix app
# Existing CLI (no desktop dependencies required):
track-arranger --help
```

Exports copy audio and never change source files. Logic lane files start at bar 1, include silence, and are already timed: disable Smart Tempo / automatic tempo following when importing. Large arrangements can take time and disk space to render. Ableton import compatibility needs testing in Live; XML structure tests alone cannot guarantee compatibility across Live versions.

MIT licensed. See [LICENSE](LICENSE).
