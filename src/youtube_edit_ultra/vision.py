"""CPU video scan: motion candidates, broadcast cuts, cached per source.

Camera movement and crowd shots can create false positives. Semantic certainty
requires annotations or a pretrained model's imported spotting results.
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
from pathlib import Path

import numpy as np

from .events import Action, make_action, validate_no_overlap
from .media import UltraError, fingerprint, probe
from .spec import SPORT_PRESETS


def scan_motion(source: Path, *, sample_fps: float = 2.0, resolution: tuple[int, int] = (192, 108),
                scan_limit: float | None = None) -> tuple[list[float], list[float]]:
    """Sample via FFmpeg pipe, avoiding costly per-frame seeking and giant arrays."""
    w, h = resolution
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-vf", f"fps={sample_fps},scale={w}:{h},format=gray", "-an"]
    if scan_limit is not None:
        command.extend(["-t", str(scan_limit)])
    command.extend(["-f", "rawvideo", "-pix_fmt", "gray", "-"])
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = w * h
    previous = None
    motions: list[float] = []
    cuts: list[float] = []
    try:
        frame_number = 0
        while True:
            assert proc.stdout is not None
            frame = proc.stdout.read(frame_size)
            if not frame or len(frame) < frame_size:
                break
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
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        status = proc.wait()
        if status:
            raise UltraError(f"Analyse FFmpeg échouée : {source.name}: {stderr[-1000:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
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
    info = probe(source)
    if not info["has_video"] or info["duration"] < 1:
        raise UltraError(f"Ce média n'est pas une vidéo valide : {source}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"{fingerprint(source)}-{sport}-scenes{int(scene_detect)}-v4"
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text())
        return [Action(**d) for d in payload["actions"]], payload["meta"]
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
    cache_path.write_text(json.dumps({"actions": [a.as_dict() for a in actions],
                                     "meta": meta}, indent=2))
    return actions, meta
