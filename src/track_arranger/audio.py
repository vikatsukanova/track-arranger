import numpy as np
import soundfile as sf


def sound_bounds(data):
    level = np.max(np.abs(data), axis=1) if data.ndim == 2 else np.abs(data)
    active = np.flatnonzero(level > max(float(level.max()) * .001, 1e-6))
    return (int(active[0]), int(active[-1]) + 1) if len(active) else (0, len(data))


def read_loop(source, bpm, bars, trim_to_bars=True):
    data, sr = sf.read(source, always_2d=True, dtype='float32')
    if trim_to_bars:
        start, _ = sound_bounds(data)
        count = max(1, round(bars * 240 / bpm * sr))
        data = data[start:start + count]
        if len(data) < count:
            data = np.pad(data, ((0, count - len(data)), (0, 0)))
    return data, sr
