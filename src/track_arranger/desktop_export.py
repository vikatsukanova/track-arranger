import gzip
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import librosa
import numpy as np
import soundfile as sf

from track_arranger.arrangement import Section
from track_arranger.desktop_models import Project
from track_arranger.audio import read_loop
from track_arranger.midi_export import export_midi

SR = 44100


def sections(project):
    start = 1
    result = []
    for section in project.sections:
        result.append(Section(section.name, section.bars, start))
        start += section.bars
    return result


def safe_name(name):
    return re.sub(r'[^\w -]', '_', name)[:64] or 'Lane'


def prepared_loops(project: Project, sources: dict[str, Path], out: Path):
    audio = out / 'Samples' / 'Imported'
    audio.mkdir(parents=True)
    used = {c.loop_id for s in project.sections for c in s.clips}
    metadata = {loop.id: loop for loop in project.loops}
    prepared = {}
    for loop_id in sorted(used):
        loop = metadata[loop_id]
        source = sources[loop_id]
        data, rate = read_loop(source, loop.bpm, loop.bars, loop.trim_to_bars)
        if rate != SR:
            data = librosa.resample(data.T, orig_sr=rate, target_sr=SR).T
        if data.shape[1] > 2:
            raise ValueError('Only mono and stereo loops are supported')
        target = round(loop.bars * 240 / project.bpm * SR) if loop.trim_to_bars else round(len(data) * loop.bpm / project.bpm)
        stretched = librosa.effects.time_stretch(data.T, rate=len(data) / target).T
        stretched = librosa.util.fix_length(stretched, size=target, axis=0)
        dest = audio / f'{loop_id}.wav'
        sf.write(dest, stretched, SR, subtype='PCM_24')
        shutil.copy2(source, audio / f'{loop_id}-original{source.suffix}')
        prepared[loop_id] = (dest, stretched)
    return prepared


def export_logic(project: Project, sources: dict[str, Path], out: Path):
    prepared = prepared_loops(project, sources, out)
    total = round(sum(s.bars for s in project.sections) * 240 / project.bpm * SR)
    lanes = sorted({c.lane for s in project.sections for c in s.clips})
    for index, lane in enumerate(lanes):
        dest = out / f'{index + 1:02}-{safe_name(lane)}.wav'
        with sf.SoundFile(dest, 'w', samplerate=SR, channels=2, subtype='PCM_24') as stream:
            start_bar = 0
            for section in project.sections:
                start = round(start_bar * 240 / project.bpm * SR)
                end = round((start_bar + section.bars) * 240 / project.bpm * SR)
                clip = next((c for c in section.clips if c.lane == lane), None)
                data = prepared[clip.loop_id][1] if clip else None
                # Stream a lane in chunks instead of holding a song in memory.
                for offset in range(0, end - start, SR * 10):
                    count = min(SR * 10, end - start - offset)
                    chunk = np.zeros((count, 2), dtype=np.float32) if data is None else data[(np.arange(count) + offset) % len(data)]
                    if chunk.shape[1] == 1:
                        chunk = np.repeat(chunk, 2, axis=1)
                    stream.write(chunk)
                start_bar += section.bars
            assert stream.tell() == total
    export_midi(sections(project), project.bpm, out / 'Sections.mid')
    (out / 'README.txt').write_text(
        f'Track Arranger — Logic import\nSet project tempo to {project.bpm} BPM and meter to 4/4.\n'
        'Drag the numbered WAV files onto separate audio tracks, all starting at bar 1.\n'
        'Disable automatic tempo following / Smart Tempo for these already timed files.\n'
        'Import Sections.mid for section markers. All lanes include silence and have the same full song length.\n'
        'Samples/Imported contains source copies and tempo-aligned loops.\n', encoding='utf-8')


def node(parent, tag, value=None, **attrs):
    if value is not None:
        attrs['Value'] = str(value)
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


def export_ableton(project: Project, sources: dict[str, Path], out: Path):
    from track_arranger.ableton_schema import clip_defaults, live_defaults, mixer_defaults, routing, sequencer, track_defaults
    prepared = prepared_loops(project, sources, out)
    root = ET.Element('Ableton', MajorVersion='5', MinorVersion='11.0_11300', SchemaChangeCount='3', Creator='Ableton Live 11.3.0', Revision='')
    live = node(root, 'LiveSet')
    node(live, 'NextPointeeId', 100000)
    node(live, 'OverwriteProtectionNumber', 2816)
    tracks = node(live, 'Tracks')
    lanes = sorted({c.lane for s in project.sections for c in s.clips})
    for index, lane in enumerate(lanes):
        track = node(tracks, 'AudioTrack', Id=index + 1)
        track_defaults(track, lane, index * 5)
        chain = node(track, 'DeviceChain')
        mixer_defaults(chain, index)
        routing(chain, 'AudioInputRouting', 'AudioIn/External/S0', 'Ext. In', '1/2')
        routing(chain, 'MidiInputRouting', 'MidiIn/None', 'No Input')
        routing(chain, 'AudioOutputRouting', 'AudioOut/Master', 'Master')
        routing(chain, 'MidiOutputRouting', 'MidiOut/None', 'No Output')
        events = sequencer(chain, index)
        start = 0
        clip_index = 0
        for section in project.sections:
            placement = next((c for c in section.clips if c.lane == lane), None)
            if placement:
                path, data = prepared[placement.loop_id]
                loop = next(l for l in project.loops if l.id == placement.loop_id)
                loop_beats = len(data) / SR * project.bpm / 60
                if loop.trim_to_bars or abs(loop_beats - loop.bars * 4) < project.bpm / 60 / SR:
                    loop_beats = loop.bars * 4
                beat = start * 4.0
                remaining = section.bars * 4.0
                while remaining > 1e-8:
                    duration = min(loop_beats, remaining)
                    clip = node(events, 'AudioClip', Id=clip_index, Time=beat)
                    clip_index += 1
                    for tag, value in [('Name', loop.filename), ('CurrentStart', beat), ('CurrentEnd', beat + duration),
                                       ('IsWarped', 'true'), ('Disabled', 'false'), ('Color', index * 5), ('Sync', 'false')]:
                        node(clip, tag, value)
                    loop_node = node(clip, 'Loop')
                    for tag, value in [('LoopStart', 0), ('LoopEnd', duration), ('StartRelative', 0), ('LoopOn', 'false'), ('OutMarker', duration), ('HiddenLoopStart', 0), ('HiddenLoopEnd', duration)]:
                        node(loop_node, tag, value)
                    clip_defaults(clip, loop_beats, len(data) / SR)
                    ref = node(node(clip, 'SampleRef'), 'FileRef')
                    node(ref, 'RelativePathType', 3)
                    node(ref, 'RelativePath', path.relative_to(out).as_posix())
                    node(ref, 'Path', str(path.resolve()))
                    node(ref, 'Type', 1)
                    node(ref, 'LivePackName', '')
                    node(ref, 'LivePackId', '')
                    sample = clip.find('SampleRef')
                    node(sample, 'LastModDate', 0)
                    node(sample, 'SourceContext')
                    node(sample, 'SampleUsageHint', 0)
                    node(sample, 'DefaultDuration', len(data))
                    node(sample, 'DefaultSampleRate', SR)
                    node(clip, 'SampleVolume', 1)
                    node(clip, 'PitchCoarse', 0)
                    node(clip, 'PitchFine', 0)
                    beat += duration
                    remaining -= duration
            start += section.bars
        node(node(chain, 'DeviceChain'), 'Devices')
    master = node(live, 'MasterTrack')
    track_defaults(master, 'Master', 0)
    master_chain = node(master, 'DeviceChain')
    mixer = mixer_defaults(master_chain, 100, master=True)
    mixer.find('Tempo/Manual').set('Value', str(project.bpm))
    routing(master_chain, 'AudioOutputRouting', 'AudioOut/External/S0', 'Ext. Out', '1/2')
    node(node(master_chain, 'DeviceChain'), 'Devices')
    preview = node(live, 'PreHearTrack')
    track_defaults(preview, 'Cue', 0)
    preview_chain = node(preview, 'DeviceChain')
    mixer_defaults(preview_chain, 101)
    routing(preview_chain, 'AudioOutputRouting', 'AudioOut/External/S0', 'Ext. Out', '1/2')
    node(node(preview_chain, 'DeviceChain'), 'Devices')
    live_defaults(live, sum(s.bars for s in project.sections) * 4)
    locators = node(node(live, 'Locators'), 'Locators')
    for i, section in enumerate(sections(project)):
        locator = node(locators, 'Locator', Id=i)
        node(locator, 'Time', (section.start_bar - 1) * 4)
        node(locator, 'Name', section.name)
        node(locator, 'Annotation', '')
        node(locator, 'IsSongStart', str(i == 0).lower())
    node(live, 'ViewStateSesstionTrackWidth', 93)
    with gzip.open(out / 'Arrangement.als', 'wb') as stream:
        stream.write(ET.tostring(root, encoding='utf-8', xml_declaration=True))
