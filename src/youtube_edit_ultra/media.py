"""Local library, explicit URL ingestion and validated FFmpeg operations."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg"}


class UltraError(RuntimeError):
    """Actionable editing error."""


DISK_GUARD_CONFIG = Path.home() / "Documents/Systeme/disk-guard/config.json"


def floor_bytes() -> int:
    """Free space every render or download must leave: the Mac-wide floor that keeps PolySentinel collecting."""
    if os.environ.get("DISKGUARD_FLOOR_BYTES"):
        return int(os.environ["DISKGUARD_FLOOR_BYTES"])
    try:
        return int(json.loads(DISK_GUARD_CONFIG.read_text())["floor_bytes"])
    except (OSError, ValueError, KeyError):
        return 12_000_000_000


def require_space(path: Path, need: int, what: str, floor: int | None = None) -> int:
    """Refuse before writing if free space minus the estimate would fall under the floor; return what may still be written."""
    floor = floor_bytes() if floor is None else floor
    free = shutil.disk_usage(path).free
    if free - need < floor:
        raise UltraError(f"Insufficient space for {what}: {free / 1e9:.2f} GB free, estimated {need / 1e9:.2f} GB, "
                         f"floor {floor / 1e9:.2f} GB (PolySentinel needs 10.5 GB). Nothing was written.")
    return free - floor


def downloader_command() -> list[str]:
    # Use this installation's dependency, not a stale global executable.
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    raise UltraError("Installer le téléchargeur : pip install '.[download]'")


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
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    return {"duration": duration, "has_video": video is not None,
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "width": (video or {}).get("width"), "height": (video or {}).get("height")}


def validate_media(path: Path, kind: str | None = None, *, cache_dir: Path | None = None) -> dict:
    """Decode each acquired content hash once; extensions and FFprobe alone are insufficient."""
    if kind not in {None, "audio", "video"}:
        raise ValueError(f"Unknown media kind: {kind}")
    path = Path(path).resolve(strict=True)
    before = path.stat()
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    cache = Path(cache_dir) if cache_dir is not None else path.parent / ".ultra-validation"
    report_path = cache / f"{digest}.json"
    try:
        saved = json.loads(report_path.read_text())
        if (isinstance(saved, dict) and saved.get("version") == 2
                and saved.get("sha256") == digest and saved.get("full_decode") is True
                and saved.get("duration", 0) > 0
                and (kind is None or saved.get("has_" + kind))):
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise UltraError(f"Source changed during validation: {path}")
            return dict(saved, path=str(path), cached=True, validation_report=str(report_path))
    except (OSError, ValueError, TypeError):
        pass
    info = probe(path)
    if (not math.isfinite(info["duration"]) or info["duration"] <= 0
            or not (info["has_audio"] or info["has_video"])
            or (kind is not None and not info["has_" + kind])):
        raise UltraError(f"Invalid {kind or 'media'} source: {path}")
    progress = run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
                    "-map", "0:v?", "-map", "0:a?", "-progress", "pipe:1",
                    "-nostats", "-f", "null", "-"])
    times = [int(value) for value in re.findall(r"^out_time_us=(\d+)$", progress, re.M)]
    frames = [int(value) for value in re.findall(r"^frame=(\d+)$", progress, re.M)]
    if not times or max(times) <= 0 or (info["has_video"] and (not frames or max(frames) <= 0)):
        raise UltraError(f"Source decoded no usable media: {path}")
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise UltraError(f"Source changed during validation: {path}")
    report = dict(info, version=2, path=str(path), sha256=digest, full_decode=True,
                  decoded_duration_seconds=max(times) / 1e6, cached=False)
    cache.mkdir(parents=True, exist_ok=True)
    temporary = cache / (".validation-" + uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(report, indent=2))
        temporary.replace(report_path)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(report, validation_report=str(report_path))


def _download_budget(folder, kind):
    available = require_space(folder, 0, f"{kind} download")
    budget = min(2_000_000_000 if kind == "video" else 500_000_000, int(available * .9))
    if budget <= 0:
        raise UltraError("No storage budget remains above the disk floor")
    return budget


def _guarded_download(command, folder, need, label):
    from .storage import guarded_command
    return run(guarded_command(command, need=need, path=folder, label=label))


def _validate_download(path, kind, max_output_bytes=None):
    report = validate_media(path, kind)
    limits = path.with_suffix(path.suffix + ".acquisition.json")
    if max_output_bytes is not None:
        if type(max_output_bytes) is not int or max_output_bytes <= 0:
            raise ValueError("Acquisition size cap must be a positive integer")
        limits.write_text(json.dumps({"max_output_bytes": max_output_bytes}))
    elif limits.exists():
        try:
            max_output_bytes = json.loads(limits.read_text())["max_output_bytes"]
            if type(max_output_bytes) is not int or max_output_bytes <= 0:
                raise ValueError("Invalid acquisition size cap")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise UltraError(f"Invalid acquisition limits: {limits}") from exc
    sidecar = path.with_suffix(".info.json")
    if sidecar.exists():
        try:
            metadata = json.loads(sidecar.read_text())
            expected = float(metadata.get("duration") or 0)
            if not math.isfinite(expected) or expected < 0:
                raise ValueError("Source duration is not finite and nonnegative")
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise UltraError(f"Invalid acquisition metadata: {sidecar}") from exc
        if (expected > 0 and abs(report["duration"] - expected) > max(.5, expected * .005)):
            raise UltraError(f"Acquired duration does not match source metadata: {path}")
    if max_output_bytes and path.stat().st_size >= max_output_bytes:
        raise UltraError(f"Audio extraction reached its storage cap: {path}")
    return report


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


def download_direct(url: str, folder: Path, kind: str) -> Path | None:
    """Fetch an explicitly permitted original media link, with no extractor or login."""
    parts = urlparse(url)
    suffix = Path(parts.path).suffix.lower()
    if parts.scheme != "https" or suffix not in (VIDEO_EXT if kind == "video" else AUDIO_EXT):
        return None
    if not parts.hostname or parts.username or parts.password:
        raise UltraError("URL directe invalide")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (kind + "-" + hashlib.sha256(url.encode()).hexdigest()[:20] + suffix)
    candidate = target
    if not target.exists():
        if not shutil.which("curl"):
            raise UltraError("curl absent pour le lien de média original")
        candidate = target.with_name(target.name + "." + uuid.uuid4().hex + ".partial")
        budget = _download_budget(folder, kind)
        _guarded_download(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
             "--proto", "=https", "--proto-redir", "=https", "--max-time", "600",
             "--max-filesize", str(budget), "--output", str(candidate), "--", url],
             folder, budget, f"authorized direct {kind}")
    validate_media(candidate, kind)
    if candidate != target:
        candidate.rename(target)
    sidecar = target.with_suffix(".info.json")
    if not sidecar.exists():
        sidecar.write_text(json.dumps({"webpage_url": url, "acquisition": "authorized_direct_url",
                                      "license": None}, indent=2))
    return target


def _finished_video_files(folder: Path, prefix: str) -> list[Path]:
    # yt-dlp retains .f<format> streams and .temp/.orig files before a completed merge.
    return sorted(p for p in folder.glob(f"{prefix}-*")
                  if p.is_file() and p.suffix.lower() in VIDEO_EXT
                  and not re.search(r"\.(?:f[^.]+|temp|orig)$", p.stem))


def download_explicit(urls: list[str], folder: Path) -> list[Path]:
    """Download ONLY explicitly supplied sources; caller attests it has rights/permission."""
    if not urls:
        return []
    folder.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for url in urls:
        direct = download_direct(url, folder, "video")
        if direct:
            result.append(direct)
            continue
        parts = urlparse(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise UltraError(f"URL non HTTP(S) : {url!r}")
        if parts.username or parts.password:
            raise UltraError("URL avec identifiants refusée")
        # Cache by URL, not its position in this run. Reordering URLs must
        # never make an idempotent rerun import another source's old files.
        prefix = "source-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        pattern = str(folder / f"{prefix}-%(id)s.%(ext)s")
        cached = _finished_video_files(folder, prefix)
        if cached:
            for path in cached:
                _validate_download(path, "video")
            result.extend(cached)
            continue
        # Two source streams plus their merged output can coexist: reserve all four parts.
        budget = _download_budget(folder, "video")
        _guarded_download([*downloader_command(), "--ignore-config", "--socket-timeout", "30", "--retries", "2", "--fragment-retries", "2", "--no-playlist", "--no-overwrites", "--restrict-filenames", "--write-info-json",
             "--max-filesize", str(budget // 4), "-f", "bv*+ba/b",
             "--merge-output-format", "mp4", "-o", pattern, "--", url],
             folder, budget, "authorized video acquisition")
        new = _finished_video_files(folder, prefix)
        if not new:
            raise UltraError(f"Aucune vidéo sauvegardée depuis: {url}")
        for path in new:
            _validate_download(path, "video")
        result.extend(new)
    return list(dict.fromkeys(result))


def ffmpeg_encode_args(*, quality: int = 21) -> list[str]:
    # Hardware support varies between Macs. libx264 is the reliable fallback.
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(quality), "-pix_fmt", "yuv420p"]


def download_audio_explicit(urls: list[str], folder: Path) -> list[Path]:
    """Extract audio ONLY from user-specified, authorized URLs (not a genre crawler)."""
    if not urls:
        return []
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for url in urls:
        direct = download_direct(url, folder, "audio")
        if direct:
            result.append(direct)
            continue
        parts = urlparse(url)
        if parts.scheme not in {"https", "http"} or not parts.hostname:
            raise UltraError(f"URL audio invalide : {url!r}")
        if parts.username or parts.password:
            raise UltraError("URL audio avec identifiants refusée")
        prefix = "music-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        cached = sorted(p for p in folder.glob(f"{prefix}-*.mp3") if p.is_file())
        if cached:
            for path in cached:
                _validate_download(path, "audio")
            result.extend(cached)
            continue
        budget = _download_budget(folder, "audio")  # source and MP3 coexist during extraction
        cap = budget // 2
        _guarded_download([*downloader_command(), "--ignore-config", "--socket-timeout", "30", "--retries", "2", "--fragment-retries", "2", "--no-playlist", "--no-overwrites", "--restrict-filenames", "--write-info-json",
             "--max-filesize", str(cap), "-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0",
             "--postprocessor-args", f"ExtractAudio+ffmpeg_o:-fs {cap}",
             "-o", str(folder / f"{prefix}-%(id)s.%(ext)s"), "--", url],
             folder, budget, "authorized audio acquisition")
        new = sorted(p for p in folder.glob(f"{prefix}-*.mp3") if p.is_file())
        if not new:
            raise UltraError(f"Aucun fichier audio extrait depuis: {url}")
        for path in new:
            _validate_download(path, "audio", cap)
        result.extend(new)
    return list(dict.fromkeys(result))
