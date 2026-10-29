"""Spotify metadata only: PKCE, refresh, pagination with completeness checks."""

import base64
import hashlib
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from .catalogue import read, save
from .media import UltraError

API = "https://api.spotify.com/v1/"
REDIRECT = "http://127.0.0.1:8769/callback"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UltraError("Redirection Spotify refusée : protection des identifiants")


class SpotifyHTTPError(UltraError):
    def __init__(self, status):
        self.status = status
        super().__init__(
            f"Spotify HTTP {status}: vérifier authentification, accès playlist ou quota"
        )


def request(url, *, form=None, token=None):
    if not (url.startswith(API) or url == "https://accounts.spotify.com/api/token"):
        raise UltraError("Destination Spotify invalide")
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if form else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    for attempt in range(3):
        try:
            req = Request(
                url, data=urlencode(form).encode() if form else None, headers=headers
            )
            with build_opener(NoRedirect()).open(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as e:
            if e.code == 429 and attempt < 2:
                delay = int(e.headers.get("Retry-After", "1"))
                if delay <= 30:
                    time.sleep(max(1, delay))
                    continue
            raise SpotifyHTTPError(e.code) from None
        except URLError:
            raise UltraError("Spotify inaccessible (réseau)") from None


def login_start(folder, client_id):
    if not client_id:
        raise UltraError("Spotify: --client-id requis (application Spotify Developer)")
    verifier = secrets.token_urlsafe(64)
    pending = dict(
        client_id=client_id,
        verifier=verifier,
        state=secrets.token_urlsafe(32),
        created=time.time(),
    )
    save(folder / "spotify-pending.secret.json", pending)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return "https://accounts.spotify.com/authorize?" + urlencode(
        dict(
            client_id=client_id,
            response_type="code",
            redirect_uri=REDIRECT,
            scope="playlist-read-private playlist-read-collaborative",
            state=pending["state"],
            code_challenge_method="S256",
            code_challenge=challenge,
        )
    )


def login_finish(folder, callback):
    pending = read(folder / "spotify-pending.secret.json", {})
    u = urlparse(callback)
    q = parse_qs(u.query)
    if (
        u.scheme + "://" + u.netloc + u.path != REDIRECT
        or not pending
        or time.time() - pending["created"] > 600
        or not secrets.compare_digest(q.get("state", [""])[0], pending["state"])
        or not q.get("code")
    ):
        raise UltraError("Callback Spotify invalide, expiré ou state incorrect")
    token = request(
        "https://accounts.spotify.com/api/token",
        form=dict(
            grant_type="authorization_code",
            code=q["code"][0],
            redirect_uri=REDIRECT,
            client_id=pending["client_id"],
            code_verifier=pending["verifier"],
        ),
    )
    token.update(
        client_id=pending["client_id"], expires_at=time.time() + token["expires_in"]
    )
    save(folder / "spotify.secret.json", token)
    save(folder / "spotify-pending.secret.json", {})


def client(folder):
    path = folder / "spotify.secret.json"
    token = read(path, {})
    if not token.get("refresh_token"):
        raise UltraError(
            "Spotify non connecté : ultra spotify login --client-id ID puis ultra spotify finish URL_CALLBACK"
        )

    def refresh():
        new = request(
            "https://accounts.spotify.com/api/token",
            form=dict(
                grant_type="refresh_token",
                refresh_token=token["refresh_token"],
                client_id=token["client_id"],
            ),
        )
        token.update(new)
        token["expires_at"] = time.time() + new["expires_in"]
        save(path, token)

    if time.time() >= token.get("expires_at", 0) - 60:
        refresh()

    def get(url):
        if not url.startswith(API):
            raise UltraError("URL Spotify API invalide")
        try:
            return request(url, token=token["access_token"])
        except SpotifyHTTPError as e:
            if e.status != 401:
                raise
            refresh()
            return request(url, token=token["access_token"])

    return get


def playlist(value, get):
    if value.startswith("spotify:playlist:"):
        pid = value.rsplit(":", 1)[-1]
    elif value.startswith("https://open.spotify.com/"):
        pid = urlparse(value).path.rstrip("/").split("/")[-1]
    else:
        pid = value
    if not re.fullmatch("[a-zA-Z0-9]{22}", pid):
        raise UltraError("Identifiant playlist Spotify invalide")
    base = API + "playlists/" + pid
    before = get(base)
    if not before.get("snapshot_id"):
        raise UltraError("Snapshot Spotify absent")
    url = base + "/items?limit=50"
    rows = []
    unavailable = []
    seen = set()
    total = None
    count = 0
    while url:
        if not url.startswith(base + "/items?") or url in seen:
            raise UltraError("pagination Spotify invalide ou cyclique")
        seen.add(url)
        page = get(url)
        if total is None:
            total = page["total"]
        if (
            total != page["total"]
            or not isinstance(page["items"], list)
            or page.get("offset", count) != count
        ):
            raise UltraError("Playlist modifiée pendant la pagination")
        for item in page["items"]:
            track = item.get("item", item.get("track"))
            if (
                not track
                or track.get("type") != "track"
                or item.get("is_local")
                or track.get("is_local")
                or track.get("is_playable") is False
            ):
                unavailable.append(
                    {"position": count, "reason": "null_local_or_non_track"}
                )
            else:
                rows.append(
                    dict(track, playlist_position=count, added_at=item.get("added_at"))
                )
            count += 1
        url = page.get("next")
        if count > total or len(seen) > 1000:
            raise UltraError("pagination Spotify incohérente")
    if count != total:
        raise UltraError(f"Playlist incomplète : {count}/{total}")
    if get(base).get("snapshot_id") != before["snapshot_id"]:
        raise UltraError("Playlist modifiée pendant la lecture ; réessayer")
    return dict(
        uri="spotify:playlist:" + pid,
        url="https://open.spotify.com/playlist/" + pid,
        name=before.get("name"),
        snapshot_id=before["snapshot_id"],
        fetched_at=time.time(),
        complete=True,
        total_items=total,
        tracks=rows,
        unavailable=unavailable,
    )


def user_playlists(get):
    url = API + "me/playlists?limit=50"
    rows = []
    seen = set()
    total = None
    while url:
        if not url.startswith(API + "me/playlists?") or url in seen:
            raise UltraError("Pagination de bibliothèque Spotify invalide")
        seen.add(url)
        page = get(url)
        if total is None:
            total = page["total"]
        if total != page["total"] or page.get("offset", len(rows)) != len(rows):
            raise UltraError("Bibliothèque Spotify modifiée pendant la lecture")
        rows.extend(page["items"])
        if len(rows) > total or len(seen) > 1000:
            raise UltraError("Pagination Spotify incohérente")
        url = page.get("next")
    if len(rows) != total:
        raise UltraError("Bibliothèque Spotify incomplète")
    return rows


def find_playlist(style, get):
    from .spec import normalize

    words = {
        "rnb-2000s": ["r&b", "2000"],
        "rnb": ["r&b"],
        "hip-hop": ["hip", "hop"],
    }.get(style, [style])
    matches = [
        p for p in user_playlists(get) if all(w in normalize(p["name"]) for w in words)
    ]
    if len(matches) != 1:
        raise UltraError(
            f"Spotify : {len(matches)} playlists compatibles ; utiliser spotify sync URI --style {style}"
        )
    return matches[0]["uri"]
