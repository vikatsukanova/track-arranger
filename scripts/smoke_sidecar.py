import json
import math
import struct
import wave
import os
from pathlib import Path
import secrets
import selectors
import subprocess
import sys
import tempfile
import time
import urllib.request

with tempfile.TemporaryDirectory() as cache:
    token = secrets.token_urlsafe(32)
    child = subprocess.Popen([str(Path(sys.argv[1]).resolve())], stdout=subprocess.PIPE,
                             env={**os.environ, 'TRACK_ARRANGER_TOKEN': token, 'TRACK_ARRANGER_CACHE': cache}, text=True)
    try:
        selector = selectors.DefaultSelector()
        selector.register(child.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=120):
            raise RuntimeError('Sidecar did not announce a port')
        port = json.loads(child.stdout.readline())['port']
        for attempt in range(100):
            try:
                request = urllib.request.Request(f'http://127.0.0.1:{port}/health', headers={'Authorization': f'Bearer {token}'})
                with urllib.request.urlopen(request, timeout=2) as response:
                    assert json.load(response)['status'] == 'ready'
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Sidecar did not become healthy')
        sr = 22050
        audio = Path(cache) / 'click.wav'
        duration = 8 * 240 / 172
        with wave.open(str(audio), 'wb') as stream:
            stream.setparams((1, 2, sr, 0, 'NONE', 'not compressed'))
            frames = []
            for i in range(round(duration * sr)):
                phase = (i / sr) % (60 / 172)
                amplitude = math.sin(2 * math.pi * 1000 * phase) * math.exp(-phase * 300)
                frames.append(struct.pack('<h', round(amplitude * 16000)))
            stream.writeframes(b''.join(frames))
        def post(path, data):
            request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(data).encode(),
                                             headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(exc.read().decode()) from exc
        loop = post('/loops/import', {'paths': [str(audio)]})[0]
        assert abs(loop['bpm'] - 172) < 3, loop
        project = {'genre': 'dnb', 'bpm': 172, 'loops': [loop], 'sections': [
            {'id': 'intro', 'name': 'Intro', 'bars': 8, 'clips': [{'lane': 'Drums', 'loop_id': loop['id']}]}]}
        for format in ['ableton', 'logic', 'midi']:
            result = post('/export', {'project': project, 'format': format, 'directory': cache})
            assert Path(result['path']).is_dir()
        print('Packaged sidecar: health, analysis and all three exports passed.')
    finally:
        child.terminate()
        child.wait(timeout=10)
