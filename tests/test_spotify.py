import pytest
from youtube_edit_ultra import spotify
from youtube_edit_ultra.media import UltraError


def test_complete_pagination_and_nulls():
    calls = []

    def get(url):
        calls.append(url)
        if "/items" not in url:
            return {"snapshot_id": "stable", "name": "test"}
        if "offset=1" in url:
            return {
                "total": 2,
                "items": [
                    {
                        "item": {
                            "type": "track",
                            "uri": "spotify:track:x",
                            "name": "X",
                            "artists": [],
                        }
                    }
                ],
                "next": None,
            }
        return {
            "total": 2,
            "items": [{"item": None}],
            "next": "https://api.spotify.com/v1/playlists/"
            + "a" * 22
            + "/items?offset=1",
        }

    result = spotify.playlist("a" * 22, get)
    assert result["complete"] and result["total_items"] == 2
    assert len(result["unavailable"]) == 1 and len(result["tracks"]) == 1
    assert len(calls) == 4


def test_rejects_hostile_page():
    def get(url):
        if "/items" not in url:
            return {"snapshot_id": "x"}
        return {
            "total": 2,
            "items": [{"item": None}],
            "next": "https://example.com/steal",
        }

    with pytest.raises(UltraError, match="pagination"):
        spotify.playlist("a" * 22, get)


def test_incomplete_page_fails():
    def get(url):
        if "/items" not in url:
            return {"snapshot_id": "x"}
        return {"total": 671, "items": [], "next": None}

    with pytest.raises(UltraError, match="incomplète"):
        spotify.playlist("a" * 22, get)


def test_pkce_state_and_private_storage(tmp_path):
    from urllib.parse import parse_qs, urlparse

    url = spotify.login_start(tmp_path, "client")
    params = parse_qs(urlparse(url).query)
    assert params["code_challenge_method"] == ["S256"]
    path = tmp_path / "spotify-pending.secret.json"
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(UltraError, match="state"):
        spotify.login_finish(tmp_path, spotify.REDIRECT + "?code=no&state=wrong")


def test_refresh_preserves_refresh_token(tmp_path, monkeypatch):
    from youtube_edit_ultra.catalogue import save, read

    save(
        tmp_path / "spotify.secret.json",
        dict(refresh_token="refresh", client_id="client", expires_at=0),
    )
    monkeypatch.setattr(
        spotify,
        "request",
        lambda url, **kwargs: dict(access_token="access", expires_in=3600),
    )
    spotify.client(tmp_path)
    assert read(tmp_path / "spotify.secret.json")["refresh_token"] == "refresh"


def test_playlist_change_detected():
    count = 0

    def get(url):
        nonlocal count
        if "/items" in url:
            return {"total": 0, "items": [], "next": None}
        count += 1
        return {"snapshot_id": str(count)}

    with pytest.raises(UltraError, match="modifiée"):
        spotify.playlist("a" * 22, get)


def test_671_tracks_all_pages():
    from urllib.parse import urlparse, parse_qs

    def get(url):
        if "/items" not in url:
            return {"snapshot_id": "stable"}
        start = int(parse_qs(urlparse(url).query).get("offset", ["0"])[0])
        end = min(start + 50, 671)
        return {
            "total": 671,
            "items": [
                {
                    "item": {
                        "type": "track",
                        "uri": f"spotify:track:{i}",
                        "name": str(i),
                        "artists": [],
                    }
                }
                for i in range(start, end)
            ],
            "next": (
                "https://api.spotify.com/v1/playlists/"
                + "a" * 22
                + f"/items?offset={end}"
            )
            if end < 671
            else None,
        }

    data = spotify.playlist("a" * 22, get)
    assert len(data["tracks"]) == 671
    assert len({t["uri"] for t in data["tracks"]}) == 671
    assert data["tracks"][-1]["playlist_position"] == 670
