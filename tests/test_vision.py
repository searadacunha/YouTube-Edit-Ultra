import sys
import io
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.vision import analyze, motion_candidates


def test_boundary_peak_does_not_discard_other_actions(tmp_path):
    motions = [0.0] * 120
    motions[35:45] = [20.0] * 10
    motions[-1] = 1000.0

    actions = motion_candidates(
        motions, tmp_path / "source.mp4", duration=60, sport="generic"
    )

    assert any(15 <= action.peak <= 25 for action in actions)


def test_scene_detection_has_its_own_cache(tmp_path, monkeypatch):
    from youtube_edit_ultra import vision

    source = tmp_path / "source.mp4"
    source.touch()
    monkeypatch.setattr(vision, "probe", lambda _: {"has_video": True, "duration": 60})
    scans = []
    monkeypatch.setattr(vision, "scan_motion", lambda _: (scans.append(True) or [0.0] * 120, []))
    detections = []
    monkeypatch.setitem(sys.modules, "scenedetect", SimpleNamespace(
        ContentDetector=lambda **_: object(),
        detect=lambda *_: detections.append(True) or [],
    ))

    _, fast = analyze(source, tmp_path / "cache", "football")
    _, scenes = analyze(source, tmp_path / "cache", "football", scene_detect=True)
    _, cached = analyze(source, tmp_path / "cache", "football", scene_detect=True)

    assert len(scans) == 2
    assert len(detections) == 1
    assert fast["scene_detection"] is False
    assert scenes["scene_detection"] is True
    assert cached == scenes


def test_uniform_camera_motion_is_not_an_action(tmp_path):
    # Previously every equally high score reached the percentile threshold,
    # producing repeated false event candidates during sustained camera motion.
    actions = motion_candidates([20.0] * 120, tmp_path / "pan.mp4",
                                duration=60, sport="football")
    assert actions == []


def test_local_motion_burst_still_produces_candidate(tmp_path):
    motions = [2.0] * 120
    motions[48:58] = [35.0] * 10
    actions = motion_candidates(motions, tmp_path / "burst.mp4",
                                duration=60, sport="boxing")
    assert any(23 <= event.peak <= 29 for event in actions)
    assert all(event.provenance == "heuristic" for event in actions)


def test_motion_pipe_drains_large_stderr_without_deadlock():
    # The child stands in for a noisy decoder; a timeout makes a deadlock test bounded.
    script = '''
from pathlib import Path
import subprocess, sys
from youtube_edit_ultra import vision
original = subprocess.Popen
def noisy_decoder(*args, **kwargs):
    return original([sys.executable, '-c',
        "import sys; sys.stderr.buffer.write(b'x'*262144); sys.stderr.flush(); sys.stdout.buffer.write(bytes(range(8)))"], **kwargs)
vision.subprocess.Popen = noisy_decoder
motion, cuts = vision.scan_motion(Path('noisy.mp4'), resolution=(2, 2))
assert len(motion) == 2
'''
    subprocess.run([sys.executable, "-c", script], check=True, timeout=10,
                   capture_output=True)


@pytest.mark.parametrize("raw", [b"", b"\0" * 5])
def test_motion_pipe_rejects_empty_or_partial_frames(tmp_path, monkeypatch, raw):
    from youtube_edit_ultra import vision
    process = SimpleNamespace(stdout=io.BytesIO(raw), stderr=io.BytesIO(b""),
                              wait=lambda: 0, poll=lambda: 0)
    monkeypatch.setattr(vision.subprocess, "Popen", lambda *a, **k: process)
    with pytest.raises(UltraError, match="image|trame"):
        vision.scan_motion(tmp_path / "broken.mp4", resolution=(2, 2))


def test_motion_cache_hashes_content_even_when_stat_is_restored(tmp_path, monkeypatch):
    from youtube_edit_ultra import vision
    source = tmp_path / "source.mp4"
    source.write_bytes(b"first")
    original = source.stat()
    monkeypatch.setattr(vision, "probe", lambda _: {"has_video": True, "duration": 60})
    scans = []
    monkeypatch.setattr(vision, "scan_motion", lambda _: (scans.append(True) or [0.0] * 120, []))
    analyze(source, tmp_path / "cache", "boxing")
    source.write_bytes(b"other")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    analyze(source, tmp_path / "cache", "boxing")
    assert len(scans) == 2


def test_motion_cache_rejects_malformed_actions(tmp_path, monkeypatch):
    from youtube_edit_ultra import vision
    source = tmp_path / "source.mp4"
    source.write_bytes(b"cache fixture")
    monkeypatch.setattr(vision, "probe", lambda _: {"has_video": True, "duration": 60})
    monkeypatch.setattr(vision, "scan_motion", lambda _: ([0.0] * 120, []))
    analyze(source, tmp_path / "cache", "boxing")
    cache = next((tmp_path / "cache").glob("*.json"))
    payload = json.loads(cache.read_text())
    payload["actions"] = [{"source": str(source), "start": 10, "peak": 5, "end": 2,
                           "sport": "boxing", "label": "invalid", "confidence": .2,
                           "provenance": "heuristic"}]
    cache.write_text(json.dumps(payload))
    with pytest.raises(UltraError, match="[Cc]ache"):
        analyze(source, tmp_path / "cache", "boxing")


def test_motion_scan_real_tiny_video(tmp_path):
    from youtube_edit_ultra.vision import scan_motion
    source = tmp_path / "tiny.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=32x32:r=10:d=1", "-c:v", "libx264", str(source)],
                   check=True, capture_output=True)
    motion, cuts = scan_motion(source, resolution=(16, 16))
    assert len(motion) == 2 and len(cuts) <= 1
