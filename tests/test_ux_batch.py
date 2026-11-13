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
