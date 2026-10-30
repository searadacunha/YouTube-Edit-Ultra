from dataclasses import replace
from pathlib import Path

import pytest

from youtube_edit_ultra.editorial import editorial_integrity, plan_editorial
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit
from youtube_edit_ultra.render import render_streamed


def structure(energy=0.8):
    return [dict(start=0, end=100, beats=list(range(101)), features=dict(wave=[energy] * 101))]


def shot(i, core=1.0, kind="action"):
    a = i * 10
    return dict(
        source="sport.mp4",
        safe_start=a,
        core_start=a + 1,
        core_end=a + 1 + core,
        safe_end=a + 6,
        peak=a + 1.5,
        label=str(i),
        kind=kind,
    )


def test_music_cuts_preserve_cores_without_overlap():
    shots = [shot(i) for i in range(10)]
    edits = plan_editorial(shots, structure(), 20)
    assert len(edits) >= 5
    assert all(e.timeline_end == round(e.timeline_end) for e in edits)
    assert editorial_integrity(edits, shots, 20)["all_selected_event_windows_preserved"]
    assert len(set(e.label for e in edits)) == len(edits)


def test_long_combination_wins_over_fast_music():
    s = shot(0, core=5)
    s["safe_end"] = 7
    edits = plan_editorial([s], structure(), 6)
    assert edits[0].source_start <= 1 and edits[0].source_end >= 6


def test_no_filler_or_music_truncation_when_actions_exhausted():
    with pytest.raises(UltraError, match="coverage exhausted"):
        plan_editorial([shot(0)], structure(), 20)


def test_low_section_prefers_context():
    rows = [shot(0, kind="insert"), shot(1)]
    edits = plan_editorial(rows, structure(0.1), 3)
    assert edits[0].label == "0"


def test_protected_core_violation_is_reported():
    s = shot(0, core=2)
    e = Edit("sport.mp4", 1, 2, 0, 1, "0", 1.5, "candidate", 0.5)
    r = editorial_integrity([e], [s], 1)
    assert not r["all_selected_event_windows_preserved"]
    assert not r["semantic_completeness_guaranteed"]


def test_intro_overlap_and_speed_changes_are_rejected():
    e = Edit("sport.mp4", 0, 2, 0, 2, "intro", None, "visual_review", 1)
    r = editorial_integrity([e, replace(e, timeline_start=2, timeline_end=4)], [], 4, intro=[e])
    assert any(x["reason"] == "repeated source interval" for x in r["violations"])
    assert editorial_integrity([replace(e, timeline_end=1)], [], 1, intro=[e])["violations"]


@pytest.mark.parametrize("field,value", [("core_end", 9), ("safe_start", -1)])
def test_invalid_protected_window(field, value):
    s = shot(0)
    s[field] = value
    with pytest.raises(UltraError):
        plan_editorial([s], structure(), 3)


def test_streaming_preserves_existing_output_and_disk_reserve(tmp_path, monkeypatch):
    import shutil

    from youtube_edit_ultra import render

    out = tmp_path / "existing.mp4"
    out.write_bytes(b"original")
    e = Edit("sport.mp4", 0, 2, 0, 2, "action", 1, "candidate", 1)
    with pytest.raises(UltraError, match="Preserve existing"):
        render_streamed([e], Path("music"), out)
    assert out.read_bytes() == b"original"
    monkeypatch.setattr(render, "probe", lambda p: dict(duration=20, has_audio=True))
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("Usage", (), {"free": 100})())
    with pytest.raises(UltraError, match="Insufficient space"):
        render_streamed([e], Path("music"), tmp_path / "new.mp4")
    assert not (tmp_path / "new.mp4").exists()


def test_create_uses_reviewed_shots_and_preserves_prepared_mix(tmp_path, monkeypatch):
    import json
    from youtube_edit_ultra import cli, editorial

    video = tmp_path / "athlete.mp4"
    mix = tmp_path / "accepted.m4a"
    video.write_bytes(b"fixture metadata only")
    mix.write_bytes(b"accepted mix unchanged")
    shots = [
        dict(
            source=str(video),
            safe_start=0,
            core_start=0,
            core_end=6,
            safe_end=6,
            peak=3,
            label="complete reviewed action",
            kind="action",
        )
    ]
    video.with_suffix(".shots.json").write_text(json.dumps(shots))
    tracklist = tmp_path / "tracks.json"
    tracklist.write_text(json.dumps([dict(title="retained", timeline_start=0, timeline_end=6)]))
    spec = tmp_path / "project.json"
    spec.write_text(
        json.dumps(
            dict(
                athlete="Canelo Alvarez",
                duration="6s",
                editorial=True,
                sources=[str(video)],
                sources_only=True,
                prepared_soundtrack=str(mix),
                music_tracklist=str(tracklist),
                output_dir=str(tmp_path / "out"),
            )
        )
    )
    monkeypatch.setattr(cli, "probe", lambda p: dict(duration=6, has_video=True, has_audio=True))
    monkeypatch.setattr(cli, "check_binaries", lambda: None)

    def forbidden(*a, **kw):
        raise AssertionError("Accepted mix or reviewed footage must not be rebuilt/reanalyzed")

    monkeypatch.setattr(cli, "build_soundtrack", forbidden)
    monkeypatch.setattr(cli, "analyze", forbidden)
    monkeypatch.setattr(cli, "extract_beats", lambda *a, **kw: list(range(7)))
    monkeypatch.setattr(editorial, "analyze_structure", lambda *a: structure())
    calls = []

    def render(edits, soundtrack, output, **kwargs):
        calls.append((edits, soundtrack))
        return dict(output=str(output))

    monkeypatch.setattr(cli, "render_streamed", render)
    monkeypatch.setattr(cli, "_thumbnail_and_metadata", lambda *a: (tmp_path / "thumb.jpg", {}))
    monkeypatch.setattr(cli, "create_storyboard", lambda *a: tmp_path / "story.jpg")
    assert cli.main(["create", "--spec", str(spec), "--strict-actions"]) == 0
    assert calls[0][1] == mix and len(calls[0][0]) == 1
    assert mix.read_bytes() == b"accepted mix unchanged"
    integrity = json.loads(
        next((tmp_path / "out").rglob("action_integrity_report.json")).read_text()
    )
    assert integrity["all_selected_event_windows_preserved"]


def test_streamed_ambience_is_sample_aligned_and_under_music(tmp_path):
    import subprocess

    import numpy as np

    src, music, out = tmp_path / "src.mp4", tmp_path / "music.wav", tmp_path / "out.mp4"
    # Loud 2 kHz burst at source 1.0-1.5 s; the shot starts at source 0.5 s, so it is heard at 0.5 s.
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:r=30:d=4",
                    "-f", "lavfi", "-i", "aevalsrc='if(between(t,1,1.5),0.9*sin(2*PI*2000*t),0)':s=48000:d=4",
                    "-shortest", "-c:v", "libx264", "-c:a", "aac", "-ac", "2", str(src)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=100:r=48000:d=4",
                    "-af", "volume=0.6", "-ac", "2", str(music)], check=True)
    e = [Edit(str(src), .5, 2.5, 0, 2, "action", None, "candidate", 1),
         Edit(str(src), 2.5, 3.5, 2, 3, "action", None, "candidate", 1)]
    render_streamed(e, music, out, width=64, height=64, reserve_bytes=0)
    y = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-ac", "1", "-ar", "48000",
                                      "-f", "f32le", "-"], capture_output=True, check=True).stdout, np.float32)
    f = np.fft.rfft(y)
    f[np.fft.rfftfreq(len(y), 1 / 48000) < 1000] = 0
    burst = np.fft.irfft(f, len(y))
    onset = np.argmax(np.abs(burst) > .5 * np.abs(burst).max()) / 48000
    assert abs(onset - .5) < .005
    rms = lambda x: np.sqrt(np.mean(x ** 2))
    assert 20 * np.log10(rms(burst[:96000]) / rms(y[:96000] - burst[:96000])) < -19
    assert not list(tmp_path.glob("*.ambience.flac"))
