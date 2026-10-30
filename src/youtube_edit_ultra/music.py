"""Create a finite soundtrack and detect musical beats without paid APIs."""
from __future__ import annotations

import math
import json
import subprocess
import hashlib
import re
from pathlib import Path

from .media import UltraError, probe, run


def audio_profile(path: Path, *, cache_dir: Path | None = None) -> dict:
    """Cache measured gain and audible bounds; container duration can include long silence."""
    from .catalogue import read, save, sha256
    key = hashlib.sha256((sha256(path) + ':audible-v2').encode()).hexdigest()
    root = Path(cache_dir) if cache_dir is not None else Path.home() / '.local/share/youtube-edit-ultra/cache/audio-profiles'
    cache = root / (key + '.json')
    if cache.exists():
        try:
            result = read(cache)
            required = ['integrated_lufs', 'true_peak_dbtp', 'gain_db', 'source_start', 'source_end', 'usable_duration']
            if (not all(math.isfinite(result[k]) for k in required)
                    or result['source_start'] < 0 or result['usable_duration'] <= 1.2
                    or abs(result['source_end'] - result['source_start'] - result['usable_duration']) > 1e-6):
                raise ValueError('invalid measurements')
            return dict(result, path=str(path))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise UltraError(f'Invalid audio profile cache {cache}: {exc}') from exc
    level = measure_loudness(path)
    duration = probe(path)['duration']
    cp = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-vn',
                         '-af', f"volume={level['gain_db']}dB,silencedetect=n=-45dB:d=0.15",
                         '-f', 'null', '-'], capture_output=True, text=True)
    if cp.returncode:
        raise UltraError('Analyse des silences échouée : ' + cp.stderr[-800:])
    start, end, pending = 0.0, duration, None
    for kind, value in re.findall(r'silence_(start|end):\s*([0-9.]+)', cp.stderr):
        value = float(value)
        if kind == 'start':
            pending = value
        elif pending is not None:
            if pending < .05:
                start = max(0, value - .03)
            if value >= duration - .1:
                end = min(duration, pending + .03)
            pending = None
    if pending is not None:
        end = min(end, pending + .03)
    if end - start <= 1.2:
        raise UltraError(f'Piste sans durée audible suffisante : {path}')
    result = dict(level, source_start=start, source_end=end, usable_duration=end-start)
    save(cache, result)
    return result


def measure_loudness(path: Path) -> dict:
    """Reuse the measured static-gain approach from Boxing-Tubeviz/remix_hiphop90s.py."""
    cp = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn",
        "-af", "loudnorm=I=-18:TP=-3:LRA=11:print_format=json", "-f", "null", "-"
    ], capture_output=True, text=True)
    if cp.returncode:
        raise UltraError("Mesure musicale échouée : " + cp.stderr[-800:])
    try:
        data = json.JSONDecoder().raw_decode(cp.stderr[cp.stderr.rfind("{"):])[0]
        level, peak = float(data["input_i"]), float(data["input_tp"])
        if not math.isfinite(level) or not math.isfinite(peak):
            raise ValueError("piste silencieuse ou trop courte pour LUFS")
    except (ValueError, KeyError) as e:
        raise UltraError(f"Mesure musicale invalide pour {path}: {e}") from e
    return dict(path=str(path), integrated_lufs=level, true_peak_dbtp=peak,
                gain_db=round(min(-18 - level, -3 - peak), 4))


def soundtrack_playlist(paths: list[Path], required: float, *, allow_repeat: bool = False,
                        fade: float = 0.7, cache_dir: Path | None = None) -> list[Path]:
    if not paths:
        raise UltraError("Aucune musique : ajouter des pistes dans library/music/<style>/ ou --music")
    durations: dict[Path, float] = {}
    for path in paths:
        if not path.is_file():
            raise UltraError(f"Fichier musical introuvable : {path}")
        duration = audio_profile(path, cache_dir=cache_dir)["usable_duration"]
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


def arrange_playlist(rows: list[dict], *, cache_dir: Path) -> tuple[list[dict], dict]:
    """Build a gradual percussive progression; explicit playlists keep their order elsewhere."""
    from .catalogue import read, save, sha256
    measured = []
    for row in rows:
        path = Path(row['path'])
        digest = sha256(path)
        cache = cache_dir / (digest + '-rhythm-v1.json')
        if cache.exists():
            rhythm = read(cache)
            if (not isinstance(rhythm, dict) or rhythm.get('sha256') != digest
                    or not all(isinstance(rhythm.get(k), (int, float)) and math.isfinite(rhythm[k])
                               and rhythm[k] >= 0 for k in ('onsets_per_second', 'estimated_bpm'))):
                raise UltraError('Invalid playlist rhythm cache: ' + str(cache))
        else:
            import statistics
            beats = extract_beats(path)
            gaps = [b - a for a, b in zip(beats, beats[1:]) if .27 <= b - a <= 1.5]
            duration = audio_profile(path, cache_dir=cache_dir)['usable_duration']
            rhythm = dict(sha256=digest, onsets_per_second=len(beats) / duration,
                          estimated_bpm=60 / statistics.median(gaps) if gaps else 0.)
            save(cache, rhythm)
        measured.append(dict(path=str(path), **rhythm))
    metrics = {m['path']: m for m in measured}
    ordered = sorted(rows, key=lambda r: (metrics[r['path']]['onsets_per_second'],
                                         metrics[r['path']]['estimated_bpm']))
    return ordered, dict(method='gradually increasing measured onset density',
                         tempo_is_estimate=True, harmonic_compatibility_verified=False,
                         tracks=[metrics[r['path']] for r in ordered])


def build_soundtrack(paths: list[Path], target: float, out: Path, *, repeat: bool = False,
                     fade: float = 0.7, cache_dir: Path | None = None) -> list[Path]:
    """Crossfade tracks, then trim to precisely the requested duration."""
    out.parent.mkdir(parents=True, exist_ok=True)
    chosen = soundtrack_playlist(paths, target, allow_repeat=repeat, fade=fade, cache_dir=cache_dir)
    levels = [audio_profile(path, cache_dir=cache_dir) for path in chosen]
    out.with_suffix(".levels.json").write_text(json.dumps(levels, indent=2) + "\n")
    filters = []
    for i in range(len(chosen)):
        filters.append(f"[{i}:a:0]atrim=start={levels[i]['source_start']}:end={levels[i]['source_end']},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={levels[i]['gain_db']}dB,asetpts=PTS-STARTPTS[a{i}]")
    left = "a0"
    for i in range(1, len(chosen)):
        new = f"mix{i}"
        filters.append(f"[{left}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[{new}]")
        left = new
    filters.append(f"[{left}]atrim=0:{target:.4f},afade=t=out:st={max(0, target - 0.5):.4f}:d=0.5,asetpts=PTS-STARTPTS[final]")
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
