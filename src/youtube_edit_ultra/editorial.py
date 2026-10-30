"""Music-led selection with protected actions, adapted from the executed Maidana edit.

Shot margins are reviewed context, not permission to shorten a combination.
Downbeats and section labels remain inferred musical evidence.
"""

import math
from collections import Counter

import numpy as np

from .media import UltraError
from .planner import Edit


def _available(shots, edits):
    return [s for s in shots if not any(
        e.source == s["source"] and s["safe_start"] < e.source_end + .05
        and s["safe_end"] > e.source_start - .05 for e in edits)]


def _choices(shots, structure, target, edits, fps):
    t = edits[-1].timeline_end if edits else 0.0
    used = Counter(e.source for e in edits)
    g = next((g for g in reversed(structure) if g["start"] <= t), structure[0])
    beats = np.asarray(g["beats"])
    wave = np.asarray(g["features"]["wave"])
    energy = float(np.interp(t, beats, wave)) if len(beats) else .5
    rank = float(np.mean(wave <= energy)) if len(wave) and np.ptp(wave) > 1e-6 else .5
    desired = float(np.interp(rank, [0, .25, .6, .9, 1], [6, 4.8, 3.2, 2.1, 1.5]))
    if len(edits) > 3 and all(e.duration < 2.1 for e in edits[-3:]):
        desired = max(desired, 3.5)
    quiet = energy < .3
    accents = np.asarray(g.get("cut_accents", g["beats"]))
    beat_ends = {round(float(b) * fps) / fps for b in accents if t + 1 <= b <= min(target, t + 12)}
    for s in shots:
        if not s.get("not_before", 0) <= t < s.get("not_after", target + 1):
            continue
        narrative = s.get("kind", "action") != "action"
        if narrative and not quiet and t > 20 and len(edits) % 14:
            continue
        # Natural complete-action endings remain available beyond the preferred beat horizon.
        ends = beat_ends | {target,
            t + math.ceil((s["core_end"] - s["core_start"] - 1e-7) * fps) / fps,
            t + math.floor((s["safe_end"] - s["safe_start"] + 1e-7) * fps) / fps}
        for end in sorted(ends):
            if end <= t or end > target + 1e-7 or (end != target and target - end < 1 / fps):
                continue
            d = end - t
            lo = math.ceil((max(s["safe_start"], s["core_end"] - d) - 1e-7) * fps) / fps
            hi = math.floor((min(s["core_start"], s["safe_end"] - d) + 1e-7) * fps) / fps
            if lo > hi:
                continue
            peak = s.get("peak")
            anchors = accents[(accents > t + .25) & (accents < end - .25)]
            starts = ([lo] if peak is None or not len(anchors) else
                [min(hi, max(lo, round((peak - (a - t)) * fps) / fps)) for a in anchors])
            for start in sorted(set(starts)):
                miss = 0 if peak is None else min((abs(t + peak - start - b) for b in anchors), default=.5)
                score = -.65 * abs(d - desired) - 5 * miss - .035 * used[s["source"]]
                score += 1.4 if quiet == narrative else -.8
                score -= .65 if edits and edits[-1].source == s["source"] else 0
                score += float(s.get("quality", .7))
                yield score, Edit(s["source"], round(start, 6), round(start + d, 6), round(t, 6),
                    round(end, 6), s["label"], peak, s.get("provenance", "editorial_candidate"),
                    float(s.get("quality", .7)), audio_intent=s.get('audio_intent', 'auto'))


def _recover_editorial(history, structure, target, fps):
    # shortcut: bounded tail search, not an exhaustive optimizer for arbitrary overlapping windows.
    budget = 1500
    for prefix, remaining in reversed(history):
        stack = [(prefix, remaining)]
        while stack and budget:
            edits, available = stack.pop()
            budget -= 1
            t = edits[-1].timeline_end if edits else 0.0
            if abs(t - target) <= 1e-5:
                return edits
            if len(edits) - len(prefix) >= 64:
                continue
            options = sorted(_choices(available[:128], structure, target, edits, fps),
                             key=lambda choice: choice[0], reverse=True)
            per_action, chosen = Counter(), []
            for _, edit in options:
                identity = (edit.source, edit.label)
                if per_action[identity] >= 2:
                    continue
                per_action[identity] += 1
                chosen.append(edit)
                if len(chosen) >= 16:
                    break
            for edit in reversed(chosen):
                stack.append((edits + [edit], _available(available, [edit])))
    return None


def plan_editorial(shots, structure, target, *, intro=(), outro=(), fps=30):
    if not shots or not structure or fps <= 0 or not math.isfinite(target) or target <= 0:
        raise UltraError("Editorial inputs, positive target and FPS required")
    if abs(target * fps - round(target * fps)) > 1e-3:
        raise UltraError("Target must lie on the output frame grid")
    at = 0.0
    for e in intro:
        if abs(e.timeline_start - at) > 1e-5 or abs(e.timeline_end - at - e.duration) > 1e-5:
            raise UltraError("Noncontiguous intro or changed playback speed")
        at = e.timeline_end
    end = outro[0].timeline_start if outro else target
    outro_at = end
    for e in outro:
        if abs(e.timeline_start - outro_at) > 1e-5 or abs(e.timeline_end - outro_at - e.duration) > 1e-5:
            raise UltraError("Noncontiguous outro or changed playback speed")
        outro_at = e.timeline_end
    if at > end or abs(outro_at - target) > 1e-5:
        raise UltraError("Intro/outro outside target duration")
    edits = list(intro)
    remaining = _available(shots, [*intro, *outro])
    for s in shots:
        bounds = [s[k] for k in ("safe_start", "core_start", "core_end", "safe_end")]
        if not all(math.isfinite(v) for v in bounds) or not (0 <= bounds[0] <= bounds[1] < bounds[2] <= bounds[3]):
            raise UltraError("Invalid protected action: " + str(s))
    history = []
    while at < end - .5 / fps:
        best = max(_choices(remaining, structure, end, edits, fps), key=lambda choice: choice[0], default=None)
        if best is None:
            recovered = _recover_editorial(history, structure, end, fps)
            if recovered is not None:
                return recovered + list(outro)
            raise UltraError(f"Editorial coverage exhausted at {at:.3f}/{end:.3f}s after bounded search; add reviewed complete actions/context")
        history.append((edits[:], remaining[:]))
        history = history[-8:]
        _, edit = best
        edits.append(edit)
        remaining = _available(remaining, [edit])
        at = edit.timeline_end
    return edits + list(outro)


def editorial_integrity(edits, shots, target, *, intro=(), outro=()):
    """Check protected cores, not equality to the wider editable context windows."""
    violations = []
    at = 0.0
    for i, e in enumerate(edits):
        if (
            abs(e.timeline_start - at) > 1e-5
            or abs(e.timeline_end - e.timeline_start - e.duration) > 1e-5
        ):
            violations.append(dict(index=i, reason="timeline gap or changed speed"))
        at = e.timeline_end
        if e not in intro and e not in outro and not any(
            s["source"] == e.source
            and s["label"] == e.label
            and s["safe_start"] - 1e-5 <= e.source_start <= s["core_start"] + 1e-5
            and s["core_end"] - 1e-5 <= e.source_end <= s["safe_end"] + 1e-5
            for s in shots
        ):
            violations.append(dict(index=i, reason="protected core or safe margins violated"))
        if any(
            p.source == e.source
            and p.source_start < e.source_end - 1e-5
            and e.source_start < p.source_end - 1e-5
            for p in edits[:i]
        ):
            violations.append(dict(index=i, reason="repeated source interval"))
    if abs(at - target) > 1e-5:
        violations.append(dict(reason="target duration mismatch"))
    return dict(
        requested_seconds=target,
        assembled_seconds=at,
        events_selected=len(edits),
        all_selected_event_windows_preserved=not violations,
        violations=violations,
        filler_segments=0,
        semantic_completeness_guaranteed=False,
        reason_semantic_limit="Core boundaries require actual visual review; motion is not proof of a complete action",
    )


def _analyze_legacy(soundtrack, tracks, cache_dir, legacy_root):
    """Execute the same pinned BeatSync/cadence components used by Maidana.

    Their bar phases/section labels are heuristics, retained as such in reports.
    """
    import hashlib
    import importlib.util
    import json
    import subprocess
    import sys
    from pathlib import Path

    import librosa

    from .media import fingerprint
    from .music import extract_beats

    root = (
        Path(legacy_root)
        if legacy_root
        else Path.home() / "Documents/Boxing-Tubeviz/mayweather_30min/v3_beat_sync/repos"
    )

    def module(name, path):
        if not path.exists():
            raise UltraError(f"Missing retained musical analyzer: {path}")
        spec = importlib.util.spec_from_file_location(
            name, path, submodule_search_locations=[str(path.parent)]
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    key = hashlib.sha256(
        (
            fingerprint(Path(soundtrack))
            + json.dumps(tracks, sort_keys=True)
            + ":legacy-structure-v1"
        ).encode()
    ).hexdigest()
    cache_dir = Path(cache_dir) / key
    cache_dir.mkdir(parents=True, exist_ok=True)
    if (cache_dir / "structure.json").exists():
        return json.loads((cache_dir / "structure.json").read_text())
    engine = module("ultra_beat_engine", root / "BeatSync-Engine/src/auto_mode/__init__.py")
    cadence = module("ultra_cadence", root / "cadence/src/auto_mode/__init__.py")
    cfg = cadence.AutoWaveConfig(
        enable_rare_micro_cuts=False,
        enable_qwen_semantics=False,
        low_energy_min_interval=3,
        medium_energy_min_interval=1.8,
        high_energy_min_interval=0.8,
        peak_energy_min_interval=0.5,
        low_energy_max_hold=6,
        medium_energy_max_hold=4,
        high_energy_max_hold=2,
        peak_energy_max_hold=1.5,
    )
    results = []
    for i, tr in enumerate(tracks):
        f = cache_dir / f"music-{i:02}.json"
        if f.exists():
            results.append(json.loads(f.read_text()))
            continue
        start = tr["timeline_start"]
        end = tr["timeline_end"]
        sr = 22050
        cp = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(start),
                "-i",
                str(soundtrack),
                "-t",
                str(end - start),
                "-ac",
                "1",
                "-ar",
                str(sr),
                "-f",
                "f32le",
                "-",
            ],
            capture_output=True,
            check=True,
        )
        y = np.frombuffer(cp.stdout, np.float32).copy()
        h, p = librosa.effects.hpss(y)
        onset = librosa.onset.onset_strength(y=p, sr=sr, hop_length=512)
        tempo, bf = librosa.beat.beat_track(
            onset_envelope=onset, sr=sr, hop_length=512, start_bpm=100, trim=False
        )
        bt = librosa.frames_to_time(bf, sr=sr, hop_length=512)
        tempo = float(np.asarray(tempo).item())
        if len(bt) < 2:
            rec = dict(
                index=i,
                title=tr["title"],
                start=start,
                end=end,
                bpm=0,
                beats=[],
                downbeats=[],
                sections=[],
                features={"wave": []},
                downbeat_status="No reliable beat grid; preserve whole actions without invented beats",
            )
            f.write_text(json.dumps(rec, indent=2))
            results.append(rec)
            continue
        features = engine.analyze_wave_features(y, p, sr, bt, bf, onset, cfg, False)
        phase = int(
            np.argmax([np.mean((features["kick"] + features["bass"])[k::4]) for k in range(4)])
        )
        features["is_bar_anchor"][:] = False
        features["is_bar_anchor"][phase::4] = True
        features["is_phrase_anchor"][:] = False
        features["is_phrase_anchor"][phase::16] = True
        sections = cadence.analyze_sections(y, h, p, sr, bt, features, cfg)
        cuts, info = cadence.select_wave_cuts(bt, sections, features, tempo, len(y) / sr, cfg)
        from scipy.ndimage import gaussian_filter1d
        from scipy.signal import find_peaks

        rms = librosa.feature.rms(y=y)[0]
        smooth = gaussian_filter1d(rms, sr / 512 * 0.35)
        times = librosa.times_like(rms, sr=sr)
        shift = round(sr / 512)
        before = np.r_[np.repeat(smooth[0], shift), smooth[:-shift]]
        after = np.r_[smooth[shift:], np.repeat(smooth[-1], shift)]
        rise = 20 * np.log10((after + 1e-5) / (before + 1e-5))
        pk, _ = find_peaks(rise, height=3, distance=round(3 * sr / 512), prominence=2)
        rec = dict(
            index=i,
            title=tr["title"],
            start=start,
            end=end,
            bpm=tempo,
            beats=(bt + start).tolist(),
            downbeats=(bt[phase::4] + start).tolist(),
            sections=[dict(x, start=x["start"] + start, end=x["end"] + start) for x in sections],
            candidate_cuts=(np.asarray(cuts) + start).tolist(),
            features={
                k: np.asarray(features[k]).tolist()
                for k in ["kick", "bass", "clap", "wave", "impact_score", "rhythm_score"]
            },
            energy_curve=[
                dict(time=float(times[j] + start), rms=float(smooth[j]))
                for j in range(0, len(times), 8)
            ],
            rises=[dict(time=float(times[j] + start), change_db=float(rise[j])) for j in pk],
            downbeat_status="inferred from bass/kick phase; not ground truth",
            method="Executed Maidana BeatSync-Engine and cadence functions, existing pinned repos; original soundtrack samples",
        )
        f.write_text(json.dumps(rec, indent=2))
        results.append(rec)
        print("Music structure", i + 1, tr["title"], round(tempo, 2), flush=True)
    attacks = extract_beats(Path(soundtrack))
    for r in results:
        r["cut_accents"] = sorted(
            set(r["beats"] + [t for t in attacks if r["start"] <= t < r["end"]])
        )
    (cache_dir / "structure.json").write_text(json.dumps(results, indent=2))
    return results


def _portable_structure(soundtrack, tracks):
    """Measured transients and energy only; no invented bars or semantic music sections."""
    import subprocess
    import tempfile

    sr, frame = 11025, 512
    frequency = np.fft.rfftfreq(frame, 1 / sr)
    results = []
    for i, tr in enumerate(tracks):
        start, end = float(tr['timeline_start']), float(tr['timeline_end'])
        parts = {k: [] for k in ('rms', 'flux', 'kick', 'bass', 'clap')}
        previous = None
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(start),
                '-i', str(soundtrack), '-t', str(end - start), '-vn', '-ac', '1', '-ar', str(sr),
                '-f', 'f32le', '-'], stdout=subprocess.PIPE, stderr=errors)
            try:
                while data := proc.stdout.read(frame * 1024 * 4):
                    y = np.frombuffer(data, dtype='<f4')
                    if not np.isfinite(y).all():
                        raise UltraError('Non-finite soundtrack samples')
                    padded = np.pad(y, (0, (-len(y)) % frame)).reshape(-1, frame)
                    spectrum = np.abs(np.fft.rfft(padded * np.hanning(frame), axis=1))
                    before = np.vstack([spectrum[0] if previous is None else previous, spectrum[:-1]])
                    parts['flux'].append(np.maximum(0, spectrum - before).mean(axis=1))
                    parts['rms'].append(np.sqrt(np.mean(padded ** 2, axis=1)))
                    for name, low, high in [('kick', 40, 120), ('bass', 30, 250), ('clap', 1500, 4500)]:
                        parts[name].append(spectrum[:, (frequency >= low) & (frequency <= high)].mean(axis=1))
                    previous = spectrum[-1]
                code = proc.wait()
                errors.seek(0)
                if code:
                    raise UltraError('Music structure decode failed: ' + errors.read().decode(errors='replace')[-1000:])
            finally:
                proc.stdout.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait()
        if not parts['rms']:
            raise UltraError('Empty soundtrack section')
        values = {k: np.concatenate(v) for k, v in parts.items()}
        times = start + np.arange(len(values['rms'])) * frame / sr
        keep = times < end
        values = {k: v[keep] for k, v in values.items()}; times = times[keep]

        def scale(v):
            lo, hi = float(np.percentile(v, 10)), float(np.percentile(v, 95))
            if hi - lo <= max(1e-8, hi * .01):
                return np.full(len(v), .5 if hi > 1e-7 else 0.)
            return np.clip((v - lo) / (hi - lo), 0., 1.)

        flux = values['flux']
        floor = max(float(np.percentile(flux, 66)), float(np.median(flux)) * 1.5, 1e-7)
        candidates = [j for j in range(1, len(flux) - 1)
                      if flux[j] > floor and flux[j] >= flux[j-1] and flux[j] >= flux[j+1]]
        selected = []
        occupied = np.zeros(len(flux), dtype=bool)
        gap = math.ceil(.27 * sr / frame)
        for j in sorted(candidates, key=lambda j: (-flux[j], j)):
            if not occupied[j]:
                selected.append(j)
                occupied[max(0, j-gap+1):j+gap] = True
        selected.sort()
        beats = times[selected].tolist() if len(selected) >= 2 else []
        selected = selected if beats else []
        energy = scale(values['rms'])
        features = {k: scale(values[k])[selected].tolist() for k in ('kick', 'bass', 'clap')}
        features.update(wave=energy[selected].tolist(), impact_score=scale(flux)[selected].tolist(),
                        rhythm_score=scale(flux)[selected].tolist())
        sections = []
        for at in np.arange(start, end, 8.):
            mask = (times >= at) & (times < min(at + 8, end))
            mean = float(np.mean(energy[mask])) if mask.any() else .5
            sections.append(dict(start=float(at), end=float(min(at + 8, end)),
                                 energy=mean, label='low' if mean < .3 else 'high' if mean > .7 else 'medium'))
        step = max(1, round(sr / frame))
        curve = [dict(time=float(times[j]), rms=float(values['rms'][j])) for j in range(0, len(times), step)]
        rises = []
        for a, b in zip(curve, curve[1:]):
            change = float(20 * np.log10((b['rms'] + 1e-7) / (a['rms'] + 1e-7)))
            if change >= 3 and (not rises or b['time'] - rises[-1]['time'] >= 3):
                rises.append(dict(time=b['time'], change_db=change))
        results.append(dict(index=i, title=tr.get('title', f'Track {i+1}'), start=start, end=end,
            bpm=float(60 / np.median(np.diff(beats))) if len(beats) > 2 else 0.,
            beats=beats, cut_accents=beats, candidate_cuts=beats, downbeats=[], features=features,
            sections=sections, energy_curve=curve, rises=rises,
            downbeat_status='Not inferred; transient candidates are not a verified bar grid',
            method='portable FFmpeg/NumPy spectral flux and band energy v1; sections and BPM are inferred'))
    return results


def _validate_structure(rows, tracks):
    if not isinstance(rows, list) or len(rows) != len(tracks):
        raise UltraError('Invalid cached music structure')
    try:
        for row, track in zip(rows, tracks):
            if row['start'] != track['timeline_start'] or row['end'] != track['timeline_end']:
                raise ValueError('track bounds differ')
            beats, wave = row['beats'], row['features']['wave']
            if len(beats) != len(wave) or any(not math.isfinite(v) for v in [*beats, *wave]):
                raise ValueError('invalid feature grid')
            if beats != sorted(set(beats)) or any(not row['start'] <= v < row['end'] for v in beats):
                raise ValueError('invalid beat bounds')
            accents = row.get('cut_accents', beats)
            if any(not math.isfinite(v) or not row['start'] <= v < row['end'] for v in accents):
                raise ValueError('invalid accent bounds')
    except (KeyError, TypeError, ValueError) as exc:
        raise UltraError(f'Invalid cached music structure: {exc}') from exc
    return rows


def analyze_structure(soundtrack, tracks, cache_dir, legacy_root=None):
    """Portable analysis by default; an explicit root selects retained legacy analyzers."""
    import hashlib
    import json
    from pathlib import Path
    from .catalogue import save, sha256
    from .media import probe

    soundtrack, cache_dir = Path(soundtrack), Path(cache_dir)
    duration = probe(soundtrack)['duration']
    if not isinstance(tracks, list) or not tracks:
        raise UltraError('Music structure requires a nonempty tracklist')
    try:
        for track in tracks:
            start, end = track['timeline_start'], track['timeline_end']
            if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= duration + .05:
                raise ValueError('track outside soundtrack')
    except (KeyError, TypeError, ValueError) as exc:
        raise UltraError(f'Invalid music structure tracklist: {exc}') from exc
    backend = 'portable-v1'
    if legacy_root is not None:
        root = Path(legacy_root).resolve()
        for relative in ('BeatSync-Engine/src/auto_mode/__init__.py', 'cadence/src/auto_mode/__init__.py'):
            if not (root / relative).is_file():
                raise UltraError(f'Missing retained musical analyzer: {root / relative}')
        backend = {'method': 'legacy-v2', 'root': str(root),
                   'sources': {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob('*.py'))}}
    digest = hashlib.sha256(json.dumps([sha256(soundtrack), tracks, backend], sort_keys=True).encode()).hexdigest()
    folder = cache_dir / digest
    cached = folder / 'structure.json'
    if cached.exists():
        try:
            return _validate_structure(json.loads(cached.read_text()), tracks)
        except (OSError, ValueError) as exc:
            raise UltraError(f'Invalid cached music structure: {cached}: {exc}') from exc
    rows = (_analyze_legacy(soundtrack, tracks, folder / 'legacy', legacy_root)
            if legacy_root is not None else _portable_structure(soundtrack, tracks))
    _validate_structure(rows, tracks)
    save(cached, rows)
    return rows
