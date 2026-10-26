"""Create a finite soundtrack and detect musical beats without paid APIs."""
from __future__ import annotations

import math
from pathlib import Path

from .media import UltraError, probe, run


def soundtrack_playlist(paths: list[Path], required: float, *, allow_repeat: bool = False,
                        fade: float = 0.7) -> list[Path]:
    if not paths:
        raise UltraError("Aucune musique : ajouter des pistes dans library/music/<style>/ ou --music")
    durations: dict[Path, float] = {}
    for path in paths:
        if not path.is_file():
            raise UltraError(f"Fichier musical introuvable : {path}")
        duration = probe(path)["duration"]
        if duration <= fade + 0.5:
            raise UltraError(f"Piste trop courte : {path.name}")
        durations[path] = duration
    chosen, available = [], 0.0
    index = 0
    while available < required + 0.05:
        if index >= len(paths) and not allow_repeat:
            raise UltraError(f"Playlist trop courte : {available / 60:.1f} min disponibles pour {required / 60:.1f} min. Ajouter des titres ou --repeat-music.")
        track = paths[index % len(paths)]
        chosen.append(track)
        available += durations[track] - (fade if len(chosen) > 1 else 0)
        index += 1
        if index > 500:
            raise UltraError("Playlist anormalement longue")
    return chosen


def build_soundtrack(paths: list[Path], target: float, out: Path, *, repeat: bool = False,
                     fade: float = 0.7) -> list[Path]:
    """Crossfade tracks, then trim to precisely the requested duration."""
    out.parent.mkdir(parents=True, exist_ok=True)
    chosen = soundtrack_playlist(paths, target, allow_repeat=repeat, fade=fade)
    filters = []
    for i in range(len(chosen)):
        filters.append(f"[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
    left = "a0"
    for i in range(1, len(chosen)):
        new = f"mix{i}"
        filters.append(f"[{left}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[{new}]")
        left = new
    filters.append(f"[{left}]atrim=0:{target:.4f},asetpts=PTS-STARTPTS[final]")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in chosen:
        cmd += ["-i", str(path)]
    cmd += ["-filter_complex", ";".join(filters), "-map", "[final]", "-vn", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", str(out)]
    run(cmd)
    if probe(out)["duration"] < target - 0.3:
        raise UltraError("Durée musicale insuffisante après rendu")
    return chosen


def extract_beats(track: Path, *, engine: str = "fast", sample_rate: int = 11025,
                  hop: int = 512) -> list[float]:
    """Music attack/beat times. Fast mode requires only FFmpeg+NumPy.

    The fast algorithm marks percussive onsets at sufficiently wide intervals;
    it cannot infer harmony/phrase structure as well as full librosa beat tracking.
    """
    if engine == "librosa":
        import librosa
        import numpy as np
        wave, sr = librosa.load(str(track), sr=sample_rate, mono=True)
        if len(wave) == 0:
            return []
        onset = librosa.onset.onset_strength(y=wave, sr=sr, hop_length=hop)
        _, frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr,
                                           hop_length=hop, trim=False)
        beat_times = list(map(float, librosa.frames_to_time(frames, sr=sr,
                                                            hop_length=hop)))
        if len(beat_times) >= max(6, len(wave) / sr / 10):
            return sorted(set(round(b, 3) for b in beat_times if math.isfinite(b)))
        # Otherwise, fall back to fast reliable transient candidates.
    elif engine != "fast":
        raise ValueError(f"Beat engine inconnu: {engine}")

    import subprocess
    import numpy as np
    # FFmpeg handles arbitrary media and resampling; no numba JIT startup cost.
    cp = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(track),
                         "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
                        capture_output=True, check=False)
    if cp.returncode:
        raise UltraError(f"Impossible de décoder la musique: {cp.stderr.decode(errors='replace')[-800:]}")
    wave = np.frombuffer(cp.stdout, dtype=np.float32)
    if wave.size < 1024:
        return []
    window_size = 1024
    step = 256
    # Streaming-ish FFT batches: keep peak RAM small even for 30–60 min playlists.
    onsets = []
    last_spectrum = None
    for chunk_start in range(0, len(wave) - window_size, step * 2048):
        chunk = wave[chunk_start:min(len(wave), chunk_start + step * 2048 + window_size)]
        if len(chunk) < window_size:
            continue
        frames = np.lib.stride_tricks.sliding_window_view(chunk, window_size)[::step]
        magnitudes = np.abs(np.fft.rfft(frames * np.hanning(window_size), axis=1)).astype(np.float32)
        # Positive spectral flux: musical attacks that often coincide with beats.
        if last_spectrum is not None:
            # The new chunk starts at the old chunk's last FFT window; skip duplicate.
            magnitudes = np.concatenate([last_spectrum[np.newaxis, :], magnitudes[1:]])
        deltas = np.maximum(0, np.diff(magnitudes, axis=0)).mean(axis=1)
        onsets.extend(deltas.astype(float).tolist())
        last_spectrum = magnitudes[-1]
    signal = np.asarray(onsets, dtype=np.float32)
    if signal.size < 6:
        return []
    signal = np.convolve(signal, np.ones(3) / 3, mode="same")
    # Adaptive thresholds across changing music tracks.
    frame_rate = sample_rate / step
    min_gap = int(frame_rate * 0.27)
    peaks = []
    window_frames = max(1, int(frame_rate * 25))
    for start in range(0, len(signal), window_frames):
        block = signal[start:start + window_frames]
        floor = max(float(np.percentile(block, 66)), float(np.median(block)) * 1.5, 0.0001)
        candidates = []
        for i in range(1, len(block) - 1):
            if block[i] > floor and block[i] >= block[i - 1] and block[i] >= block[i + 1]:
                candidates.append((float(block[i]), start + i))
        accepted = []
        for _, position in sorted(candidates, reverse=True):
            if all(abs(position - x) >= min_gap for x in accepted):
                accepted.append(position)
        peaks.extend(accepted)
    return sorted(set(round(p / frame_rate, 3) for p in peaks))
