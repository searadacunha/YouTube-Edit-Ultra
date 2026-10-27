import sys
from types import SimpleNamespace

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
