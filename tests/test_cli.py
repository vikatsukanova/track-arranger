import subprocess
import sys

import pytest


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "track_arranger.cli", *args],
        capture_output=True, text=True,
    )


def test_default_cli(tmp_path):
    out = tmp_path / "my track.mid"
    result = run_cli("--out", str(out))
    assert result.returncode == 0
    assert out.is_file()
    assert "174 BPM" in result.stdout
    assert "Total: 192 bars | 04:24" in result.stdout
    assert result.stdout.count("  - ") == 14


@pytest.mark.parametrize("bpm", ["159", "181", "nan", "inf", "oops"])
def test_bad_bpm(tmp_path, bpm):
    out = tmp_path / "bad.mid"
    result = run_cli("--bpm", bpm, "--out", str(out))
    assert result.returncode == 2
    assert not out.exists()


def test_missing_output():
    assert run_cli().returncode == 2


def test_bad_suffix(tmp_path):
    assert run_cli("--out", str(tmp_path / "file.txt")).returncode == 2


def test_missing_parent_is_friendly(tmp_path):
    result = run_cli("--out", str(tmp_path / "missing" / "file.mid"))
    assert result.returncode == 1
    assert "Could not write MIDI" in result.stderr
    assert "Traceback" not in result.stderr
