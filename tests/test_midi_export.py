import pytest
from mido import MidiFile, bpm2tempo

from track_arranger.arrangement import build_arrangement
from track_arranger.midi_export import export_midi


@pytest.mark.parametrize("bpm", [160, 174, 180])
def test_midi_structure(tmp_path, bpm):
    out = tmp_path / "arrangement.mid"
    sections = build_arrangement()
    export_midi(sections, bpm, out)
    midi = MidiFile(out)
    assert midi.type == 1
    assert len(midi.tracks) == 8
    ticks_per_bar = midi.ticks_per_beat * 4
    assert midi.tracks[0].name == "Sections"
    tempos = [m for m in midi.tracks[0] if m.type == "set_tempo"]
    assert len(tempos) == 1
    assert tempos[0].tempo == bpm2tempo(bpm)
    signatures = [m for m in midi.tracks[0] if m.type == "time_signature"]
    assert [(m.numerator, m.denominator) for m in signatures] == [(4, 4)]
    tick = 0
    markers = []
    for message in midi.tracks[0]:
        tick += message.time
        if message.type == "marker":
            markers.append((message.text, tick))
    assert markers == [(s.name, (s.start_bar - 1) * ticks_per_bar) for s in sections]
    assert tick == 192 * ticks_per_bar

    for section, track in zip(sections, midi.tracks[1:]):
        assert track.name == section.name
        tick = 0
        notes = []
        for message in track:
            tick += message.time
            if message.type in ("note_on", "note_off"):
                notes.append((message.type, tick, message.note))
        start = (section.start_bar - 1) * ticks_per_bar
        end = start + section.bars * ticks_per_bar
        assert notes == [("note_on", start, 60), ("note_off", end, 60)]
    assert midi.length == pytest.approx(192 * 4 * 60 / bpm, abs=0.001)
