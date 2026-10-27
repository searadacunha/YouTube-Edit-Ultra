"""Local library, explicit URL ingestion and validated FFmpeg operations."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg"}


class UltraError(RuntimeError):
    """Actionable editing error."""


def run(command: list[str], *, quiet: bool = True) -> str:
    cp = subprocess.run(command, capture_output=True, text=True, check=False)
    if cp.returncode:
        raise UltraError(f"Commande en échec ({cp.returncode}): {' '.join(command[:7])}\n{cp.stderr[-2500:]}")
    if not quiet and cp.stderr:
        print(cp.stderr[-1000:])
    return cp.stdout


def check_binaries() -> None:
    missing = [x for x in ("ffmpeg", "ffprobe") if not shutil.which(x)]
    if missing:
        raise UltraError("Installer FFmpeg : brew install ffmpeg (binaire(s) absent(s): " + ", ".join(missing) + ")")


def probe(path: Path) -> dict:
    obj = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = obj.get("streams", [])
    duration = float(obj.get("format", {}).get("duration", 0.0) or 0.0)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    return {"duration": duration, "has_video": video is not None,
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "width": (video or {}).get("width"), "height": (video or {}).get("height")}


def fingerprint(path: Path) -> str:
    st = path.stat()
    return hashlib.sha256(f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:24]


def slug(text: str) -> str:
    from .spec import normalize
    out = re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")
    return out[:70] or "mix"


def video_library(root: Path, athlete: str, *, all_library: bool = False) -> list[Path]:
    folder = root / "videos"
    files = sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT), key=lambda p: p.name.lower()) if folder.exists() else []
    if all_library:
        return files
    # Only return local files tagged/named after requested athlete; do not silently mix other athletes.
    words = [w for w in slug(athlete).split("-") if len(w) >= 3]
    matching = [p for p in files if (all(w in slug(p.stem + " " + str(p.parent)) for w in words)
                                     or (len(words) > 1 and words[-1] in slug(p.stem)))]
    return matching


def audio_library(root: Path, style: str) -> list[Path]:
    root = root / "music"
    if not root.exists():
        return []
    candidates = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT]
    # Style-specific folder takes priority; filenames need not carry a genre.
    style_matches = [p for p in candidates if slug(style) in slug(p.parent.name) or slug(style) in slug(p.stem)]
    return sorted(style_matches or (candidates if style == "default" else []))


def load_url_list(path: Path) -> list[str]:
    return [x.strip() for x in path.read_text().splitlines() if x.strip() and not x.startswith("#")]


def download_explicit(urls: list[str], folder: Path) -> list[Path]:
    """Download ONLY explicitly supplied sources; caller attests it has rights/permission."""
    if not urls:
        return []
    if not shutil.which("yt-dlp"):
        raise UltraError("Installer l'option download : pip install '.[download]' ou brew install yt-dlp")
    folder.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for url in urls:
        parts = urlparse(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise UltraError(f"URL non HTTP(S) : {url!r}")
        if parts.username or parts.password:
            raise UltraError("URL avec identifiants refusée")
        # Cache by URL, not its position in this run. Reordering URLs must
        # never make an idempotent rerun import another source's old files.
        prefix = "source-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        pattern = str(folder / f"{prefix}-%(id)s.%(ext)s")
        run(["yt-dlp", "--no-playlist", "--no-overwrites", "--restrict-filenames", "-f", "bv*+ba/b",
             "--merge-output-format", "mp4", "-o", pattern, "--", url])
        new = sorted(p for p in folder.glob(f"{prefix}-*")
                     if p.is_file() and p.suffix.lower() in VIDEO_EXT)
        if not new:
            raise UltraError(f"Aucune vidéo sauvegardée depuis: {url}")
        result.extend(new)
    return list(dict.fromkeys(result))


def ffmpeg_encode_args(*, quality: int = 21) -> list[str]:
    # Hardware support varies between Macs. libx264 is the reliable fallback.
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(quality), "-pix_fmt", "yuv420p"]


def download_audio_explicit(urls: list[str], folder: Path) -> list[Path]:
    """Extract audio ONLY from user-specified, authorized URLs (not a genre crawler)."""
    if not urls:
        return []
    if not shutil.which("yt-dlp"):
        raise UltraError("Installer le téléchargeur audio : pip install '.[download]'")
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for url in urls:
        parts = urlparse(url)
        if parts.scheme not in {"https", "http"} or not parts.hostname:
            raise UltraError(f"URL audio invalide : {url!r}")
        if parts.username or parts.password:
            raise UltraError("URL audio avec identifiants refusée")
        prefix = "music-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        run(["yt-dlp", "--no-playlist", "--no-overwrites", "--restrict-filenames",
             "-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0",
             "-o", str(folder / f"{prefix}-%(id)s.%(ext)s"), "--", url])
        new = sorted(p for p in folder.glob(f"{prefix}-*.mp3") if p.is_file())
        if not new:
            raise UltraError(f"Aucun fichier audio extrait depuis: {url}")
        result.extend(new)
    return list(dict.fromkeys(result))
