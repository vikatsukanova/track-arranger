import gzip
from xml.etree import ElementTree as ET

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from pydantic import ValidationError

from track_arranger.analysis import guess_role
from track_arranger.api import create_app
from track_arranger.desktop_models import Loop, Placement, Project, TimelineSection, Variation
from track_arranger.placement import place_loop
from track_arranger.variations import render


@pytest.fixture
def tone(tmp_path):
    sr = 8000
    t = np.arange(sr) / sr
    y = .5 * np.sin(2 * np.pi * 60 * t)
    path = tmp_path / 'tone.wav'
    sf.write(path, y, sr)
    return path


def loop():
    return Loop(id='tone', filename='tone.wav', bpm=174, key='C major', bars=1, seconds=240/174, role='Drop')


def test_guess_direction():
    sr = 22050
    t = np.arange(sr * 3) / sr
    quiet = .01 * np.sin(2 * np.pi * 900 * t)
    loud = .5 * np.sin(2 * np.pi * 60 * t)
    for start in range(0, len(t)-300, sr//4):
        loud[start:start+300] += np.sin(np.arange(300) * 2*np.pi*2000/sr) * np.exp(-np.arange(300)/40)
    assert guess_role(loud, sr) == 'Drop'
    assert guess_role(quiet, sr) == 'Intro'


def test_role_required_and_placement():
    payload = loop().model_dump()
    del payload['role']
    with pytest.raises(ValidationError):
        Loop(**payload)
    sections = [TimelineSection(id=str(i), name=name, bars=8) for i, name in enumerate(['Intro','Build','Drop 1','Breakdown','Build 2','Drop 2','Outro'])]
    for role, expected in [('Drop', [2,5]), ('Intro',[0]), ('Build',[1]), ('Breakdown',[3]), ('Other',[])]:
        result = place_loop(sections, loop().model_copy(update={'role':role}))
        assert [i for i,s in enumerate(result) if s.clips] == expected
    occupied = place_loop(sections, loop())
    assert place_loop(occupied, loop().model_copy(update={'id':'second'})) == occupied
    assert all(not s.clips for s in sections)


@pytest.mark.parametrize('kind', ['Full','Low-pass','High-pass','Filter sweep','Quieter','Fade'])
def test_variation_length_and_audio(tmp_path, tone, kind):
    destination = tmp_path / 'render.wav'
    render(tone, destination, 8, 174, 1, Variation(kind=kind))
    data, sr = sf.read(destination)
    assert len(data) == round(8*240/174*sr)
    assert np.all(np.isfinite(data))
    assert np.any(data)


def test_audio_auth_and_confirm_required(tmp_path, tone):
    cache = tmp_path / 'cache'
    client = TestClient(create_app(cache, 'secret'))
    assert client.get('/audio/tone').status_code == 401
    client.headers['Authorization'] = 'Bearer secret'
    assert client.get('/audio/unknown').status_code == 404
    (cache / 'tone.wav').write_bytes(tone.read_bytes())
    response = client.get('/audio/tone')
    assert response.status_code == 200
    assert response.content[:4] == b'RIFF'
    assert response.headers['content-type'] == 'audio/wav'
    aligned = client.get('/audio/tone?bpm=174&bars=1')
    import io
    assert sf.info(io.BytesIO(aligned.content)).frames == round(240/174*8000)
    assert client.get('/audio/tone?bpm=0').status_code == 422
    project = Project(loops=[loop()], sections=[TimelineSection(id='intro', name='Intro', bars=8)])
    payload = project.model_dump()
    del payload['loops'][0]['role']
    assert client.post('/suggestions/intro', json=payload).status_code == 422
    request = dict(loop=loop().model_dump(), bars=8, bpm=174, variation=Variation(kind='Quieter', gain=.2).model_dump())
    bad = {**request, 'loop': {k:v for k,v in request['loop'].items() if k != 'role'}}
    assert client.post('/variations', json=bad).status_code == 422
    rendered = client.post('/variations', json=request).json()
    assert (cache / f"{rendered['id']}.wav").exists()
    # Rendering an audition does not place it; only the explicitly accepted clip exports.
    for accepted in (False, True):
        project.loops = [loop(), Loop(**rendered)]
        project.sections[0].clips = [Placement(lane='Loop', loop_id=rendered['id'])] if accepted else []
        payload = project.model_dump()
        for format in ('logic', 'ableton'):
            response = client.post('/export', json={'project':payload, 'format':format,'directory':str(tmp_path)})
            assert response.status_code == 200, response.text
            from pathlib import Path
            out = Path(response.json()['path'])
            if format == 'logic':
                assert bool(list(out.glob('*.wav'))) == accepted
                assert (out / 'Sections.mid').exists()
            else:
                with gzip.open(out / 'Arrangement.als') as stream:
                    root = ET.parse(stream)
                assert bool(root.findall('.//AudioClip')) == accepted
            if accepted:
                copied = out / 'Samples/Imported' / f"{rendered['id']}-original.wav"
                assert copied.read_bytes() == (cache / f"{rendered['id']}.wav").read_bytes()


def test_sweep_opens_and_outro_fades(tmp_path):
    sr = 8000
    count = round(8 * 240 / 174 * sr)
    t = np.arange(count) / sr
    source = tmp_path / 'bright.wav'
    sf.write(source, .4 * np.sin(2 * np.pi * 2000 * t), sr, subtype='FLOAT')
    sweep = tmp_path / 'sweep.wav'
    render(source, sweep, 8, 174, 8, Variation(kind='Filter sweep', cutoff=300, gain=1))
    audio, _ = sf.read(sweep)
    rms = lambda data: np.sqrt(np.mean(data ** 2))
    assert rms(audio[-sr:]) > rms(audio[:sr]) * 3
    fade = tmp_path / 'fade.wav'
    render(source, fade, 8, 174, 8, Variation(kind='Fade', cutoff=500, gain=.5))
    audio, _ = sf.read(fade)
    assert rms(audio[-sr//4:]) < rms(audio[:sr//4]) * .1
    assert abs(audio[-1]) < 1e-8


def test_trim_exact_bars_and_original_toggle(tmp_path):
    from track_arranger.audio import read_loop
    sr, bpm, bars = 8000, 174, 2
    count = round(bars * 240 / bpm * sr)
    tone = .4 * np.cos(2 * np.pi * 120 * np.arange(count) / sr)
    original = np.concatenate([np.zeros(sr//2), tone, np.zeros(sr*2)])
    source = tmp_path / 'padded.wav'
    sf.write(source, original, sr, subtype='FLOAT')
    before = source.read_bytes()
    trimmed, _ = read_loop(source, bpm, bars, True)
    untrimmed, _ = read_loop(source, bpm, bars, False)
    assert len(trimmed) == count
    assert len(untrimmed) == len(original)
    np.testing.assert_allclose(trimmed[:, 0], tone, atol=1e-7)
    assert source.read_bytes() == before
    # Authenticated preview uses the same toggle and never changes the source.
    cache = tmp_path / 'cache'
    client = TestClient(create_app(cache, 'secret'))
    client.headers['Authorization'] = 'Bearer secret'
    (cache / 'padded.wav').write_bytes(before)
    import io
    for trim, expected in [(True,count),(False,len(original))]:
        result = client.get(f'/audio/padded?bars={bars}&source_bpm={bpm}&trim_to_bars={str(trim).lower()}')
        assert result.status_code == 200
        assert sf.info(io.BytesIO(result.content)).frames == expected
        aligned = client.get(f'/audio/padded?bpm={bpm}&bars={bars}&source_bpm={bpm}&trim_to_bars={str(trim).lower()}')
        assert sf.info(io.BytesIO(aligned.content)).frames == expected
    assert (cache / 'padded.wav').read_bytes() == before


def test_analysis_ignores_trailing_silence_for_bar_count(tmp_path):
    from track_arranger.analysis import analyze
    sr, bpm, bars = 22050, 172, 8
    count = round(bars * 240 / bpm * sr)
    data = np.zeros(count)
    click = np.cos(np.arange(440) * 2*np.pi*1000/sr) * np.exp(-np.arange(440)/60)
    for beat in range(32):
        start = round(beat * 60/bpm*sr)
        data[start:start+len(click)] += click
    path = tmp_path / 'padded-click.wav'
    sf.write(path, np.concatenate([np.zeros(sr//2),data,np.zeros(sr*2)]),sr)
    metadata = analyze(path)
    assert abs(metadata['bpm'] - bpm) < 3
    assert metadata['bars'] == bars


def test_import_caches_trimmed_and_original_audio(tmp_path):
    sr = 8000
    source = tmp_path / 'source.wav'
    t = np.arange(sr * 3) / sr
    sf.write(source, np.concatenate([np.zeros(sr//2), .4*np.cos(2*np.pi*120*t), np.zeros(sr*2)]), sr)
    before = source.read_bytes()
    cache = tmp_path / 'cache'
    client = TestClient(create_app(cache, 'secret'))
    client.headers['Authorization'] = 'Bearer secret'
    result = client.post('/loops/import', json={'paths':[str(source)]})
    assert result.status_code == 200
    loop = result.json()[0]
    assert loop['trim_to_bars'] is True
    assert sf.info(cache / f"{loop['id']}.wav").frames == round(loop['bars']*240/loop['bpm']*sr)
    assert sf.info(cache / f"{loop['id']}-raw.wav").frames == len(t) + sr//2 + sr*2
    assert source.read_bytes() == before


def test_trim_toggle_controls_export_loop_length(tmp_path):
    from track_arranger.desktop_export import prepared_loops, SR
    sr, bpm, bars = 8000, 174, 2
    count = round(bars * 240 / bpm * sr)
    source = tmp_path / 'padded.wav'
    sf.write(source, np.concatenate([.4*np.cos(2*np.pi*120*np.arange(count)/sr), np.zeros(sr*2)]), sr)
    for trim in (True, False):
        item = loop().model_copy(update={'bpm':bpm,'bars':bars,'trim_to_bars':trim})
        project = Project(bpm=bpm, loops=[item], sections=[TimelineSection(id='drop',name='Drop 1',bars=8,clips=[Placement(lane='Loop',loop_id=item.id)])])
        prepared = prepared_loops(project,{item.id:source},tmp_path / str(trim))
        data = prepared[item.id][1]
        if trim:
            assert len(data) == round(bars*240/bpm*SR)
            assert np.sqrt(np.mean(data[-SR:]**2)) > .1
        else:
            assert abs(len(data) - round((count/sr + 2)*SR)) <= 1
            assert np.max(np.abs(data[-SR:])) < 1e-4
