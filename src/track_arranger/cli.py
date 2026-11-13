import argparse
from pathlib import Path

from track_arranger.arrangement import (
    bars_to_seconds, build_arrangement, format_time, validate_bpm,
)
from track_arranger.midi_export import export_midi
from track_arranger.tips import TIPS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a rule-based DnB arrangement and MIDI scaffold (4/4)."
    )
    parser.add_argument("--bpm", type=float, default=174, help="160–180 (default: 174)")
    parser.add_argument("--out", type=Path, required=True, help="output .mid file path")
    args = parser.parse_args()
    try:
        validate_bpm(args.bpm)
    except ValueError as error:
        parser.error(str(error))
    if args.out.suffix.lower() != ".mid":
        parser.error("Output path must end in .mid.")

    sections = build_arrangement()
    try:
        export_midi(sections, args.bpm, args.out)
    except OSError as error:
        parser.exit(1, f"Could not write MIDI to {args.out}: {error}\n")

    print(f"Track Arranger | Drum and bass | {args.bpm:g} BPM | 4/4")
    print(f"{'Section':<12} {'Bars':>4} {'Start bar':>10} {'Start time':>11}")
    for section in sections:
        time = format_time(section.start_seconds(args.bpm))
        print(f"{section.name:<12} {section.bars:>4} {section.start_bar:>10} {time:>11}")
        for tip in TIPS["dnb"][section.name]:
            print(f"  - {tip}")
    total_bars = sum(section.bars for section in sections)
    duration = format_time(bars_to_seconds(total_bars, args.bpm))
    print(f"Total: {total_bars} bars | {duration}")
    print(f"MIDI written to {args.out}")


if __name__ == "__main__":
    main()
