import json
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
