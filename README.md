# Track Arranger

Turn a stuck eight-bar loop into a full arrangement plan.

Track Arranger is a free, open-source, non-AI Python command-line tool for
electronic music producers. The MVP focuses on drum and bass: it prints a
section map with original, rule-based production tips and exports a MIDI
scaffold you can build on in your DAW. No account, subscription, API key or
network connection is needed to run it.

It exists as a small, editable alternative to paid arrangement assistants:
a starting structure that leaves the creative decisions with the producer.
Built by Victoria Tsukanova, a senior React/TypeScript developer learning Python.

## Install

Requires Python 3.10 or newer. mido is the only direct runtime dependency
(mido also installs its own dependency, packaging).

Install directly from the repository with pipx for an isolated CLI:

```sh
pipx install git+https://github.com/vikatsukanova/track-arranger.git
```

Or clone and install with pip in a virtual environment:

```sh
git clone https://github.com/vikatsukanova/track-arranger.git
cd track-arranger
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
```

## Use

```sh
track-arranger --bpm 174 --out my-track.mid
# BPM defaults to 174:
track-arranger --out my-track.mid
track-arranger --help
```

Accepts BPM from 160 through 180, including decimals. All sections are in 4/4,
with positive lengths in multiples of eight bars. Bar numbering starts at 1;
elapsed time starts at zero and displays whole seconds rounded down.
The output directory must already exist. An existing output file is overwritten.

Sample output:

```text
Track Arranger | Drum and bass | 174 BPM | 4/4
Section      Bars  Start bar  Start time
Intro          32          1       00:00
  - Keep the drums sparse and steady so a DJ can mix into the track.
  - Tease a small piece of the hook without revealing the full bass.
Build          16         33       00:44
  - Open a filter gradually to make the next section feel wider.
  - Leave a brief gap before the drop so the first kick lands clearly.
Drop 1         32         49       01:06
  - Bring in the full bass and main hook together.
  - Change a drum fill or bass answer every eight bars to keep momentum.
Breakdown      32         81       01:50
  - Pull out the drums and sub bass to let the pads breathe.
  - Keep one familiar motif so the quieter section still feels connected.
Build 2        16        113       02:34
  - Bring back rhythmic tension in layers rather than all at once.
  - Use a different fill to signal that the second drop is approaching.
Drop 2         32        129       02:56
  - Return to the main hook with a new bass response or drum variation.
  - Save one extra texture for the final eight bars of the drop.
Outro          32        161       03:40
  - Remove melodic layers in stages to leave room for the next record.
  - Keep a clear drum pulse for mixing and let effect tails finish cleanly.
Total: 192 bars | 04:24
MIDI written to my-track.mid
```

The fixed 192-bar template is a suggestion, not a rule for every DnB track.
The tool generates structure and advice, not drums, bass lines or audio.

## Bring the MIDI into your DAW

The type-1 MIDI file contains a `Sections` conductor track with tempo, a 4/4
time signature and seven section markers. Each section also gets its own named
track containing one low-velocity C4 note (MIDI note 60; octave names vary by DAW)
at the section's start, held for its entire length.

MIDI has no standard clip-name field. Track names provide portable section
labels; the DAW determines region/clip names and whether MIDI markers become
arrangement markers. The separate tracks are intentional so those labels survive
more import workflows. The placeholder notes are scaffolding: mute them or leave
them without an instrument while producing.

### Logic Pro

1. Open the `.mid` with **File → Open** to create a project from its tempo and
   signature, or drag it into the Tracks area of an existing project at bar 1.
2. If prompted, accept the MIDI tempo information when you want the file's BPM.
   In an existing project, check that the project tempo matches the chosen BPM.
3. Inspect the named MIDI regions/tracks. Show the global Marker track to inspect
   imported markers; import behavior varies by Logic version and workflow.
4. Build your musical parts alongside the placeholders, then mute or remove them.

### Ableton Live

1. Set the project tempo to the chosen BPM and use Arrangement View.
2. Drag the `.mid` from Live's browser or your file manager onto the arrangement
   at bar 1. Allow separate MIDI tracks when prompted for the multitrack file.
3. Use the named section tracks and sustained notes as the structure guide.
   Live may not import MIDI tempo or marker events as tempo/locators; set tempo
   manually and add locators at the printed start bars if needed.
4. Leave placeholder tracks without instruments or mute them, then arrange your
   sounds alongside them. Clip boundaries may include leading silence; the note
   positions and durations are the section boundaries.

DAW import instructions are guidance; this MVP's automated tests verify the MIDI
file contents, not Logic or Live's import UI.

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest
```

- `src/track_arranger/cli.py`: argparse and terminal presentation.
- `arrangement.py`: frozen section dataclass, bar math and data-driven templates.
- `tips.py`: editable original production advice, grouped by genre and section.
- `midi_export.py`: mido export and MIDI delta-time conversion.
- `tests/`: bar/time math, template, tips, CLI validation and MIDI round-trip checks.

To extend the template system, add genre data to `TEMPLATES` and matching `TIPS`,
then introduce genre selection and appropriate tempo validation. Only DnB is
implemented and exposed in this MVP.

## Roadmap

- More subgenres and styles: liquid DnB, neurofunk, dubstep and house.
- Soundtrack templates with different pacing and section structures.
- More arrangement variations and editable templates.
- Maybe a DAW plugin later, while keeping the free CLI available.

## License

[MIT](LICENSE) — copyright 2026 Victoria Tsukanova.
