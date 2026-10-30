"""CPU video scan: motion candidates, broadcast cuts, cached per source.

Camera movement and crowd shots can create false positives. Semantic certainty
requires annotations or a pretrained model's imported spotting results.
"""
from __future__ import annotations

import json
import hashlib
import math
import subprocess
from collections import deque
from pathlib import Path
from threading import Thread

import numpy as np

from .events import Action, make_action, validate_no_overlap
from .catalogue import save, sha256
from .media import UltraError, probe
from .spec import SPORT_PRESETS


def scan_motion(source: Path, *, sample_fps: float = 2.0, resolution: tuple[int, int] = (192, 108),
                scan_limit: float | None = None) -> tuple[list[float], list[float]]:
    """Sample via FFmpeg pipe, avoiding costly per-frame seeking and giant arrays."""
    w, h = resolution
    if (not math.isfinite(sample_fps) or sample_fps <= 0 or
            any(type(x) is not int or x <= 0 for x in (w, h)) or
            (scan_limit is not None and (not math.isfinite(scan_limit) or scan_limit <= 0))):
        raise UltraError("Paramètres d'analyse vidéo invalides")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-vf", f"fps={sample_fps},scale={w}:{h},format=gray", "-an"]
    if scan_limit is not None:
        command.extend(["-t", str(scan_limit)])
    command.extend(["-f", "rawvideo", "-pix_fmt", "gray", "-"])
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Drain concurrently, retaining only a bounded diagnostic tail.
    errors: deque[bytes] = deque(maxlen=16)
    def drain_errors():
        if proc.stderr is not None:
            for chunk in iter(lambda: proc.stderr.read(4096), b""):
                errors.append(chunk)
    reader = Thread(target=drain_errors, daemon=True)
    reader.start()
    frame_size = w * h
    previous = None
    motions: list[float] = []
    cuts: list[float] = []
    try:
        frame_number = 0
        while True:
            assert proc.stdout is not None
            frame = bytearray()
            while len(frame) < frame_size:
                chunk = proc.stdout.read(frame_size - len(frame))
                if not chunk:
                    break
                frame.extend(chunk)
            if not frame:
                break
            if len(frame) != frame_size:
                raise UltraError(f"Trame vidéo incomplète : {source}, image {frame_number + 1} "
                                 f"({len(frame)}/{frame_size} octets)")
            arr = np.frombuffer(frame, dtype=np.uint8).astype(np.int16)
            if previous is not None:
                absolute = np.abs(arr - previous)
                change = float(absolute.mean())
                motions.append(change)
                # Large abrupt changes are likely broadcast cuts, not athlete speed.
                if change >= 39.0:
                    cuts.append(frame_number / sample_fps)
            else:
                motions.append(0.0)
            previous = arr
            frame_number += 1
        status = proc.wait()
        reader.join()
        stderr = b"".join(errors).decode("utf-8", errors="replace")
        if status:
            raise UltraError(f"Analyse FFmpeg échouée : {source.name}: {stderr[-1000:]}")
        if not motions:
            raise UltraError(f"Aucune image vidéo décodée : {source}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        reader.join()
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()
    return motions, cuts


def motion_candidates(motions: list[float], source: Path, *, duration: float, sport: str,
                      sample_fps: float = 2.0, cuts: list[float] | None = None) -> list[Action]:
    if len(motions) < 4:
        return []
    pre, post = SPORT_PRESETS[sport]["lead"], SPORT_PRESETS[sport]["trail"]
    scores = np.asarray(motions, dtype=np.float32)
    if len(scores) >= 5:
        smooth = np.convolve(scores, np.ones(5) / 5, mode="same")
    else:
        smooth = scores
    # A sustained camera pan can give every frame a high absolute difference.
    # Require a local burst above the video's own median activity; a uniform
    # high-motion baseline is not evidence of repeated sporting actions.
    baseline = float(np.median(smooth))
    deviation = float(np.median(np.abs(smooth - baseline)))
    threshold = max(6.0, float(np.percentile(smooth, 72)),
                    baseline + max(2.0, 1.5 * deviation))
    peaks = []
    min_spacing = max(8.0, (pre + post) * 0.75)
    for i in np.argsort(smooth)[::-1]:
        t = float(i) / sample_fps
        if smooth[i] < threshold:
            break
        # Scores are sorted by strength, not by time. A boundary peak must
        # not hide lower-scoring actions elsewhere in the source.
        if t < 1 or t > duration - 1:
            continue
        if any(abs(t - old) < min_spacing for old in peaks):
            continue
        if cuts and any(abs(t - cut) <= 0.75 for cut in cuts):
            continue
        peaks.append(t)
    peaks.sort()
    # No claim that a movement burst equals a goal or KO.
    values = []
    for t in peaks:
        a = max(0.0, t - pre)
        b = min(duration, t + post)
        if b - a >= SPORT_PRESETS[sport]["min_event"]:
            values.append(make_action(source, a, t, b, duration, sport,
                                      "motion_candidate", 0.25, "heuristic", padding=0))
    # Joining repeated peaks keeps dribble → shot → celebration and punch combinations intact.
    # Very long merges are allowed: fidelity to the action beats quick cuts.
    return validate_no_overlap(values, max_span=55.0)


def analyze(source: Path, cache_dir: Path, sport: str, *, scene_detect: bool = False) -> tuple[list[Action], dict]:
    source = source.resolve()
    before = source.stat()
    signature = (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    binding = {"version": 5, "source": str(source), "sha256": sha256(source),
               "sport": sport, "preset": SPORT_PRESETS[sport], "scene_detect": scene_detect,
               "sample_fps": 2.0, "resolution": [192, 108]}
    info = probe(source)
    if not info["has_video"] or not math.isfinite(info["duration"]) or info["duration"] < 1:
        raise UltraError(f"Ce média n'est pas une vidéo valide : {source}")
    def unchanged():
        after = source.stat()
        if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != signature:
            raise UltraError(f"Source modifiée pendant l'analyse vidéo : {source}")
    unchanged()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text())
            if not isinstance(payload, dict) or payload.get("binding") != binding:
                raise ValueError("source ou paramètres différents")
            meta, rows = payload["meta"], payload["actions"]
            if (not isinstance(meta, dict) or not isinstance(rows, list) or
                    meta.get("source") != str(source) or meta.get("duration") != info["duration"] or
                    meta.get("scene_detection") is not scene_detect or
                    meta.get("semantic_events_confirmed") is not False or
                    type(meta.get("sampled_frames")) is not int or meta["sampled_frames"] <= 0 or
                    type(meta.get("detected_cuts")) is not int or meta["detected_cuts"] < 0):
                raise ValueError("structure de résultats invalide")
            actions = [Action(**d) for d in rows]
            for action in actions:
                if (action.source != str(source) or action.sport != sport or
                        action.provenance != "heuristic" or not isinstance(action.label, str) or
                        not all(type(x) in (int, float) and math.isfinite(x) for x in
                                (action.start, action.peak, action.end, action.confidence)) or
                        not 0 <= action.start <= action.peak <= action.end <= info["duration"] + .001 or
                        action.duration < .15 or not 0 <= action.confidence <= 1):
                    raise ValueError("action invalide")
            unchanged()
            return actions, meta
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise UltraError(f"Cache d'analyse vidéo invalide : {cache_path}: {exc}") from exc
    motion, cuts = scan_motion(source)
    if scene_detect:
        try:
            from scenedetect import detect, ContentDetector
        except ImportError as exc:
            raise UltraError("Installer PySceneDetect : pip install '.[scenes]'") from exc
        # Accuracy mode. This rescans the input at full decoding cost.
        detected = detect(str(source), ContentDetector(threshold=32.0))
        cuts = [float(scene[1].get_seconds()) for scene in detected[:-1]]
    actions = motion_candidates(motion, source, duration=info["duration"], sport=sport,
                                cuts=cuts)
    meta = {"source": str(source), "duration": info["duration"],
            "sampled_frames": len(motion), "detected_cuts": len(cuts),
            "detector": "low_resolution_motion+scene_change",
            "scene_detection": scene_detect,
            "semantic_events_confirmed": False}
    unchanged()
    save(cache_path, {"binding": binding, "actions": [a.as_dict() for a in actions], "meta": meta})
    return actions, meta
