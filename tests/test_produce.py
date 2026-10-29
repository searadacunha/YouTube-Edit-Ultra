import json
import pytest
from youtube_edit_ultra import catalogue
from youtube_edit_ultra.spec import parse_prompt


def test_prompt_crawford():
    p = parse_prompt("Terence Crawford 30 minutes R&B 2000s")
    assert p == dict(
        athlete="Terence Crawford",
        sport="boxing",
        style="rnb-2000s",
        duration_seconds=1800,
    )


def test_title_variants():
    assert catalogue.family("La Bebe (Remix)") == catalogue.family("La Bebe")
    assert catalogue.family("ROMPE - Radio Edit") == catalogue.family("Rompe")


def test_scan_history_and_missing(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    (root / "loop").symlink_to(root, target_is_directory=True)
    (root / "full_music.json").write_text(
        json.dumps(
            {"tracks": [{"title": "Rompe", "artist": "Daddy Yankee", "sha256": "old"}]}
        )
    )
    state = catalogue.scan([root], catalogue.empty())
    assert len(state["used"]) == 1
    assert state["used"][0]["family"] == "rompe"
    assert not state["errors"]


def test_select_requires_rights_and_deduplicates():
    a = dict(
        path="a",
        sha256="one",
        available=True,
        kind="audio",
        title="Rompe",
        artist="Daddy Yankee",
        genre="reggaeton",
    )
    b = dict(a, path="b", sha256="two", title="Rompe (Remix)")
    state = catalogue.empty()
    state["media"] = {"a": a, "b": b}
    assert catalogue.select_music(state, "reggaeton", None)[0] == []
    state["permissions"] = {
        k: {"evidence": "test ownership", "reuse": True} for k in ["one", "two"]
    }
    assert len(catalogue.select_music(state, "reggaeton", None)[0]) == 1
    state["used"] = [{"family": "rompe"}]
    assert catalogue.select_music(state, "reggaeton", None)[0] == []


def test_scan_corrupt_history_reports_error(tmp_path):
    (tmp_path / "full_music.json").write_text("{bad json")
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert len(state["errors"]) == 1


def test_spotify_match_requires_artist_and_version():
    row = dict(
        path="a",
        sha256="x",
        available=True,
        kind="audio",
        title="Song",
        artist="Artist",
        genre="",
    )
    state = catalogue.empty()
    state["media"] = {"a": row}
    state["permissions"] = {"x": {"reuse": True, "evidence": "owned"}}
    playlist = {"tracks": [{"name": "Song (Remix)", "artists": [{"name": "Artist"}]}]}
    assert not catalogue.select_music(state, "anything", playlist)[0]
    playlist["tracks"][0]["name"] = "Song"
    assert len(catalogue.select_music(state, "anything", playlist)[0]) == 1


def test_license_not_inferred_from_title():
    from youtube_edit_ultra.produce import cc_by

    assert not cc_by({"title": "Official Creative Commons Canelo", "license": None})
    assert not cc_by({"license": "Standard YouTube License"})
    assert cc_by({"license": "Creative Commons Attribution license (reuse allowed)"})


def test_produce_end_to_end(tmp_path):
    import subprocess
    import numpy as np
    from youtube_edit_ultra.cli import main
    from youtube_edit_ultra.media import run, probe

    root = tmp_path / "inputs"
    root.mkdir()
    video = root / "Canelo Alvarez test.mp4"
    audio = root / "reggaeton - Test Artist - New Song.wav"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ]
    )
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0.1*sin(2*PI*(300*t+20*t*t)):s=48000:d=8",
            "-metadata",
            "title=New Song",
            "-metadata",
            "artist=Test Artist",
            str(audio),
        ]
    )
    video.with_suffix(".actions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "start": 0,
                        "peak": 3,
                        "end": 6,
                        "label": "synthetic_test_not_boxing",
                    }
                ]
            }
        )
    )
    folder = tmp_path / "state"
    state = catalogue.empty()
    state["permissions"] = {
        catalogue.sha256(p): {"reuse": True, "evidence": "generated synthetic test"}
        for p in [video, audio]
    }
    catalogue.save(folder / "catalogue.json", state)
    command = [
        "produce",
        "Canelo Alvarez 6s reggaeton",
        "--state-dir",
        str(folder),
        "--root",
        str(root),
        "--output-dir",
        str(tmp_path / "exports"),
        "--offline",
        "--strict-actions",
        "--width",
        "320",
        "--height",
        "180",
    ]
    assert main(command) == 0
    output = next((tmp_path / "exports").rglob("montage.mp4"))
    assert probe(output)["duration"] == pytest.approx(6, abs=0.15)
    qa = json.loads((output.parent / "verification_report.json").read_text())
    assert qa["full_decode"] and not qa["semantic_actions_verified"]
    for name in [
        "thumbnail.jpg",
        "storyboard.jpg",
        "edit_plan.json",
        "music_tracklist.json",
        "source_report.json",
        "render_report.json",
        "youtube_metadata.json",
    ]:
        assert (output.parent / name).is_file()

    def wave(p):
        c = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(p),
                "-t",
                "5",
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "f32le",
                "-",
            ],
            capture_output=True,
            check=True,
        )
        return np.frombuffer(c.stdout, dtype=np.float32)

    a, b = wave(audio), wave(output)
    # Test the real AAC/FFmpeg chain, allowing <25 ms encoder/filter latency.
    scores = []
    for shift in range(-200, 201):
        x, y = (
            (a[-shift:], b[: len(b) + shift])
            if shift < 0
            else (a[: len(a) - shift or None], b[shift:])
        )
        n = min(len(x), len(y))
        scores.append(float(np.corrcoef(x[:n], y[:n])[0, 1]))
    assert max(scores) > 0.97
    # Persisted usage must prevent silently recycling the soundtrack.
    assert main(command) == 2
    blocked = sorted((tmp_path / "exports").glob("*/production_report.json"))[-1]
    assert json.loads(blocked.read_text())["status"] == "BLOCKED"


def test_changed_content_loses_authorization(tmp_path):
    p = tmp_path / "asset.mp3"
    p.write_bytes(b"first")
    row = {"sha256": catalogue.sha256(p), "available": True}
    state = catalogue.empty()
    state["permissions"][row["sha256"]] = {"reuse": True, "evidence": "owner"}
    assert catalogue.permitted(state, row)
    p.write_bytes(b"changed")
    row["sha256"] = catalogue.sha256(p)
    assert not catalogue.permitted(state, row)


def test_duration_validation_on_real_export(tmp_path):
    from youtube_edit_ultra.media import run, UltraError
    from youtube_edit_ultra.produce import verify_output

    p = tmp_path / "short.mp4"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=25:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(p),
        ]
    )
    with pytest.raises(UltraError, match="Durée finale"):
        verify_output(p, 1800)


def test_download_only_trusted_licensed_candidate(tmp_path, monkeypatch):
    from youtube_edit_ultra import produce
    from youtube_edit_ultra.cli import main

    candidates = [
        dict(
            title="Canelo Alvarez official",
            license="Standard YouTube License",
            webpage_url="https://example.org/no",
        ),
        dict(
            title="Canelo Alvarez licensed",
            license="Creative Commons Attribution license (reuse allowed)",
            webpage_url="https://example.org/yes",
            uploader="test",
            channel_url="https://example.org/publisher",
        ),
    ]
    monkeypatch.setattr(produce, "discover", lambda *a: candidates)
    called = []

    def download(urls, dest):
        called.extend(urls)
        raise produce.UltraError("test network unavailable")

    monkeypatch.setattr(produce, "download_explicit", download)
    root = tmp_path / "inputs"
    root.mkdir()
    catalogue.save(
        tmp_path / "state/config.json",
        {"trusted_cc_publishers": ["https://example.org/publisher"]},
    )
    assert (
        main(
            [
                "produce",
                "Canelo Alvarez 30m reggaeton",
                "--root",
                str(root),
                "--state-dir",
                str(tmp_path / "state"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert called == ["https://example.org/yes"]
    report = next((tmp_path / "out").glob("*/production_report.json"))
    assert "test network unavailable" in json.loads(report.read_text())["warnings"]


def test_ignore_marker(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / ".ultra-ignore").touch()
    (fixtures / "full_music.json").write_text("deliberately invalid")
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert not state["errors"] and not state["used"]


def test_2000s_includes_2009_not_2010():
    state = catalogue.empty()
    row = dict(
        path="rnb-2000s/song.wav",
        sha256="x",
        available=True,
        kind="audio",
        title="New Song",
        artist="Artist",
        genre="rnb-2000s",
        release_date="2009-01-01",
    )
    state["media"] = {"song": row}
    state["permissions"] = {"x": {"reuse": True, "evidence": "owner"}}
    assert catalogue.select_music(state, "rnb-2000s", None)[0]
    row["release_date"] = "2010-01-01"
    assert not catalogue.select_music(state, "rnb-2000s", None)[0]
