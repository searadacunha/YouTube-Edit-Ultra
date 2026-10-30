import json
import time
from urllib.error import HTTPError

import pytest

from youtube_edit_ultra import catalogue, spotify
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.produce import download_permission


def test_unknown_cc_publisher_does_not_authorize_download():
    candidate = {
        "license": "Creative Commons Attribution license (reuse allowed)",
        "channel_url": "https://example.org/channel",
    }
    assert not download_permission(candidate, {})
    assert download_permission(
        candidate, {"trusted_cc_publishers": [candidate["channel_url"]]}
    )


def test_refresh_once_on_revoked_access_token(tmp_path, monkeypatch):
    catalogue.save(
        tmp_path / "spotify.secret.json",
        {
            "refresh_token": "refresh",
            "access_token": "old",
            "client_id": "id",
            "expires_at": time.time() + 3600,
        },
    )
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        if url.endswith("api/token"):
            return {"access_token": "new", "expires_in": 3600}
        if kwargs["token"] == "old":
            raise spotify.SpotifyHTTPError(401)
        return {"ok": True}

    monkeypatch.setattr(spotify, "request", request)
    assert spotify.client(tmp_path)(spotify.API + "me/playlists") == {"ok": True}
    assert len(calls) == 3
    assert (
        catalogue.read(tmp_path / "spotify.secret.json")["refresh_token"] == "refresh"
    )


def test_rate_limit_is_bounded(monkeypatch):
    calls = []

    class Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            raise HTTPError(req.full_url, 429, "quota", {"Retry-After": "1"}, None)

    monkeypatch.setattr(spotify, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(spotify.time, "sleep", lambda t: None)
    with pytest.raises(spotify.SpotifyHTTPError) as error:
        spotify.request(spotify.API + "me/playlists", token="test")
    assert error.value.status == 429 and len(calls) == 3


def test_api_redirect_never_forwards_credentials():
    with pytest.raises(UltraError, match="Redirection"):
        spotify.NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://elsewhere.org"
        )


def test_playlist_offset_corruption_fails():
    def get(url):
        if "/items" not in url:
            return {"snapshot_id": "stable"}
        return {"total": 1, "offset": 4, "items": [{"item": None}], "next": None}

    with pytest.raises(UltraError):
        spotify.playlist("a" * 22, get)


def test_user_library_paginates_and_selects_playlist():
    def get(url):
        if "offset=1" in url:
            return {
                "total": 2,
                "offset": 1,
                "items": [
                    {"name": "RAP / R&B 90s–2000s", "uri": "spotify:playlist:chosen"}
                ],
                "next": None,
            }
        return {
            "total": 2,
            "offset": 0,
            "items": [{"name": "Rock", "uri": "other"}],
            "next": spotify.API + "me/playlists?offset=1",
        }

    assert spotify.find_playlist("rnb-2000s", get) == "spotify:playlist:chosen"


def test_candidate_list_is_not_usage(tmp_path):
    (tmp_path / "music_tracklist.json").write_text(
        json.dumps({"tracks": [], "candidates": [{"title": "Unused"}]})
    )
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert state["used"] == []


def test_rnb_release_year_is_required(tmp_path):
    path = tmp_path / "song.wav"
    path.write_bytes(b"release-year metadata fixture")
    row = {
        "path": str(path),
        "sha256": catalogue.sha256(path),
        "available": True,
        "kind": "audio",
        "title": "New Song",
        "artist": "Artist",
        "genre": "rnb-2000s",
    }
    state = catalogue.empty()
    state["media"] = {"song": row}
    state["permissions"] = {row["sha256"]: {"reuse": True, "evidence": "original"}}
    assert not catalogue.select_music(state, "rnb-2000s", None)[0]
    row["release_date"] = "2004-01-01"
    assert len(catalogue.select_music(state, "rnb-2000s", None)[0]) == 1


def test_nested_history_survives_missing_audio(tmp_path):
    (tmp_path / "full_music.json").write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "track": {
                            "title": "Old Song",
                            "artist": "Singer",
                            "file": "/missing/song.mp3",
                        }
                    }
                ]
            }
        )
    )
    state = catalogue.scan([tmp_path], catalogue.empty())
    assert state["used"][0]["family"] == "oldsong"
    catalogue.scan([tmp_path], state)
    assert len(state["used"]) == 1
    assert len(state["projects"]) == 1


def test_spotify_is_not_a_download_source(tmp_path):
    from youtube_edit_ultra.cli import main

    assert (
        main(
            [
                "catalogue",
                "--state-dir",
                str(tmp_path),
                "authorize-url",
                "https://open.spotify.com/track/example",
                "--kind",
                "audio",
                "--evidence",
                "test",
            ]
        )
        == 2
    )
