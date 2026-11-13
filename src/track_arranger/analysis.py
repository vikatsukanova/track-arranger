from pathlib import Path
import librosa
import numpy as np
from track_arranger.audio import sound_bounds


def analyze(path: Path) -> dict:
    y, sr = librosa.load(path, sr=22050, duration=120)
    if len(y) < sr / 4 or not np.any(np.abs(y) > 1e-6):
        raise ValueError('Audio must contain at least 0.25 seconds of non-silent sound')
    start, end = sound_bounds(y)
    active_seconds = (end - start) / sr
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr, start_bpm=174)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    if bpm <= 0:
        bpm = 174.0
    while bpm < 140:
        bpm *= 2
    while bpm > 200:
        bpm /= 2
    chroma = librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1)
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    scores = [(float(np.dot(chroma, np.roll(profile, i)) / np.linalg.norm(profile)), i, mode)
              for profile, mode in [(major, 'major'), (minor, 'minor')] for i in range(12)]
    _, tonic, mode = max(scores)
    seconds = float(librosa.get_duration(path=path))
    return dict(bpm=round(bpm, 2), key=f"{['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][tonic]} {mode}",
                suggested_role=guess_role(y, sr), bars=max(1, round(active_seconds * bpm / 240)), seconds=seconds)


def guess_role(y, sr):
    rms = float(np.sqrt(np.mean(y ** 2)))
    spectrum = np.abs(np.fft.rfft(y)) ** 2
    low = float(spectrum[np.fft.rfftfreq(len(y), 1 / sr) < 150].sum() / max(spectrum.sum(), 1e-12))
    density = len(librosa.onset.onset_detect(y=y, sr=sr)) / (len(y) / sr)
    if rms > .12 and low > .3 and density > 1:
        return 'Drop'
    if rms < .05 and low < .1:
        return 'Intro'
    return 'Drop'
