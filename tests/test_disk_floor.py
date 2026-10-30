"""Shared disk floor: simulated free space only, no real render or download of any size."""
import shutil
import subprocess
from pathlib import Path

import pytest

from youtube_edit_ultra import media, render
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit

G = 1_000_000_000


def free_space(monkeypatch, *values):
    """disk_usage returns the given free values in order, then repeats the last one."""
    seq = list(values)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": seq.pop(0) if len(seq) > 1 else seq[0]})())


def test_floor_comes_from_env_then_shared_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", "7")
    assert media.floor_bytes() == 7
    monkeypatch.delenv("DISKGUARD_FLOOR_BYTES")
    cfg = tmp_path / "config.json"
    cfg.write_text('{"floor_bytes": 11000000000}')
    monkeypatch.setattr(media, "DISK_GUARD_CONFIG", cfg)
    assert media.floor_bytes() == 11 * G
    monkeypatch.setattr(media, "DISK_GUARD_CONFIG", tmp_path / "absent.json")
    assert media.floor_bytes() == 12 * G


def test_require_space_refuses_under_floor_and_returns_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", str(12 * G))
    free_space(monkeypatch, 14 * G)
    assert media.require_space(tmp_path, G, "x") == 2 * G
    with pytest.raises(UltraError, match="Insufficient space for x"):
        media.require_space(tmp_path, 3 * G, "x")


def fake_segments(monkeypatch, written):
    monkeypatch.setattr(render, "fingerprint", lambda p: "fp")

    def segment(edit, out, **kw):
        out.write_bytes(b"0" * 10)
        written.append(out)
    monkeypatch.setattr(render, "render_segment", segment)


def edits(n):
    return [Edit("src.mp4", i * 2, i * 2 + 2, i * 2, i * 2 + 2, "action", 1, "candidate", 1) for i in range(n)]


def test_segment_render_refuses_before_writing(monkeypatch, tmp_path):
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", str(12 * G))
    written = []
    fake_segments(monkeypatch, written)
    free_space(monkeypatch, 12 * G + 1000)  # under floor + estimate for 6 s of 1080p
    with pytest.raises(UltraError, match="Insufficient space for segment render"):
        render.render_edits(edits(3), Path("music"), tmp_path / "out.mp4", tmp_path / "cache", width=1920, height=1080)
    assert written == [] and not list((tmp_path / "cache").iterdir())


def test_segment_render_stops_cleanly_when_space_runs_out(monkeypatch, tmp_path):
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", str(12 * G))
    written = []
    fake_segments(monkeypatch, written)
    # preflight OK, segment 1 OK, then another program eats the margin before segment 2.
    free_space(monkeypatch, 20 * G, 20 * G, 11 * G)
    with pytest.raises(UltraError, match="before segment 2; finished segments stay cached"):
        render.render_edits(edits(3), Path("music"), tmp_path / "out.mp4", tmp_path / "cache")
    cache = sorted(p.name for p in (tmp_path / "cache").iterdir())
    assert len(written) == 1 and len(cache) == 1 and cache[0].startswith("clip-")  # no .partial left
    assert not (tmp_path / "out.mp4").exists()


def test_streamed_render_stops_and_marks_partial_output(monkeypatch, tmp_path):
    src, music, out = tmp_path / "src.mp4", tmp_path / "music.wav", tmp_path / "out.mp4"
    # Noisy 640x360 so ~5 MB reach the muxer before the stop: it must already be writing the output.
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=13",
                    "-f", "lavfi", "-i", "sine=f=300:r=48000:d=13", "-vf", "noise=alls=80:allf=t",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(src)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=100:r=48000:d=13", "-ac", "2", str(music)],
                   check=True)
    keep = tmp_path / "earlier.mp4"
    keep.write_bytes(b"earlier render")
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", str(12 * G))
    free_space(monkeypatch, *[20 * G] * 12, 11 * G)  # preflight and 11 shots fine, under the floor at shot 12
    e = [Edit(str(src), i, i + 1, i, i + 1, "action", None, "candidate", 1) for i in range(12)]
    with pytest.raises(UltraError, match="Disk reserve reached"):
        render.render_streamed(e, music, out, width=640, height=360)
    assert not out.exists()  # never a partial file under the final name
    [partial] = tmp_path.glob("out.incomplete-*.mp4")
    assert media.probe(partial)["has_video"]  # stopped cleanly: the partial file is a readable MP4
    assert keep.read_bytes() == b"earlier render"


def test_downloads_are_capped_by_what_the_floor_leaves(monkeypatch, tmp_path):
    monkeypatch.setenv("DISKGUARD_FLOOR_BYTES", str(12 * G))
    calls = []
    monkeypatch.setattr(media, "run", lambda cmd, **kw: calls.append(cmd) or "")
    monkeypatch.setattr(media, "downloader_command", lambda: ["yt-dlp"])
    free_space(monkeypatch, 16 * G)
    with pytest.raises(UltraError, match="Aucune vidéo"):  # the fake run saves nothing
        media.download_explicit(["https://example.com/watch?v=x"], tmp_path)
    args = calls[0]
    assert args[args.index("--max-filesize") + 1] == str(G // 2)  # 2 GB job budget covers both source streams and their merged output.
    free_space(monkeypatch, 11 * G)
    calls.clear()
    with pytest.raises(UltraError, match="Insufficient space for video download"):
        media.download_explicit(["https://example.com/watch?v=y"], tmp_path)
    assert calls == []
