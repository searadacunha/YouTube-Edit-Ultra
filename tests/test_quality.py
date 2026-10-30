"""Real tiny FFmpeg exports: encoded audio, packet preservation and honest failure reports."""
import json
import shutil
import subprocess

import numpy as np
import pytest

from youtube_edit_ultra.media import UltraError, run
from youtube_edit_ultra.planner import Edit
from youtube_edit_ultra.render import render_edits, render_streamed


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")


def fixture_video(path, *, duration=3, amplitude=.1, image="testsrc2=s=160x90:r=30"):
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"{image}:d={duration}",
         "-f", "lavfi", "-i", f"aevalsrc={amplitude}*sin(2*PI*997*t):s=48000:d={duration}",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-b:a", "256k", "-shortest", str(path)])
    return path


def audio(path):
    cp = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                         "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(cp.stdout, np.float32)[4800:96000]


@pytest.mark.parametrize("streamed", [False, True])
def test_limiter_does_not_amplify_quiet_soundtrack(tmp_path, streamed):
    src = fixture_video(tmp_path / "source.mp4")
    song = tmp_path / "song.wav"
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=317:r=48000:d=3", str(song)])
    edits = [Edit(str(src), 0, 3, 0, 3, "action", None, "fixture", 1)]
    out = tmp_path / "output.mp4"
    options = dict(width=160, height=90, source_volume=0, music_volume=1)
    if streamed:
        render_streamed(edits, song, out, **options)
    else:
        render_edits(edits, song, out, tmp_path / "cache", **options)
    ratio = np.sqrt(np.mean(audio(out) ** 2) / np.mean(audio(song) ** 2))
    assert ratio == pytest.approx(1, abs=.015)


def test_verified_real_export_and_exact_expectations(tmp_path):
    from youtube_edit_ultra.quality import VerificationError, verify_output
    video = fixture_video(tmp_path / "fixture.mp4")
    report = verify_output(video, 3, width=160, height=90, fps=30)
    assert report["full_decode"] and report["decoded_video_frames"] == 90
    assert report["true_peak_dbfs"] < 0 and not report["quality_flags"]
    with pytest.raises(VerificationError, match="Durée finale") as error:
        verify_output(video, 3.3)
    assert error.value.code == "duration"
    assert json.loads(video.with_suffix(".verification.json").read_text())["status"] == "FAILED"
    with pytest.raises(VerificationError, match="Résolution"):
        verify_output(video, 3, width=1920, height=1080)
    with pytest.raises(VerificationError, match="FPS"):
        verify_output(video, 3, fps=25)


def test_decode_failure_is_saved_and_not_repaired(tmp_path):
    from youtube_edit_ultra.quality import VerificationError, finalize_output
    video = tmp_path / "broken.mp4"
    video.write_bytes(b"not a media file")
    with pytest.raises(VerificationError):
        finalize_output(video, 3, job_dir=tmp_path)
    report = json.loads(video.with_suffix(".verification.json").read_text())
    assert report["status"] == "FAILED" and not report["full_decode"]
    assert not list(tmp_path.glob("*.audio-fixed-*.mp4"))


def test_black_and_freeze_are_not_deliverable(tmp_path):
    from youtube_edit_ultra.quality import VerificationError, finalize_output
    video = fixture_video(tmp_path / "black.mp4", image="color=c=black:s=160x90:r=30")
    with pytest.raises(VerificationError) as error:
        finalize_output(video, 3, job_dir=tmp_path)
    assert error.value.code == "quality_flags"
    assert error.value.report["full_decode"] and error.value.report["quality_flags"]
    assert not list(tmp_path.glob("*.audio-fixed-*.mp4"))


def test_peak_repair_preserves_original_and_h264_packets(tmp_path):
    from youtube_edit_ultra.catalogue import sha256
    from youtube_edit_ultra.quality import VerificationError, finalize_output, verify_output, video_packet_hash
    video = fixture_video(tmp_path / "loud.mp4", amplitude=1.5)
    original_hash = sha256(video)
    with pytest.raises(VerificationError) as error:
        verify_output(video, 3)
    assert error.value.code == "true_peak" and error.value.report["true_peak_dbfs"] >= 0
    report = finalize_output(video, 3, job_dir=tmp_path, width=160, height=90, fps=30)
    assert report["full_decode"] and report["true_peak_dbfs"] <= -1
    assert report["output"] != str(video)
    assert 1 <= len(report["corrections"]) <= 2
    assert sha256(video) == original_hash
    assert video_packet_hash(video) == video_packet_hash(report["output"])


def test_repair_refuses_without_disk_and_leaves_original(tmp_path, monkeypatch):
    from youtube_edit_ultra import quality
    video = fixture_video(tmp_path / "loud.mp4", amplitude=1.5)
    def deny(*args, **kwargs):
        raise UltraError("Insufficient space for audio repair")
    monkeypatch.setattr(quality, "require_space", deny)
    with pytest.raises(UltraError, match="Insufficient space"):
        quality.finalize_output(video, 3, job_dir=tmp_path)
    assert video.exists() and not list(tmp_path.glob("*.audio-fixed-*.mp4"))


def test_repair_rejects_external_and_symlink_input(tmp_path):
    from youtube_edit_ultra.quality import finalize_output
    video = fixture_video(tmp_path / "source.mp4", amplitude=1.5)
    job = tmp_path / "job"
    job.mkdir()
    with pytest.raises(UltraError, match="job"):
        finalize_output(video, 3, job_dir=job)
    link = job / "link.mp4"
    link.symlink_to(video)
    with pytest.raises(UltraError, match="job"):
        finalize_output(link, 3, job_dir=job)


def test_finalization_reuses_verified_bytes_and_rechecks_changed_inputs(tmp_path, monkeypatch):
    from youtube_edit_ultra import quality
    video = fixture_video(tmp_path / "loud.mp4", amplitude=1.5)
    first = quality.finalize_output(video, 3, job_dir=tmp_path)
    verifier = quality.verify_output
    def unexpected(*args, **kwargs):
        raise AssertionError("Unchanged completed job should not be re-encoded or re-decoded")
    monkeypatch.setattr(quality, "verify_output", unexpected)
    assert quality.finalize_output(video, 3, job_dir=tmp_path)["sha256"] == first["sha256"]
    # A changed artifact invalidates the cache before it could be returned as verified.
    from pathlib import Path
    Path(first["output"]).write_bytes(b"corrupt")
    with pytest.raises(AssertionError, match="Unchanged"):
        quality.finalize_output(video, 3, job_dir=tmp_path)
    monkeypatch.setattr(quality, "verify_output", verifier)


def test_audio_retries_are_bounded(tmp_path, monkeypatch):
    from youtube_edit_ultra import quality
    video = fixture_video(tmp_path / "fixture.mp4")
    calls = []
    def always_peak(path, target, **kwargs):
        calls.append(path)
        raise quality.VerificationError("true_peak", "still loud",
                                        {"true_peak_dbfs": 2, "quality_flags": []})
    monkeypatch.setattr(quality, "verify_output", always_peak)
    with pytest.raises(quality.VerificationError, match="still loud"):
        quality.finalize_output(video, 3, job_dir=tmp_path, max_attempts=1)
    assert len(calls) == 2
    assert len(list(tmp_path.glob("*.audio-fixed-*.mp4"))) == 1
    with pytest.raises(ValueError, match="between 0 and 3"):
        quality.finalize_output(video, 3, job_dir=tmp_path, max_attempts=100)


def test_silent_audio_is_not_a_valid_peak_measurement(tmp_path):
    from youtube_edit_ultra.quality import VerificationError, finalize_output
    video = fixture_video(tmp_path / "silent.mp4", amplitude=0)
    with pytest.raises(VerificationError) as error:
        finalize_output(video, 3, job_dir=tmp_path)
    assert any("silence_start" in flag for flag in error.value.report["quality_flags"])
    assert not list(tmp_path.glob("*.audio-fixed-*.mp4"))


def test_delivery_requires_mp4_and_square_pixels(tmp_path):
    from youtube_edit_ultra.quality import VerificationError, verify_output
    other_container = fixture_video(tmp_path / "fixture.mkv")
    with pytest.raises(VerificationError, match="Export MP4"):
        verify_output(other_container, 3)
    source = fixture_video(tmp_path / "source.mp4")
    anamorphic = tmp_path / "anamorphic.mp4"
    run(["ffmpeg", "-v", "error", "-i", str(source), "-vf", "setsar=2",
         "-c:v", "libx264", "-c:a", "copy", str(anamorphic)])
    with pytest.raises(VerificationError, match="Pixels carrés"):
        verify_output(anamorphic, 3)


@pytest.mark.parametrize("options", [{"width": -1}, {"height": 0}, {"fps": 0},
                                    {"fps": 1.5}, {"true_peak_limit": float("nan")}])
def test_invalid_expectations_refused_before_execution(tmp_path, options):
    from youtube_edit_ultra.quality import verify_output
    with pytest.raises(ValueError):
        verify_output(tmp_path / "not-read.mp4", 3, **options)


@pytest.mark.parametrize("streamed", [False, True])
def test_render_preserves_existing_output_before_touching_cache(tmp_path, streamed):
    output = tmp_path / "final.mp4"
    output.write_bytes(b"previous final must stay")
    edits = [Edit("unread-source.mp4", 0, 3, 0, 3, "action", None, "fixture", 1)]
    with pytest.raises(UltraError, match="Preserve existing output"):
        if streamed:
            render_streamed(edits, tmp_path / "unread-music.wav", output)
        else:
            render_edits(edits, tmp_path / "unread-music.wav", output, tmp_path / "cache")
    assert output.read_bytes() == b"previous final must stay"
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("streamed", [False, True])
def test_render_preserves_dangling_output_symlink(tmp_path, streamed):
    output = tmp_path / "final.mp4"
    target = tmp_path / "missing-personal-file.mp4"
    output.symlink_to(target)
    edits = [Edit("unread-source.mp4", 0, 3, 0, 3, "action", None, "fixture", 1)]
    with pytest.raises(UltraError, match="Preserve existing output"):
        if streamed:
            render_streamed(edits, tmp_path / "unread-music.wav", output)
        else:
            render_edits(edits, tmp_path / "unread-music.wav", output, tmp_path / "cache")
    assert output.is_symlink() and not target.exists()


def test_streamed_size_estimate_matches_crawford_budget():
    from youtube_edit_ultra.render import estimate_streamed_bytes
    assert estimate_streamed_bytes(1800) == 1_622_808_000
    assert 0 < estimate_streamed_bytes(3) < 3_000_000
    for duration in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            estimate_streamed_bytes(duration)


def test_streamed_ambience_temp_cannot_replace_existing_file(tmp_path):
    source = fixture_video(tmp_path / "source.mp4")
    output = tmp_path / "final.mp4"
    existing = tmp_path / "final.ambience.flac"
    existing.write_bytes(b"previous personal audio")
    edits = [Edit(str(source), 0, 3, 0, 3, "action", None, "fixture", 1)]
    render_streamed(edits, source, output, width=160, height=90)
    assert existing.read_bytes() == b"previous personal audio"


def test_segment_final_mux_refuses_file_created_after_preflight(tmp_path, monkeypatch):
    from youtube_edit_ultra import render
    source = fixture_video(tmp_path / "source.mp4")
    output = tmp_path / "final.mp4"
    edits = [Edit(str(source), 0, 3, 0, 3, "action", None, "fixture", 1)]
    original = render.require_space
    def check_then_other_writer(path, need, what, *args):
        budget = original(path, need, what, *args)
        if what == "final mix":
            output.write_bytes(b"other writer's final")
        return budget
    monkeypatch.setattr(render, "require_space", check_then_other_writer)
    with pytest.raises(UltraError):
        render_edits(edits, source, output, tmp_path / "cache", width=160, height=90)
    assert output.read_bytes() == b"other writer's final"


def test_streamed_failure_never_renames_another_writers_output(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from youtube_edit_ultra import render
    source = fixture_video(tmp_path / "source.mp4")
    output = tmp_path / "final.mp4"
    edits = [Edit(str(source), 0, 3, 0, 3, "action", None, "fixture", 1)]
    other_video = source.read_bytes()
    checks = []
    def free_space(path):
        checks.append(path)
        if len(checks) == 2:
            output.write_bytes(other_video)
        return SimpleNamespace(free=10**15)
    monkeypatch.setattr(render.shutil, "disk_usage", free_space)
    with pytest.raises(UltraError, match="Preserve existing output"):
        render_streamed(edits, source, output, width=160, height=90)
    assert output.read_bytes() == other_video
