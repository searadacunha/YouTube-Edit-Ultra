"""Explicit OAuth YouTube upload; no unapproved automatic publication."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .media import UltraError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def client():
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise UltraError("Option YouTube manquante : pip install '.[youtube]'") from exc
    auth_dir = Path.home() / ".config" / "youtube-edit-ultra"
    auth_dir.mkdir(parents=True, exist_ok=True)
    token = auth_dir / "token.json"
    secrets = Path(os.environ.get("YEU_CLIENT_SECRETS", str(auth_dir / "client_secret.json")))
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets.exists():
                raise UltraError(f"OAuth absent : placer le fichier client_secret.json ici : {secrets}")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes=SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")
        try:
            os.chmod(token, 0o600)
        except OSError:
            pass
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, *, title: str, description: str, tags: list[str],
           privacy: str, thumbnail: Path | None = None, state_path: Path | None = None) -> dict:
    if privacy not in {"private", "unlisted", "public"}:
        raise UltraError("Publication explicite requise : private, unlisted ou public")
    if not video.is_file():
        raise UltraError(f"Vidéo manquante: {video}")
    state_path = state_path or video.with_suffix(".youtube.json")
    if state_path.is_file():
        state = json.loads(state_path.read_text())
        if state.get("video_id"):
            # Do not post duplicates after a successful upload.
            return state
    from googleapiclient.http import MediaFileUpload
    youtube = client()
    request = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title[:100], "description": description[:5000],
                          "tags": tags[:35], "categoryId": "17"},
              "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}},
        media_body=MediaFileUpload(str(video), mimetype="video/mp4",
                                   chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    retries = 0
    while response is None:
        try:
            _, response = request.next_chunk()
            retries = 0
        except Exception as exc:
            retries += 1
            if retries > 5:
                raise UltraError(f"YouTube upload échoué : {exc}") from exc
            time.sleep(min(2 ** retries, 32))
    vid = response.get("id")
    if not vid:
        raise UltraError("YouTube n'a pas renvoyé d'identifiant de vidéo")
    state = {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
             "requested_privacy": privacy, "note": "Le projet API Google peut imposer private avant audit."}
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    if thumbnail and thumbnail.exists():
        try:
            from googleapiclient.http import MediaFileUpload
            youtube.thumbnails().set(videoId=vid,
                                     media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")).execute()
            state["thumbnail_uploaded"] = True
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        except Exception as exc:
            state["thumbnail_error"] = str(exc)
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return state
