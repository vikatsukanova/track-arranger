import re
import json
import os
import secrets
import socket
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import soundfile as sf
from fastapi import Query, Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from track_arranger.analysis import analyze
from track_arranger.arrangement import build_arrangement
from track_arranger.desktop_export import export_ableton, export_logic, sections
from track_arranger.desktop_models import AnalyzedLoop, Loop, Project, Variation
from track_arranger.variations import render
from track_arranger.midi_export import export_midi
from track_arranger.suggestions import suggestions
from track_arranger.tips import TIPS

MAX_BYTES = 100 * 1024 * 1024


class RenderRequest(BaseModel):
    loop: Loop
    bars: int = Field(ge=8, le=256, multiple_of=8)
    bpm: float = Field(ge=160, le=180)
    variation: Variation


class ImportPaths(BaseModel):
    paths: list[str]


class ExportRequest(BaseModel):
    project: Project
    format: Literal['ableton', 'logic', 'midi']
    directory: str


def create_app(cache: Path, token: str) -> FastAPI:
    cache.mkdir(parents=True, exist_ok=True)

    def authorize(authorization: str = Header(default='')):
        if not secrets.compare_digest(authorization, f'Bearer {token}'):
            raise HTTPException(401, 'Invalid session token')

    app = FastAPI(dependencies=[Depends(authorize)])
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:1420', 'http://localhost:1420', 'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'],
                       allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

    def register(name: str, data: bytes) -> AnalyzedLoop:
        suffix = Path(name).suffix.lower()
        if suffix not in {'.wav', '.aif', '.aiff', '.mp3'}:
            raise HTTPException(422, 'Choose WAV, AIFF or MP3 audio')
        if len(data) > MAX_BYTES:
            raise HTTPException(413, 'Each loop must be under 100 MB')
        loop_id = uuid.uuid4().hex
        source = cache / f'{loop_id}.source{suffix}'
        source.write_bytes(data)
        try:
            info = sf.info(source)
            if info.duration > 120 or info.channels > 2:
                raise ValueError('Loops must be mono/stereo and at most 120 seconds')
            metadata = AnalyzedLoop(id=loop_id, filename=Path(name).name, **analyze(source))
            audio, sr = sf.read(source, always_2d=True)
            sf.write(cache / f'{loop_id}.wav', audio, sr, subtype='FLOAT')
            return metadata
        except Exception as exc:
            raise HTTPException(422, f'Cannot analyze {Path(name).name}: {exc}') from exc
        finally:
            if not (cache / f'{loop_id}.wav').exists():
                source.unlink(missing_ok=True)

    @app.get('/health')
    def health():
        return {'status': 'ready'}

    @app.post('/loops/upload')
    def upload(file: UploadFile):
        return register(file.filename or 'loop.wav', file.file.read(MAX_BYTES + 1))

    @app.post('/loops/import')
    def import_paths(request: ImportPaths):
        if not 1 <= len(request.paths) <= 128:
            raise HTTPException(422, 'Choose between 1 and 128 loops')
        result = []
        for raw in request.paths:
            path = Path(raw)
            try:
                if path.stat().st_size > MAX_BYTES:
                    raise HTTPException(413, 'Each loop must be under 100 MB')
                result.append(register(path.name, path.read_bytes()))
            except OSError as exc:
                raise HTTPException(422, 'Cannot read audio file') from exc
        return result

    @app.get('/audio/{loop_id}')
    def audio(loop_id: str, bpm: float | None = Query(default=None, ge=160, le=180), bars: float = Query(default=8, ge=.125, le=1024)):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', loop_id):
            raise HTTPException(404, 'Unknown loop')
        path = cache / f'{loop_id}.wav'
        if not path.is_file():
            raise HTTPException(404, 'Unknown loop')
        if bpm is not None:
            aligned = cache / f'{loop_id}-tempo-{bpm}-{bars}.wav'
            if not aligned.exists():
                render(path, aligned, bars, bpm, bars, Variation(kind='Full', gain=1))
            path = aligned
        return FileResponse(path, media_type='audio/wav')

    @app.post('/variations')
    def variation(request: RenderRequest):
        source = cache / f'{request.loop.id}.wav'
        if not source.is_file():
            raise HTTPException(404, 'Unknown loop')
        loop_id = uuid.uuid4().hex
        render(source, cache / f'{loop_id}.wav', request.bars, request.bpm, request.loop.bars, request.variation)
        return request.loop.model_copy(update=dict(id=loop_id, filename=f'{request.loop.filename} · {request.variation.kind}',
            bars=request.bars, bpm=request.bpm, seconds=request.bars * 240 / request.bpm))

    @app.get('/arrangement')
    def arrangement():
        return [dict(id=uuid.uuid4().hex, **asdict(s), clips=[], tips=TIPS['dnb'][s.name]) for s in build_arrangement()]

    @app.get('/tips')
    def tips():
        return TIPS

    @app.post('/suggestions/{section_id}')
    def suggest(section_id: str, project: Project):
        try:
            return suggestions(project, section_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post('/export')
    def export(request: ExportRequest):
        project = request.project
        metadata = {loop.id: loop for loop in project.loops}
        sources = {}
        for section in project.sections:
            for clip in section.clips:
                if clip.loop_id not in metadata or not (cache / f'{clip.loop_id}.wav').is_file():
                    raise HTTPException(422, 'A loop is missing. Import it again before exporting.')
                sources[clip.loop_id] = next(cache.glob(f'{clip.loop_id}.source.*'), cache / f'{clip.loop_id}.wav')
        parent = Path(request.directory).expanduser()
        if not parent.is_dir():
            raise HTTPException(422, 'Choose an existing export directory')
        out = parent / f'Track-Arranger-{uuid.uuid4().hex[:8]}'
        out.mkdir()
        try:
            if request.format == 'midi':
                export_midi(sections(project), project.bpm, out / 'Sections.mid')
            elif request.format == 'ableton':
                export_ableton(project, sources, out)
            else:
                export_logic(project, sources, out)
        except Exception as exc:
            import shutil
            shutil.rmtree(out)
            raise HTTPException(422, f'Export failed: {exc}') from exc
        return {'path': str(out)}

    return app


def main():
    import uvicorn
    token = os.environ.get('TRACK_ARRANGER_TOKEN')
    if not token:
        raise SystemExit('TRACK_ARRANGER_TOKEN is required')
    cache = Path(os.environ.get('TRACK_ARRANGER_CACHE', str(Path.home() / 'Library' / 'Caches' / 'TrackArranger')))
    sock = socket.socket()
    sock.bind(('127.0.0.1', int(os.environ.get('TRACK_ARRANGER_PORT', '0'))))
    sock.listen(128)
    print(json.dumps({'port': sock.getsockname()[1]}), flush=True)
    server = uvicorn.Server(uvicorn.Config(create_app(cache, token), log_level='warning', access_log=False))
    server.run(sockets=[sock])


if __name__ == '__main__':
    main()
