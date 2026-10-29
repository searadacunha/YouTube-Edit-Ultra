"""Persistent local inventory. Presence and public provenance never imply permission."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .media import AUDIO_EXT, VIDEO_EXT, UltraError, run
from .spec import normalize

SKIP = {".git", ".venv", "node_modules", ".Trash", "RuView", "__pycache__", "repos"}
HISTORY = {
    "full_music.json",
    "music_timeline.json",
    "soundtrack_v5.json",
    "hiphop90s_mix.json",
    "mix.json",
    "source_report.json",
    "music_tracklist.json",
}


def empty():
    return dict(
        version=2,
        media={},
        permissions={},
        used=[],
        projects=[],
        errors=[],
        history_files={},
        authorized_urls=[],
        discovered_sources={},
        track_identities={},
        unconfirmed_history=[],
    )


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".ultra-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def family(title):
    title = re.sub(r"\([^)]*\)|\[[^]]*\]", "", title)
    title = re.split(
        r"\s+(?:-\s*)?(?:remix|radio edit|remaster|live|sped|slowed|feat\.?|ft\.?)\b",
        title,
        flags=re.I,
    )[0]
    return re.sub(r"[^a-z0-9]", "", normalize(title))


def identity(row):
    row = row.get("track", row)
    name = (
        row.get("filename")
        or row.get("source_path")
        or row.get("file")
        or row.get("source")
        or row.get("path")
        or ""
    )
    name = re.sub(r"^\d+\s*-\s*", "", Path(name).stem)
    parts = name.split(" - ", 1)
    return row.get("title") or parts[-1], row.get("artist") or (
        parts[0] if len(parts) == 2 else ""
    )


def scan(roots, state):
    state["errors"] = []
    for key in ("discovered_sources", "track_identities"):
        state.setdefault(key, {})
    state.setdefault("unconfirmed_history", [])
    if state.get("version", 1) < 2:
        state["history_files"] = {}
        state["version"] = 2
    # Analysis establishes identity, never whether the track reached an export.
    for row in list(state["used"]):
        if Path(row.get("evidence", "")).name == "audio_analysis.json":
            state["unconfirmed_history"].append(row)
            state["used"].remove(row)
    for entry in state["media"].values():
        entry["available"] = Path(entry["path"]).is_file()
    seen = set()
    for root in roots:
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            state["errors"].append({"path": str(root), "error": "Root missing"})
            continue
        for folder, dirs, files in os.walk(
            root,
            onerror=lambda e: state["errors"].append(
                {"path": str(e.filename), "error": str(e)}
            ),
        ):
            if (Path(folder) / ".ultra-ignore").exists():
                dirs[:] = []
                continue
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in SKIP
                and not d.startswith("RuView")
                and not (Path(folder) / d).is_symlink()
            )
            for name in sorted(files):
                path = Path(folder) / name
                if path.is_symlink() or str(path) in seen:
                    continue
                seen.add(str(path))
                try:
                    if name == "audio_analysis.json":
                        data = read(path)
                        entries = data.get("tracks", []) if isinstance(data, dict) else data
                        if not isinstance(entries, list):
                            raise ValueError("Audio analysis must contain a track list")
                        for entry in entries:
                            if not isinstance(entry, dict):
                                raise ValueError("Audio analysis track must be an object")
                            track = entry.get("track", entry)
                            source = track.get("file") or track.get("path")
                            if source and track.get("title"):
                                state["track_identities"][source] = dict(
                                    title=track["title"], artist=track.get("artist", ""),
                                    identity_evidence=str(path))
                        continue
                    if path.suffix == ".json" and (
                        name in {"sources.json", "proxies.json"}
                        or path.parent.name == "search"
                        or (name.startswith("search_") and path.parent.name == "sources")
                    ):
                        import_sources(path, state)
                        continue
                    if name in HISTORY:
                        # Import only tracks actually in a timeline/mix, not candidate lists.
                        digest = sha256(path)
                        if state["history_files"].get(str(path)) == digest:
                            if any(
                                r.get("evidence") == str(path) for r in state["used"]
                            ) and not any(
                                p.get("history_file") == str(path)
                                for p in state["projects"]
                            ):
                                state["projects"].append(
                                    {
                                        "history_file": str(path),
                                        "status": "HISTORICAL_MANIFEST_OBSERVED_EXPORT_NOT_REVERIFIED",
                                    }
                                )
                            continue
                        data = read(path)
                        tracks = (
                            data.get("tracks", [])
                            if isinstance(data, dict)
                            else data
                            if isinstance(data, list)
                            else []
                        )
                        if name == "source_report.json":
                            tracks = (
                                [
                                    {"path": p}
                                    for p in data.get("music", [])
                                    if isinstance(p, str)
                                ]
                                if isinstance(data, dict)
                                else []
                            )
                        if not isinstance(tracks, list):
                            raise ValueError("History tracks must be a list")
                        for i, track in enumerate(tracks):
                            if not isinstance(track, dict):
                                raise ValueError("History track must be an object")
                            title, artist = identity(track)
                            if title:
                                item = dict(
                                    title=title,
                                    artist=artist,
                                    family=family(title),
                                    sha256=track.get("sha256"),
                                    evidence=str(path),
                                    pointer=f"/tracks/{i}",
                                    source=track.get("source") or track.get("file") or track.get("path"),
                                    usage_status="timeline_record_export_not_reverified",
                                )
                                old = next((r for r in state["used"] if
                                    r.get("evidence") == str(path) and r.get("pointer") == item["pointer"]), None)
                                if old is not None:
                                    old.update(item)
                                else:
                                    state["used"].append(item)
                        state["history_files"][str(path)] = digest
                        if tracks and not any(
                            p.get("history_file") == str(path)
                            for p in state["projects"]
                        ):
                            state["projects"].append(
                                {
                                    "history_file": str(path),
                                    "status": "HISTORICAL_MANIFEST_OBSERVED_EXPORT_NOT_REVERIFIED",
                                }
                            )
                        continue
                    if path.suffix.lower() not in AUDIO_EXT | VIDEO_EXT:
                        continue
                    st = path.stat()
                    cached = state["media"].get(str(path), {})
                    signature = [st.st_size, st.st_mtime_ns, st.st_ctime_ns]
                    if cached.get("stat") == signature:
                        continue
                    info = json.loads(
                        run(
                            [
                                "ffprobe",
                                "-v",
                                "error",
                                "-show_streams",
                                "-show_format",
                                "-of",
                                "json",
                                str(path),
                            ]
                        )
                    )
                    streams = info.get("streams", [])
                    video = next(
                        (
                            s
                            for s in streams
                            if s["codec_type"] == "video"
                            and not s.get("disposition", {}).get("attached_pic")
                        ),
                        None,
                    )
                    tags = {
                        k.lower(): v
                        for k, v in info.get("format", {}).get("tags", {}).items()
                    }
                    title, artist = identity(
                        dict(
                            path=str(path),
                            title=tags.get("title"),
                            artist=tags.get("artist"),
                        )
                    )
                    sidecar = path.with_suffix(".info.json")
                    origin = read(sidecar, {})
                    state["media"][str(path)] = dict(
                        path=str(path),
                        stat=signature,
                        sha256=sha256(path),
                        available=True,
                        kind="video" if video else "audio",
                        title=origin.get("title") or title,
                        artist=artist,
                        genre=tags.get("genre", ""),
                        duration=float(info.get("format", {}).get("duration", 0)),
                        width=(video or {}).get("width"),
                        height=(video or {}).get("height"),
                        fps=(video or {}).get("r_frame_rate"),
                        url=origin.get("webpage_url"),
                        uploader=origin.get("uploader"),
                        license=origin.get("license"),
                        provenance=str(sidecar)
                        if sidecar.exists()
                        else "local tags/path",
                    )
                    state["media"][str(path)].update(
                        release_date=tags.get("date"),
                        isrc=tags.get("isrc"),
                        spotify_uri=tags.get("spotify_uri"),
                    )
                except (OSError, ValueError, KeyError, TypeError, UltraError) as e:
                    state["errors"].append({"path": str(path), "error": str(e)})
    for row in state["used"]:
        alias = state["track_identities"].get(row.get("source"))
        if alias:
            row.update(alias, family=family(alias["title"]))
    return state


def import_sources(path, state):
    """Read the old find_sources/download_sources manifests without executing them."""
    data = read(path)
    if not isinstance(data, dict):
        return
    entries = data.get("entries", list(data.values()))
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = entry.get("webpage_url") or entry.get("url")
        if not url and re.fullmatch(r"[\w-]{11}", str(entry.get("id", ""))):
            url = "https://www.youtube.com/watch?v=" + entry["id"]
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        row = state["discovered_sources"].setdefault(url, {"webpage_url": url, "evidence": []})
        for key in ("id", "title", "duration", "license", "channel_url", "uploader", "file"):
            if entry.get(key) is not None:
                row[key] = entry[key]
        if data.get("query"):
            row["query"] = data["query"]
        if str(path) not in row["evidence"]:
            row["evidence"].append(str(path))


def permitted(state, row):
    permission = state["permissions"].get(row["sha256"], {})
    return (
        row.get("available")
        and permission.get("reuse") is True
        and bool(permission.get("evidence"))
    )


def select_music(state, style, playlist):
    used = {r["family"] for r in state["used"]}
    hashes = {r.get("sha256") for r in state["used"] if r.get("sha256")}
    uncertain = {r["family"] for r in state.get("unconfirmed_history", [])}
    chosen, excluded, seen = [], [], set()
    selected_hashes = set()
    tracks = playlist["tracks"] if playlist is not None else None
    for row in sorted(state["media"].values(), key=lambda r: r["path"]):
        if row["kind"] != "audio" or not row.get("available"):
            continue
        key = family(row["title"])
        if key in uncertain and key not in used:
            excluded.append(dict(path=row["path"], title=row["title"], reason="usage_unconfirmed_analysis_only"))
            continue
        if (
            key in used
            or row["sha256"] in hashes
            or key in seen
            or row["sha256"] in selected_hashes
        ):
            excluded.append(
                dict(
                    path=row["path"],
                    title=row["title"],
                    reason="previously_used_or_same_title_family",
                )
            )
            continue
        if not permitted(state, row):
            excluded.append(dict(path=row["path"], reason="reuse_permission_missing"))
            continue
        match = None
        if tracks is not None:
            # Exact normalized version plus artist; remixes only collapse for exclusion.
            matches = [
                t
                for t in tracks
                if normalize(t["name"]) == normalize(row["title"])
                and normalize(row["artist"])
                in (
                    {normalize(a["name"]) for a in t["artists"]}
                    | {normalize(", ".join(a["name"] for a in t["artists"]))}
                )
                and (
                    not t.get("duration_ms")
                    or abs(t["duration_ms"] / 1000 - row.get("duration", 0)) < 3
                )
            ]
            matches = list(
                {
                    t.get("uri", json.dumps(t, sort_keys=True)): t for t in matches
                }.values()
            )
            if len(matches) != 1:
                excluded.append(
                    dict(
                        path=row["path"],
                        reason="spotify_identity_unmatched_or_ambiguous",
                    )
                )
                continue
            match = matches[0]
        elif normalize(style).replace("-", " ") not in normalize(
            row["path"] + " " + row.get("genre", "")
        ).replace("-", " "):
            continue
        if style == "rnb-2000s":
            date = (
                (match or {}).get("album", {}).get("release_date")
                or row.get("release_date")
                or ""
            )
            if not re.match(r"^200[0-9](?:-|$)", date):
                excluded.append(
                    dict(
                        path=row["path"],
                        reason="release_year_missing_or_outside_2000_2009",
                    )
                )
                continue
        chosen.append(dict(row, spotify=match))
        seen.add(key)
        selected_hashes.add(row["sha256"])
    return chosen, excluded
