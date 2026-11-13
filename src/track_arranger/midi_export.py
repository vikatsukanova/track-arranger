from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from track_arranger.arrangement import BEATS_PER_BAR, Section, validate_bpm


def export_midi(sections: list[Section], bpm: float, out: Path) -> None:
    validate_bpm(bpm)
    midi = MidiFile(type=1, ticks_per_beat=480)
    ticks_per_bar = midi.ticks_per_beat * BEATS_PER_BAR
    conductor = MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(MetaMessage("track_name", name="Sections"))
    conductor.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm)))
    conductor.append(MetaMessage("time_signature", numerator=4, denominator=4))

    previous_tick = 0
    for section in sections:
        start_tick = (section.start_bar - 1) * ticks_per_bar
        conductor.append(MetaMessage(
            "marker", text=section.name, time=start_tick - previous_tick
        ))
        previous_tick = start_tick

        placeholder = MidiTrack()
        midi.tracks.append(placeholder)
        placeholder.append(MetaMessage("track_name", name=section.name))
        placeholder.append(Message("note_on", note=60, velocity=1, time=start_tick))
        placeholder.append(Message(
            "note_off", note=60, velocity=0, time=section.bars * ticks_per_bar
        ))
        placeholder.append(MetaMessage("end_of_track"))

    end_tick = max(
        ((section.start_bar - 1 + section.bars) * ticks_per_bar for section in sections),
        default=0,
    )
    conductor.append(MetaMessage("end_of_track", time=end_tick - previous_tick))
    midi.save(out)
