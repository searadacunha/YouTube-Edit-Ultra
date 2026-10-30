"""Discover licensed music from publisher catalogues, without Spotify credentials."""
import hashlib
import html
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from . import catalogue as cat
from .media import UltraError, validate_media, _download_budget
from .spec import normalize
from .music import audio_profile


def fetch(url, cache):
    path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    if not path.exists() or time.time() - path.stat().st_mtime > 86400:
        cp = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                             '--proto', '=https', '--proto-redir', '=https', '--retry', '2',
                             '--max-time', '25', '--max-filesize', '5000000', url],
                            capture_output=True)
        if cp.returncode:
            raise UltraError(cp.stderr.decode(errors='replace')[-500:])
        data = cp.stdout
        if len(data) > 5_000_000:
            raise UltraError("Music catalogue response too large")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    # Licence evidence stays immutable when the daily discovery cache refreshes.
    evidence = path.with_name(path.stem + '-' + hashlib.sha256(data).hexdigest()[:20] + '.html')
    if not evidence.exists():
        evidence.write_bytes(data)
    return data.decode(), str(evidence)


def mixkit_rows(page, style):
    result = []
    for raw in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("@graph", []), list):
            raise ValueError("Mixkit metadata must contain a graph list")
        for group in data.get("@graph", []):
            if not isinstance(group, dict) or not isinstance(group.get("itemListElement", []), list):
                raise ValueError("Invalid Mixkit track group")
            for item in group.get("itemListElement", []):
                if not isinstance(item, dict):
                    raise ValueError("Invalid Mixkit track metadata")
                if item.get("@type") != "MusicRecording":
                    continue
                if not all(isinstance(item.get(k), str) for k in ("url", "name", "byArtist", "genre")):
                    raise ValueError("Music recording identity and genre must be strings")
                url = item.get("url", "")
                if (item.get("@type") == "MusicRecording"
                        and item.get("license") == "https://mixkit.co/license/#musicFree"
                        and item.get("isAccessibleForFree") is True
                        and url.startswith("https://assets.mixkit.co/music/")
                        and normalize(item.get("genre", "")) == normalize(style)):
                    result.append(dict(title=item["name"], artist=item["byArtist"],
                                       url=url, license=item["license"], style=style))
    return result


def fsm_row(page, url, style):
    # Restrict parsing to the selected track, before the similar-track catalogue.
    head = page.split("<div class='spotifyPlaylistsCont'", 1)[0]
    title = re.search(r"<title>(.*?) by (.*?) \|", head, re.S)
    categories = re.search(r"class=['\"]trackCategories['\"][^>]*>(.*?)</p>", head, re.S)
    licence = re.search(r"https://creativecommons\.org/licenses/by/(?:3\.0|4\.0)/[^'\"<\s]*", head)
    audio = re.search(r"href=['\"](/music/[^'\"]+\.mp3)['\"]", head)
    wanted = normalize(style).replace("-", " ")
    tags = normalize(html.unescape(re.sub("<[^>]+>", " ", categories[1]))) if categories else ""
    if not (title and licence and audio and wanted in tags.replace("-", " ")):
        return None
    return dict(title=html.unescape(title[1]), artist=html.unescape(title[2]),
                url=urljoin(url, audio[1]), source_url=url, license=licence[0], style=style)


def discover(style, cache):
    """Retain source-level failures; do not relabel generic funk as Brazilian funk."""
    rows, errors = [], []
    # A modern stock catalogue cannot establish a 2000–2009 release date.
    if style == "rnb-2000s":
        return [], ["R&B 2000s requires recordings with verified release years; stock music is not substituted"]
    for provider in ("mixkit", "fsm"):
        try:
            if provider == "mixkit":
                page, evidence = fetch("https://mixkit.co/free-stock-music/" + quote(style) + "/", cache)
                candidates = mixkit_rows(page, style)
                # Keep the publisher's current licence alongside the catalogue declaration.
                licence, licence_evidence = fetch("https://mixkit.co/license/", cache)
                if "musicFree" not in licence:
                    raise UltraError("Mixkit music licence section unavailable")
                rows.extend(dict(r, evidence=evidence, license_evidence=licence_evidence,
                                 catalogue_url="https://mixkit.co/free-stock-music/" + quote(style) + "/")
                            for r in candidates)
            else:
                page, _ = fetch("https://www.free-stock-music.com/search.php?keyword=" + quote(style.replace("-", " ")), cache)
                paths = list(dict.fromkeys(re.findall(r"href=['\"](/music/[^'\"]+\.mp3)['\"]", page)))
                for path in paths[:30]:
                    url = "https://www.free-stock-music.com/" + Path(path).stem + ".html"
                    try:
                        track, evidence = fetch(url, cache)
                        row = fsm_row(track, url, style)
                        if row:
                            rows.append(dict(row, evidence=evidence))
                    except (OSError, ValueError, UltraError) as exc:
                        errors.append(f"{url}: {exc}")
        except (OSError, ValueError, UltraError) as exc:
            errors.append(f"{provider}: {exc}")
    return list({r["url"]: r for r in rows}.values()), errors


def acquire(style, target, state, folder, mode="personal"):
    """Acquire only enough unheard tracks; reuse files and hash-bound grants."""
    if mode not in {"personal", "commercial"}:
        raise ValueError(f"Unknown rights mode: {mode}")
    cache = folder / "music-discovery"
    candidates, errors = discover(style, cache)
    attempts = []
    used = {r["family"] for r in state["used"] + state.get("unconfirmed_history", [])}
    for row in candidates:
        selected, _ = cat.select_music(state, style, None, mode=mode)
        if sum(audio_profile(Path(r["path"]))["usable_duration"] for r in selected) - .7 * max(0, len(selected) - 1) >= target + 1:
            break
        if cat.family(row["title"]) in used or any(cat.family(r["title"]) == cat.family(row["title"]) for r in selected):
            continue
        commercial = next((entry.get("permission", entry) for entry in state.get("authorized_urls", [])
                           if entry.get("url") == row["url"]
                           and cat.grant_allows(entry.get("permission", entry), "commercial")), None)
        if mode == "commercial" and commercial is None:
            reason = "Commercial licence scope and source rights require explicit verified evidence"
            attempts.append(dict(row, status="SKIPPED_COMMERCIAL_RIGHTS_UNVERIFIED", error=reason))
            errors.append(row["url"] + ": " + reason)
            continue
        dest = cache / hashlib.sha256(row["url"].encode()).hexdigest()[:20]
        dest.mkdir(parents=True, exist_ok=True)
        file = dest / "track.mp3"
        try:
            if urlparse(row["url"]).hostname not in {"assets.mixkit.co", "www.free-stock-music.com"}:
                raise UltraError("Unrecognized music host")
            if not file.exists():
                budget = _download_budget(folder, "audio")
                partial = dest / "track.download"
                cmd = ["curl", "--fail", "--location", "--silent", "--show-error", "--max-time", "60",
                       "--proto", "=https", "--proto-redir", "=https", "--retry", "2",
                       "--max-filesize", str(budget)]
                if row.get("source_url"):
                    cmd += ["--referer", row["source_url"]]
                from .storage import guarded_command
                command = guarded_command([*cmd, "--output", str(partial), row["url"]],
                                          need=budget, path=dest, label="licensed music acquisition")
                cp = subprocess.run(command, capture_output=True, text=True)
                if cp.returncode:
                    raise UltraError(cp.stderr[-500:])
                info = validate_media(partial, "audio", cache_dir=folder / "cache" / "source-validation")
                if info["duration"] <= 2:
                    raise UltraError("Publisher returned no usable audio")
                partial.replace(file)
            validate_media(file, "audio", cache_dir=folder / "cache" / "source-validation")
            cat.scan([dest], state)
            entry = state["media"].get(str(file.resolve()))
            if not entry or not entry.get("available"):
                raise UltraError("Acquired audio failed catalogue inventory")
            entry.update(title=row["title"], artist=row["artist"], genre=style,
                         url=row["url"], provenance=row["evidence"],
                         usable_duration=audio_profile(file)["usable_duration"])
            state["permissions"][entry["sha256"]] = dict(commercial) if commercial else cat.permission_grant(
                row, previous=state["permissions"].get(entry["sha256"]), checked_at=time.time(),
                credit=f"{row['title']} — {row['artist']} | {row.get('source_url', row['url'])} | {row['license']}")
            attempts.append(dict(row, status="AVAILABLE", path=str(file)))
            cat.save(folder / "catalogue.json", state)
        except (OSError, ValueError, UltraError) as exc:
            attempts.append(dict(row, status="FAILED", error=str(exc)))
            errors.append(row["url"] + ": " + str(exc))
    report = dict(candidates=candidates, attempts=attempts, errors=errors)
    cat.save(cache / "last_report.json", report)
    return report
