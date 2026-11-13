import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if len(sys.argv) > 1:
    target = sys.argv[1]
else:
    target = subprocess.check_output(['rustc', '-vV'], text=True).split('host: ')[1].splitlines()[0]
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', 'track-arranger-api',
        '--additional-hooks-dir', str(root / 'scripts/pyinstaller-hooks'), '--paths', str(root / 'src'), '--distpath', str(root / 'work/sidecar-dist'),
        '--workpath', str(root / 'work/sidecar-build'), '--specpath', str(root / 'work')]
for package in ['librosa', 'soundfile', 'soxr', 'scipy', 'sklearn', 'numba', 'llvmlite', 'uvicorn']:
    args += ['--collect-all', package]
if platform.system() == 'Darwin':
    args += ['--codesign-identity', '-']
args += [str(root / 'scripts/sidecar_entry.py')]
subprocess.run(args, check=True, cwd=root)
binaries = root / 'app/src-tauri/binaries'
binaries.mkdir(parents=True, exist_ok=True)
suffix = '.exe' if os.name == 'nt' else ''
shutil.copy2(root / f'work/sidecar-dist/track-arranger-api{suffix}', binaries / f'track-arranger-api-{target}{suffix}')
