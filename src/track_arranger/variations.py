from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from track_arranger.desktop_models import Variation
from track_arranger.audio import read_loop


def render(source: Path, destination: Path, bars: float, bpm: float, loop_bars: float, variation: Variation, trim_to_bars=False, source_bpm=None, whole_loop=False):
    data, sr = read_loop(source, source_bpm or bpm, loop_bars, trim_to_bars)
    target = max(1, round(len(data) * source_bpm / bpm)) if not trim_to_bars and source_bpm is not None else max(1, round(loop_bars * 240 / bpm * sr))
    if len(data) != target:
        data = librosa.effects.time_stretch(data.T, rate=len(data) / target).T
    data = librosa.util.fix_length(data, size=target, axis=0)
    count = target if whole_loop else round(bars * 240 / bpm * sr)
    data = data[np.arange(count) % len(data)]
    cutoff = min(variation.cutoff, sr * .45)
    def filtered(kind, hz):
        return sosfilt(butter(2, hz, btype=kind, fs=sr, output='sos'), data, axis=0)
    if variation.kind == 'Low-pass':
        data = filtered('lowpass', cutoff)
    elif variation.kind == 'High-pass':
        data = filtered('highpass', cutoff)
    elif variation.kind == 'Filter sweep':
        # Open a low-pass from the chosen cutoff to the dry loop.
        result = np.zeros_like(data)
        position = np.linspace(0, 7, count)
        for i, hz in enumerate(np.geomspace(cutoff, sr * .45, 8)):
            band = data if i == 7 else filtered('lowpass', hz)
            result += band * np.maximum(0, 1 - np.abs(position - i))[:, None]
        data = result
    elif variation.kind == 'Fade':
        data = filtered('lowpass', cutoff) * np.linspace(1, 0, count)[:, None]
    sf.write(destination, data * variation.gain, sr, subtype='FLOAT')
