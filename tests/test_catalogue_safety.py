import json
import math
import struct
import wave

import pytest

from youtube_edit_ultra import catalogue as cat, media


def audio(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        out.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i * .2)))
                                 for i in range(4000)))
    return path


def inventoried(path):
    state = cat.scan([path.parent], cat.empty())
    row = state["media"][str(path)]
    state["permissions"][row["sha256"]] = {"reuse": True, "evidence": "Owned fixture"}
    return state, row


def test_failed_refresh_never_leaves_old_grant_usable(tmp_path):
    path = audio(tmp_path / "track.wav")
    state, row = inventoried(path)
    assert cat.permitted(state, row)
    path.write_bytes(b"interrupted replacement")
    cat.scan([tmp_path], state)
    assert state["errors"]
    assert not state["media"][str(path)]["available"]
    assert not cat.permitted(state, state["media"][str(path)])


def test_selection_checks_changed_file_outside_current_scan_roots(tmp_path):
    path = audio(tmp_path / "first" / "track.wav")
    state, row = inventoried(path)
    audio(tmp_path / "second" / "other.wav")
    path.write_bytes(b"not the authorized bytes")
    cat.scan([tmp_path / "second"], state)
    assert not cat.permitted(state, row)
    assert row["available"] is False


def test_same_content_refresh_keeps_authorized_custom_metadata(tmp_path):
    path = audio(tmp_path / "track.wav")
    state, row = inventoried(path)
    row.update(title="Verified title", artist="Artist", genre="rnb-2000s",
               release_date="2003-01-01", url="https://example.org/track",
               identity_evidence="dated album record")
    path.touch()
    cat.scan([tmp_path], state)
    refreshed = state["media"][str(path)]
    for key in ["title", "artist", "genre", "release_date", "url", "identity_evidence"]:
        assert refreshed[key] == row[key]
    assert cat.permitted(state, refreshed)


@pytest.mark.parametrize("duration,streams", [
    ("nan", [{"codec_type": "audio"}]), ("0", [{"codec_type": "audio"}]),
    ("2", []),
])
def test_scan_rejects_invalid_probe_results(tmp_path, monkeypatch, duration, streams):
    path = tmp_path / "track.wav"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(cat, "run", lambda _: json.dumps({"format": {"duration": duration},
                                                         "streams": streams}))
    state = cat.scan([tmp_path], cat.empty())
    assert state["errors"]
    assert not state["media"].get(str(path), {}).get("available")


def commercial_grant():
    return cat.permission_grant(
        "Signed fixture licence", mode="commercial", license="fixture-commercial-1",
        rights_verified_by="Fixture owner", rights_verified_at="2026-10-30T00:00:00Z",
        commercial_use=True, adaptation=True, distribution=True, monetization=True,
        credit="Fixture owner", attribution_required=True,
    )


def test_legacy_grants_are_personal_and_missing_paths_are_never_permitted(tmp_path):
    path = audio(tmp_path / "track.wav")
    state, row = inventoried(path)
    assert cat.permitted(state, row, mode="personal")
    assert not cat.permitted(state, row, mode="commercial")
    path.unlink()
    assert not cat.permitted(state, row)


def test_commercial_requires_explicit_complete_scope_and_current_bytes(tmp_path):
    path = audio(tmp_path / "track.wav")
    state, row = inventoried(path)
    grant = commercial_grant()
    state["permissions"][row["sha256"]] = grant
    assert cat.permitted(state, row, mode="personal")
    assert cat.permitted(state, row, mode="commercial")
    for key in ["evidence", "license", "rights_verified_by", "rights_verified_at", "credit",
                "commercial_use", "adaptation", "distribution", "monetization"]:
        incomplete = dict(grant)
        incomplete.pop(key)
        assert not cat.grant_allows(incomplete, "commercial"), key
    assert not cat.grant_allows(dict(grant, rights_verified_at="not a date"), "commercial")
    assert not cat.grant_allows(dict(grant, rights_verified_by=True), "commercial")
    with pytest.raises(media.UltraError):
        cat.permission_grant("Public URL", mode="commercial")
    with pytest.raises(ValueError):
        cat.grant_allows(grant, "anything")


def test_personal_reacquisition_does_not_drop_commercial_proof():
    grant = commercial_grant()
    assert cat.permission_grant("cache reuse", previous=grant) == grant


def test_complete_decode_cache_binds_to_content(tmp_path, monkeypatch):
    path = audio(tmp_path / "track.wav")
    calls = []
    original = media.run
    def run(argv, **kwargs):
        calls.append(argv)
        return original(argv, **kwargs)
    monkeypatch.setattr(media, "run", run)
    first = media.validate_media(path, "audio")
    second = media.validate_media(path, "audio")
    assert first["full_decode"] and not first["cached"]
    assert second["cached"] and first["sha256"] == second["sha256"]
    assert sum(argv[0] == "ffmpeg" for argv in calls) == 1
    path.write_bytes(b"incomplete media")
    with pytest.raises(media.UltraError):
        media.validate_media(path, "audio")


def test_downloaded_extension_without_valid_media_is_not_success(tmp_path, monkeypatch):
    original = media.run
    def run(argv, **kwargs):
        if "-o" in argv:
            pattern = argv[argv.index("-o") + 1]
            from pathlib import Path
            Path(pattern.replace("%(id)s", "test").replace("%(ext)s", "mp4")).write_bytes(b"broken")
            return ""
        return original(argv, **kwargs)
    monkeypatch.setattr(media, "run", run)
    monkeypatch.setattr(media, "downloader_command", lambda: ["yt-dlp"])
    with pytest.raises(media.UltraError):
        media.download_explicit(["https://example.org/video"], tmp_path)


def test_empty_decode_cannot_create_validation_cache(tmp_path, monkeypatch):
    path = audio(tmp_path / "empty_decode.wav")
    original = media.run
    monkeypatch.setattr(media, "run", lambda argv, **kw:
                        "frame=0\nout_time_us=0\nprogress=end\n" if argv[0] == "ffmpeg"
                        else original(argv, **kw))
    with pytest.raises(media.UltraError, match="no usable media"):
        media.validate_media(path)
    assert not (tmp_path / ".ultra-validation").exists()


def test_metadata_duration_mismatch_is_not_a_completed_acquisition(tmp_path):
    path = audio(tmp_path / "short.wav")
    path.with_suffix(".info.json").write_text(json.dumps({"duration": 100}))
    with pytest.raises(media.UltraError, match="duration does not match"):
        media._validate_download(path, "audio")


def test_direct_acquisition_reuses_real_decoded_bytes(tmp_path, monkeypatch):
    original = audio(tmp_path / "owned" / "original.wav")
    destination = tmp_path / "download"
    calls = []
    real_run = media.run
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "curl":
            from pathlib import Path
            Path(argv[argv.index("--output") + 1]).write_bytes(original.read_bytes())
            return ""
        return real_run(argv, **kwargs)
    monkeypatch.setattr(media, "run", run)
    url = "https://example.org/owned-fixture.wav"
    first = media.download_audio_explicit([url], destination)[0]
    second = media.download_audio_explicit([url], destination)[0]
    assert first == second and cat.sha256(first) == cat.sha256(original)
    assert sum(command[0] == "curl" for command in calls) == 1
    assert sum(command[0] == "ffmpeg" for command in calls) == 1
    assert json.loads(first.with_suffix(".info.json").read_text())["webpage_url"] == url
    assert next((destination / ".ultra-validation").glob("*.json")).is_file()


def test_capped_audio_cannot_become_success_on_cache_retry(tmp_path):
    path = audio(tmp_path / "capped.wav")
    with pytest.raises(media.UltraError, match="storage cap"):
        media._validate_download(path, "audio", 5000)
    with pytest.raises(media.UltraError, match="storage cap"):
        media._validate_download(path, "audio")


def test_style_uses_documented_country_and_keeps_historical_year_gate(tmp_path):
    path = audio(tmp_path / 'Artist - Song.wav')
    state, row = inventoried(path)
    row.update(genre='hip-hop', language='ja')
    assert cat.select_music(state, 'japanese-hip-hop', None)[0]
    row['language'] = 'en'
    assert not cat.select_music(state, 'japanese-hip-hop', None)[0]
    row.update(genre='R&B', release_date='2003-01-01')
    assert cat.select_music(state, 'rnb-2000s', None)[0]
    row['release_date'] = '2026-01-01'
    assert not cat.select_music(state, 'rnb-2000s', None)[0]


@pytest.mark.parametrize("kind", ["video", "audio"])
@pytest.mark.parametrize("reuse,expected", [(False, 0), (True, 1), (None, 1)])
def test_url_reuse_denial_is_respected_and_legacy_grants_still_work(
        tmp_path, monkeypatch, kind, reuse, expected):
    from youtube_edit_ultra import produce, music_sources
    from youtube_edit_ultra.cli import main
    root = tmp_path / "inputs"
    root.mkdir()
    entry = dict(url="https://example.org/owned-source", kind=kind,
                 athlete="Canelo Alvarez", style="reggaeton", evidence="Fixture permission")
    if reuse is not None:
        entry["reuse"] = reuse
    state = cat.empty()
    state["authorized_urls"] = [entry]
    cat.save(tmp_path / "state/catalogue.json", state)
    calls = []
    def download(*args):
        calls.append(args)
        raise media.UltraError("simulated acquisition boundary")
    monkeypatch.setattr(produce, "download_explicit", download)
    monkeypatch.setattr(produce, "download_audio_explicit", download)
    monkeypatch.setattr(produce, "discover", lambda *args: [])
    monkeypatch.setattr(music_sources, "acquire", lambda *args, **kwargs:
                        dict(candidates=[], attempts=[], errors=[]))
    assert main(["produce", "Canelo Alvarez 6s reggaeton", "--root", str(root),
                 "--state-dir", str(tmp_path / "state"), "--output-dir", str(tmp_path / "out")]) == 2
    assert len(calls) == expected
