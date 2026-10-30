import json
import hashlib
from pathlib import Path

import pytest

from youtube_edit_ultra.events import from_json
from youtube_edit_ultra import media


def test_import_soccer_annotations(tmp_path):
    source = tmp_path / 'ronaldo.mp4'
    annotation = tmp_path / 'ronaldo.actions.json'
    annotation.write_text(json.dumps({'events': [
        {'start': 10, 'peak': 14, 'end': 19, 'label': 'skill-and-shot'}
    ]}))
    items = from_json(annotation, source, 50, 'football')
    assert len(items) == 1
    assert items[0].start <= 10
    assert items[0].end >= 19
    assert items[0].provenance == 'annotation'


def test_soccer_net_timestamp(tmp_path):
    src = tmp_path / 'match.mp4'
    file = tmp_path / 'match.actions.json'
    file.write_text(json.dumps({'predictions': [{'position': 60000, 'label': 'Goal', 'confidence': .9}]}))
    items = from_json(file, src, 160, 'football')
    assert items[0].peak == 60
    assert items[0].start < items[0].peak < items[0].end
    assert items[0].provenance == 'SoccerNet'


@pytest.mark.parametrize("audio", [False, True])
def test_url_cache_stays_scoped_and_preserves_requested_order(tmp_path, monkeypatch, audio):
    monkeypatch.setattr(media.shutil, "which", lambda _: "yt-dlp")
    urls = ["https://example.org/first", "https://example.org/second"]
    ext = "mp3" if audio else "mp4"

    def fake_download(command):
        if command[0] == "ffprobe":
            return json.dumps({"streams": [{"codec_type": "audio" if audio else "video"}],
                               "format": {"duration": "1"}})
        if command[0] == "ffmpeg":
            return "frame=30\nout_time_us=1000000\nprogress=end\n"
        pattern = command[command.index("-o") + 1]
        # Different URLs may have the same media ID on different hosts.
        output = Path(pattern.replace("%(id)s", "same-id").replace("%(ext)s", ext))
        output.write_text(command[-1], encoding="utf-8")
        return ""

    monkeypatch.setattr(media, "run", fake_download)
    download = media.download_audio_explicit if audio else media.download_explicit
    original = download(urls, tmp_path)
    # Existing unrelated downloads must never enter a later explicit request.
    (tmp_path / f"source-0000-unrelated.{ext}").touch()
    requested = download(list(reversed(urls)), tmp_path)

    assert len(set(original)) == 2
    assert requested == list(reversed(original))
    assert [path.read_text() for path in requested] == list(reversed(urls))
    assert download([urls[1]], tmp_path) == [original[1]]


def test_partial_download_is_not_reported_as_a_video(tmp_path, monkeypatch):
    monkeypatch.setattr(media.shutil, "which", lambda _: "yt-dlp")

    def partial(command):
        pattern = command[command.index("-o") + 1]
        Path(pattern.replace("%(id)s", "id").replace("%(ext)s", "mp4.part")).touch()
        return ""

    monkeypatch.setattr(media, "run", partial)
    with pytest.raises(media.UltraError, match="Aucune vidéo"):
        media.download_explicit(["https://example.org/source"], tmp_path)


@pytest.mark.parametrize("suffix", [".f137.mp4", ".f251.webm", ".temp.mp4", ".orig.mp4"])
def test_unmerged_intermediates_resume_without_becoming_final(tmp_path, monkeypatch, suffix):
    url = "https://example.org/source"
    prefix = "source-" + hashlib.sha256(url.encode()).hexdigest()[:20]
    intermediate = tmp_path / (prefix + "-id" + suffix)
    intermediate.write_bytes(b"retained intermediate")
    final = tmp_path / (prefix + "-id.mp4")
    calls, validated = [], []
    def download(command, *args, **kwargs):
        calls.append(command)
        final.write_bytes(b"completed merged file")
        return ""
    monkeypatch.setattr(media, "downloader_command", lambda: ["yt-dlp"])
    monkeypatch.setattr(media, "_guarded_download", download)
    monkeypatch.setattr(media, "_validate_download", lambda path, kind: validated.append(path))
    assert media.download_explicit([url], tmp_path) == [final]
    assert len(calls) == 1 and validated == [final]
    assert intermediate.read_bytes() == b"retained intermediate"
    assert media.download_explicit([url], tmp_path) == [final]
    assert len(calls) == 1 and validated == [final, final]


def test_successful_command_with_only_intermediates_is_not_completion(tmp_path, monkeypatch):
    url = "https://example.org/source"
    def download(command, *args, **kwargs):
        pattern = command[command.index("-o") + 1]
        Path(pattern.replace("%(id)s", "id.f137").replace("%(ext)s", "mp4")).write_bytes(b"unmerged")
        return ""
    monkeypatch.setattr(media, "downloader_command", lambda: ["yt-dlp"])
    monkeypatch.setattr(media, "_guarded_download", download)
    monkeypatch.setattr(media, "_validate_download", lambda *a: None)
    with pytest.raises(media.UltraError, match="Aucune vidéo"):
        media.download_explicit([url], tmp_path)
    assert len(list(tmp_path.glob("*.f137.mp4"))) == 1
