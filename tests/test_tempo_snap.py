import numpy as np
import pytest
import soundfile as sf

from track_arranger.analysis import analyze, snap_loop_tempo
from track_arranger.audio import read_loop


def generated_loop(sr, bars=8):
    bpm = 174
    count = round(bars * 240 / bpm * sr)
    t = np.arange(count) / sr
    data = .2 * np.cos(2 * np.pi * 120 * t)
    click = np.cos(np.arange(440) * 2 * np.pi * 1000 / sr) * np.exp(-np.arange(440) / 60)
    for beat in range(bars * 4):
        start = round(beat * 60 / bpm * sr)
        data[start:start + len(click)] += click[:len(data) - start]
    return data


@pytest.mark.parametrize('silence', [0, .6])
def test_loop_length_corrects_frame_quantized_tempo(tmp_path, silence):
    sr = 22050
    original = generated_loop(sr)
    source = tmp_path / 'loop.wav'
    sf.write(source, np.concatenate([original, np.zeros(round(silence * sr))]), sr, subtype='FLOAT')
    metadata = analyze(source)
    assert metadata['bpm'] == pytest.approx(174, abs=.1)
    assert metadata['bars'] == 8
    trimmed, rate = read_loop(source, metadata['bpm'], metadata['bars'])
    assert len(trimmed) == round(8 * 240 / 174 * rate)
    np.testing.assert_allclose(trimmed[:, 0], original, atol=1e-7)
    assert abs(trimmed[-1, 0]) > .01


def test_nonmatching_length_keeps_librosa_tempo(tmp_path, monkeypatch):
    monkeypatch.setattr('track_arranger.analysis.librosa.beat.beat_track',
                        lambda **kwargs: (np.array([172.27]), np.array([])))
    source = tmp_path / 'three-bars.wav'
    sf.write(source, generated_loop(22050, bars=3), 22050, subtype='FLOAT')
    metadata = analyze(source)
    assert metadata['bpm'] == 172.27
    assert metadata['bars'] == 3


def test_sixteenth_tail_tolerance_and_four_percent_limit():
    assert snap_loop_tempo(174, 8 * 240 / 174 + .04) == (174, 8)
    assert snap_loop_tempo(172.27, 8 * 240 / 174) == (174, 8)
    assert snap_loop_tempo(160, 8 * 240 / 174)[0] == 160
