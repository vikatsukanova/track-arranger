import gzip
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from track_arranger.analysis import analyze
from track_arranger.api import create_app
from track_arranger.desktop_export import SR, export_ableton, export_logic
from track_arranger.desktop_models import Loop, Placement, Project, TimelineSection
from track_arranger.suggestions import suggestions


@pytest.fixture
def click_loop(tmp_path):
    sr = 22050
    bpm = 172
    seconds = 8 * 240 / bpm
    y = np.zeros(round(seconds * sr), dtype=np.float32)
    click = np.sin(np.arange(440) * 2 * np.pi * 1000 / sr) * np.exp(-np.arange(440) / 60)
    for beat in range(32):
        start = round(beat * 60 / bpm * sr)
        y[start:start + len(click)] += click[:len(y) - start]
    path = tmp_path / 'click.wav'
    sf.write(path, y, sr)
    return path


@pytest.fixture
def project(click_loop):
    return Project(bpm=172, loops=[Loop(id='test', filename='click.wav', bpm=172, key='C major', bars=8, seconds=8 * 240 / 172)],
                   sections=[TimelineSection(id='intro', name='Intro', bars=8, clips=[Placement(lane='Drums', loop_id='test')]),
                             TimelineSection(id='build', name='Build', bars=16, clips=[Placement(lane='Bass', loop_id='test')])])


def test_analysis_known_bpm_and_bars(click_loop):
    result = analyze(click_loop)
    assert abs(result['bpm'] - 172) < 3
    assert abs(result['bars'] - 8) < .25
    assert result['seconds'] == pytest.approx(8 * 240 / 172, abs=.01)
    assert result['key'].split()[-1] in {'major', 'minor'}


def test_analysis_tonal_c_major(tmp_path):
    sr = 22050
    t = np.arange(sr * 4) / sr
    y = sum(np.sin(2 * np.pi * hz * t) * amplitude for hz, amplitude in [(261.63, .4), (329.63, .3), (392, .3)])
    path = tmp_path / 'chord.aiff'
    sf.write(path, y, sr)
    assert analyze(path)['key'] == 'C major'


def test_analysis_silent(tmp_path):
    path = tmp_path / 'silence.wav'
    sf.write(path, np.zeros(22050), 22050)
    with pytest.raises(ValueError, match='non-silent'):
        analyze(path)


def test_logic_length_timing_silence_and_source_copy(tmp_path, project, click_loop):
    out = tmp_path / 'logic'
    export_logic(project, {'test': click_loop}, out)
    lanes = sorted(out.glob('*.wav'))
    assert len(lanes) == 2
    expected = round(24 * 240 / 172 * SR)
    for lane in lanes:
        assert sf.info(lane).frames == expected
        assert sf.info(lane).channels == 2
    bass, _ = sf.read(next(out.glob('*Bass.wav')))
    drums, _ = sf.read(next(out.glob('*Drums.wav')))
    boundary = round(8 * 240 / 172 * SR)
    assert np.max(np.abs(bass[:boundary])) == 0
    assert np.max(np.abs(bass[boundary:])) > .1
    assert np.max(np.abs(drums[boundary:])) == 0
    assert (out / 'Samples/Imported/test-original.wav').read_bytes() == click_loop.read_bytes()
    assert (out / 'Sections.mid').is_file()
    assert 'bar 1' in (out / 'README.txt').read_text()


def test_ableton_xml_tempo_locators_and_clips(tmp_path, project, click_loop):
    out = tmp_path / 'ableton'
    export_ableton(project, {'test': click_loop}, out)
    with gzip.open(out / 'Arrangement.als') as stream:
        root = ET.parse(stream).getroot()
    assert root.tag == 'Ableton'
    live = root.find('LiveSet')
    assert float(live.find('MasterTrack/DeviceChain/Mixer/Tempo/Manual').get('Value')) == 172
    assert [float(n.get('Value')) for n in live.findall('Locators/Locators/Locator/Time')] == [0, 32]
    tracks = live.findall('Tracks/AudioTrack')
    assert len(tracks) == 2
    clips = live.findall('Tracks/AudioTrack/DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events/AudioClip')
    assert len(clips) == 3
    assert sorted(float(c.get('Time')) for c in clips) == [0, 32, 64]
    for clip in clips:
        relative = clip.find('SampleRef/FileRef/RelativePath').get('Value')
        assert (out / relative).is_file()
        assert float(clip.find('CurrentEnd').get('Value')) - float(clip.find('CurrentStart').get('Value')) == 32


def test_suggestions_are_pure(project):
    before = project.model_dump()
    result = suggestions(project, 'intro')
    assert any(s['kind'] == 'length' and s['bars'] == 16 for s in result)
    assert any(s['kind'] == 'next' and s['name'] == 'Build' for s in result)
    assert project.model_dump() == before
    with pytest.raises(ValueError):
        suggestions(project, 'missing')


def test_api_auth_validation_import_and_export(tmp_path, click_loop, project):
    client = TestClient(create_app(tmp_path / 'cache', 'secret'))
    assert client.get('/health').status_code == 401
    assert client.post('/export', json={}).status_code == 401
    client.headers['Authorization'] = 'Bearer secret'
    assert client.get('/health').json() == {'status': 'ready'}
    arrangement = client.get('/arrangement').json()
    assert [s['name'] for s in arrangement] == ['Intro', 'Build', 'Drop 1', 'Breakdown', 'Build 2', 'Drop 2', 'Outro']
    assert all(s['tips'] for s in arrangement)
    assert client.post('/loops/upload', files={'file': ('bad.txt', b'bad')}).status_code == 422
    assert client.post('/loops/upload', files={'file': ('bad.wav', b'bad')}).status_code == 422
    loop = client.post('/loops/import', json={'paths': [str(click_loop)]}).json()[0]
    project.loops[0] = Loop(**loop)
    for section in project.sections:
        section.clips[0].loop_id = loop['id']
    assert client.post('/suggestions/intro', json=project.model_dump()).status_code == 200
    assert client.post('/suggestions/missing', json=project.model_dump()).status_code == 404
    for format in ('midi', 'logic', 'ableton'):
        response = client.post('/export', json={'project': project.model_dump(), 'format': format, 'directory': str(tmp_path)})
        assert response.status_code == 200, response.text
        assert Path(response.json()['path']).is_dir()
    payload = project.model_dump()
    payload['sections'][0]['bars'] = 7
    assert client.post('/suggestions/intro', json=payload).status_code == 422
    payload = project.model_dump()
    payload['sections'][0]['clips'][0]['loop_id'] = '../../missing'
    assert client.post('/export', json={'project': payload, 'format': 'ableton', 'directory': str(tmp_path)}).status_code == 422
    assert client.options('/health', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'GET'}).status_code == 400


@pytest.mark.parametrize('extension', ['aiff', 'mp3'])
def test_api_supported_formats(tmp_path, click_loop, extension):
    y, sr = sf.read(click_loop)
    source = tmp_path / f'loop.{extension}'
    sf.write(source, y, sr)
    client = TestClient(create_app(tmp_path / 'cache', 'secret'))
    client.headers['Authorization'] = 'Bearer secret'
    response = client.post('/loops/upload', files={'file': (source.name, source.read_bytes())})
    assert response.status_code == 200, response.text
    assert abs(response.json()['bpm'] - 172) < 3
    copied = next((tmp_path / 'cache').glob('*.source.*'))
    assert copied.read_bytes() == source.read_bytes()
