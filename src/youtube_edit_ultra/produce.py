"""Acquire permitted assets and orchestrate the existing create engine."""

import fcntl
import hashlib
import json
import re
import shutil
import subprocess
import time
import sys
from pathlib import Path

from . import catalogue as cat, spotify
from .media import UltraError, download_explicit, download_audio_explicit, downloader_command, slug
from .spec import parse_prompt, normalize


def legacy_candidates(state, athlete):
    words = normalize(athlete).split()
    return [dict(r) for r in state.get("discovered_sources", {}).values()
            if all(w in normalize((r.get("title") or "") + " " + r.get("query", ""))
                   for w in words)]


def discover(athlete, cache, queries=()):
    """Resumable multi-query search, adapted from Haaland's find_sources.py.

    Discovery failures stay explicit; one failed query must not discard others.
    """
    from concurrent.futures import ThreadPoolExecutor

    sport = parse_prompt(athlete)["sport"]
    suffixes = (["boxing highlights", "full fight", "body punches counters defense"]
                if sport == "boxing" else ["highlights", "best goals", "skills"]
                if sport == "football" else ["sports highlights", "competition", "training"])
    queries = list(dict.fromkeys([athlete + " " + s for s in suffixes] + list(queries)[:3]))

    def search(query):
        path = cache / (slug(query) + ".json")
        try:
            if path.exists() and time.time() - path.stat().st_mtime < 86400:
                return cat.read(path), None
            cp = subprocess.run([
                *downloader_command(), "--ignore-config", "--skip-download", "--dump-single-json",
                "--no-warnings", "--socket-timeout", "15", "--retries", "1", "--",
                f"ytsearch10:{query}"], capture_output=True, text=True, timeout=100)
            if cp.returncode:
                raise UltraError(cp.stderr[-1000:])
            result = []
            for e in json.loads(cp.stdout).get("entries", []):
                if e:
                    result.append({**{k: e.get(k) for k in [
                        "id", "title", "webpage_url", "uploader", "channel_url", "license", "duration"]},
                        "query": query})
            cat.save(path, result)
            return result, None
        except (OSError, ValueError, UltraError, subprocess.TimeoutExpired) as e:
            return [], {"query": query, "error": str(e)}

    result, errors = {}, []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows, error in pool.map(search, queries):
            if error:
                errors.append(error)
            for row in rows:
                if row.get("webpage_url"):
                    result[row["webpage_url"]] = row
    cat.save(cache / "last_search_report.json", dict(
        queries=queries, errors=errors, candidate_count=len(result)))
    return list(result.values())


def cc_by(candidate):
    # YouTube's extractor supplies this licence field, never infer it from the title.
    return normalize(candidate.get("license") or "") in {
        "creative commons attribution license (reuse allowed)",
        "creative commons attribution license (reuse allowed).",
    }


def download_permission(candidate, config):
    """A licence label alone does not establish the uploader's ownership."""
    return cc_by(candidate) and candidate.get("channel_url") in config.get(
        "trusted_cc_publishers", []
    )


def resolve_playlist(folder, config, style, explicit):
    """A saved genre preference is optional; an explicitly requested playlist is binding."""
    url = explicit or config.get("playlists", {}).get(style)
    status = dict(mode="local", requested_url=url, membership_verified=False)
    try:
        if not url and (folder / "spotify.secret.json").exists():
            url = spotify.find_playlist(style, spotify.client(folder))
            config.setdefault("playlists", {})[style] = url
            cat.save(folder / "config.json", config)
        if not url:
            return None, None, status
        status["requested_url"] = url
        data = spotify.playlist(url, spotify.client(folder))
        cat.save(folder / "playlists" / (slug(style) + ".json"), data)
        status.update(mode="spotify", membership_verified=True)
        return data, url, status
    except (UltraError, ValueError, KeyError, OSError) as e:
        if explicit:
            raise UltraError(str(e)) from e
        status.update(mode="local_fallback", error=str(e))
        return None, None, status


def athlete_match(text, athlete):
    words = normalize(athlete).split()
    normalized = normalize(text)
    if all(re.search(r"\b" + re.escape(w) + r"\b", normalized) for w in words):
        return True
    return normalize(athlete) == "canelo alvarez" and bool(re.search(r"\bcanelo\b", normalized))


def relevant_video(row, athlete):
    path = Path(row["path"])
    # A user's home directory is not an athlete tag (e.g. /Users/benjamindacunha).
    try:
        path = path.relative_to(Path.home())
    except ValueError:
        pass
    text = normalize((row.get("title") or "") + " " + str(path))
    return row["kind"] == "video" and athlete_match(text, athlete)


def annotated_coverage(videos, sport):
    from .events import from_json, validate_no_overlap
    actions = []
    for row in {r['sha256']: r for r in videos}.values():
        source = Path(row['path'])
        annotation = source.with_suffix('.actions.json')
        shots = source.with_suffix('.shots.json')
        if shots.is_file():
            from .events import Action
            for shot in cat.read(shots):
                if shot.get('provenance') not in {'annotation', 'visual_review', 'visual_sample_review', 'human_review'}:
                    continue
                start, end = shot['safe_start'], shot['safe_end']
                if not 0 <= start <= shot['core_start'] < shot['core_end'] <= end <= row['duration']:
                    raise UltraError('Invalid shot boundaries: ' + str(shots))
                actions.append(Action(str(source), start, (start + end) / 2, end,
                                      sport=sport, label=shot.get('label', 'action'),
                                      confidence=shot.get('quality', 1), provenance=shot['provenance']))
            continue
        if annotation.exists():
            actions.extend(from_json(annotation, source, row['duration'], sport))
    return sum(a.duration for a in validate_no_overlap(actions))


def readiness(state, athlete, target, videos, music, style="", mode="personal"):
    local = [r for r in state["media"].values() if r.get("available") and relevant_video(r, athlete)]
    local = list({r["sha256"]: r for r in local}.values())
    audio = [r for r in state["media"].values() if r.get("available") and r["kind"] == "audio"
             and normalize(style).replace("-", " ") in
             normalize(r["path"] + " " + r.get("genre", "")).replace("-", " ")]
    audio = list({r["sha256"]: r for r in audio}.values())
    available_music = max(0, sum(r.get("usable_duration", r["duration"]) for r in music) - .7 * max(0, len(music) - 1))
    return dict(
        target_seconds=target,
        video=dict(accessible_raw_seconds=sum(r["duration"] for r in local),
                   permitted_raw_seconds=sum(r["duration"] for r in videos),
                   permitted_raw_shortfall_seconds=max(0, target - sum(r["duration"] for r in videos))),
        audio=dict(accessible_style_matched_seconds=sum(r["duration"] for r in audio),
                   selected_seconds_after_crossfades=available_music,
                   selected_shortfall_seconds=max(0, target - available_music)),
        technical=dict(video_files_missing=not local, audio_style_files_missing=not audio),
        permissions=dict(video_files_without_evidence=[r["path"] for r in local if not cat.permitted(state, r, mode=mode)],
                         audio_files_without_evidence=[r["path"] for r in audio if not cat.permitted(state, r, mode=mode)]),
        editorial=dict(unique_complete_actions_seconds=None,
                       status="NOT_VERIFIED; raw durations are upper bounds, not usable action coverage"),
    )


def verify_output(path, target, **kwargs):
    # Kept here for existing callers and production scripts.
    from .quality import verify_output as verify
    return verify(path, target, **kwargs)


def execute(args):
    folder = Path(args.state_dir).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "catalogue.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UltraError("Une autre opération utilise ce catalogue") from None
        return locked(args, folder)


def locked(args, folder, *, output=None, prepare_only=False):

    request = getattr(args, 'request', None) or parse_prompt(args.prompt)
    mode = getattr(args, 'mode', 'personal')
    if request["athlete"] == "Sport highlights":
        raise UltraError(
            "Sportif non reconnu ; préciser un nom supporté ou utiliser ultra create --athlete"
        )
    state = cat.read(folder / "catalogue.json", cat.empty())
    config = cat.read(folder / "config.json", {})
    roots = (
        args.roots
        or config.get("roots")
        or [
            str(Path.home() / x)
            for x in ["Documents", "Music", "Movies", "Downloads", "Desktop"]
        ]
    )
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + str(time.time_ns())[-6:]
    out = Path(output) if output is not None else Path(args.output_dir).expanduser().resolve() / stamp
    out.mkdir(parents=True, exist_ok=output is not None)
    report = dict(
        status="RUNNING",
        request=request,
        roots=roots,
        blockers=[],
        warnings=[],
        output=str(out),
        history_scope="recognized local manifests, not exhaustive deleted-project or YouTube history",
        mode=mode,
    )
    report_path = out / "production_report.json"
    cat.save(report_path, report)
    try:
        print("Catalogue : recherche et indexation des médias locaux", flush=True)
        cat.scan(roots, state)
        cat.save(folder / "catalogue.json", state)
        cat.save(
            out / "scan_report.json",
            dict(
                errors=state["errors"],
                media_count=len(state["media"]),
                history_files=state["history_files"],
            ),
        )
        if state["errors"]:
            report["warnings"].append(
                "Erreurs de scan : voir scan_report.json ; couverture historique partielle"
            )
        if any(Path(e["path"]).name in cat.HISTORY for e in state["errors"]):
            report["blockers"].append(
                "Historique musical illisible ; corriger les fichiers signalés dans scan_report.json"
            )
        videos = [
            r
            for r in state["media"].values()
            if r["kind"] == "video"
            and cat.permitted(state, r, mode=mode)
            and relevant_video(r, request["athlete"])
        ]
        candidates = legacy_candidates(state, request["athlete"])
        if not args.offline:
            for entry in state.get("authorized_urls", []):
                if not cat.grant_allows({"reuse": True, **entry}, mode):
                    continue
                if entry["kind"] == "video" and normalize(
                    entry.get("athlete", "")
                ) != normalize(request["athlete"]):
                    continue
                if entry["kind"] == "audio" and entry.get("style") != request["style"]:
                    continue
                # A validated local copy must work even when its host is now unavailable.
                cached = [r for r in state["media"].values()
                          if r.get("url") == entry["url"] and r["kind"] == entry["kind"]
                          and cat.permitted(state, r, mode=mode)]
                if cached:
                    if entry["kind"] == "video":
                        videos.extend(cached)
                    continue
                try:
                    dest = (
                        folder
                        / "downloads"
                        / hashlib.sha256(entry["url"].encode()).hexdigest()[:20]
                    )
                    if shutil.disk_usage(folder).free < 2_000_000_000:
                        raise UltraError("Moins de 2 Go libres")
                    downloader = (
                        download_explicit
                        if entry["kind"] == "video"
                        else download_audio_explicit
                    )
                    files = downloader([entry["url"]], dest)
                    cat.scan([dest], state)
                    for f in files:
                        r = state['media'].get(str(f.resolve()))
                        if not r or not r.get('available'):
                            raise UltraError('Acquired file failed catalogue validation: ' + str(f))
                        r.update(
                            url=entry["url"],
                            title=entry.get("title") or r["title"],
                            artist=entry.get("artist") or r["artist"],
                            genre=entry.get("style", ""),
                        )
                        grant = {k: value for k, value in entry.items()
                                 if k not in {'url', 'kind', 'athlete', 'style', 'title', 'artist'}}
                        grant.setdefault('reuse', True)
                        state['permissions'][r['sha256']] = grant
                        for key in ('release_date', 'language', 'country'):
                            if entry.get(key): r[key] = entry[key]
                        if entry["kind"] == "video":
                            videos.append(r)
                except (UltraError, OSError) as e:
                    report["warnings"].append(str(e))
        if not args.offline and annotated_coverage(videos, request['sport']) < request["duration_seconds"]:
            try:
                print("Recherche publique des sources et de leurs licences", flush=True)
                fresh = discover(request["athlete"], folder / "search",
                                 [c["query"] for c in candidates if c.get("query")])
                search_report = cat.read(folder / "search" / "last_search_report.json", {})
                cat.save(out / "search_report.json", search_report)
                report["warnings"].extend("Recherche partielle : " + e["query"] + ": " + e["error"]
                                          for e in search_report.get("errors", []))
                candidates = list({c["webpage_url"]: c for c in [*candidates, *fresh]}.values())
                for c in candidates:
                    c['permission'] = 'declared_CC_BY' if cc_by(c) else 'UNKNOWN_NO_DOWNLOAD'
                    if mode == "commercial" or not download_permission(c, config):
                        c["permission"] = "UNVERIFIED_NO_DOWNLOAD"
                        continue
                    if not athlete_match(c["title"] or "", request["athlete"]):
                        continue
                    cached = [r for r in state['media'].values()
                              if r.get('url') == c['webpage_url'] and cat.permitted(state, r, mode=mode)]
                    if cached:
                        videos.extend(cached)
                        c['acquisition_status'] = 'CACHED'
                        continue
                    try:
                        if shutil.disk_usage(folder).free < 2_000_000_000:
                            raise UltraError("Moins de 2 Go libres avant téléchargement")
                        destination = (
                            folder
                            / "downloads"
                            / hashlib.sha256(c["webpage_url"].encode()).hexdigest()[:20]
                        )
                        files = download_explicit([c["webpage_url"]], destination)
                        cat.scan([destination], state)
                        for f in files:
                            r = state['media'].get(str(f.resolve()))
                            if not r or not r.get('available'):
                                raise UltraError('Acquired file failed catalogue validation: ' + str(f))
                            r.update(
                                title=c["title"],
                                url=c["webpage_url"],
                                uploader=c["uploader"],
                                license=c["license"],
                            )
                            state["permissions"][r["sha256"]] = dict(
                                reuse=True,
                                evidence=c,
                                checked_at=time.time(),
                                basis="CC_BY_from_user_trusted_publisher",
                            )
                            videos.append(r)
                    except (UltraError, OSError, ValueError) as exc:
                        c['acquisition_error'] = str(exc)
                        report['warnings'].append(c['webpage_url'] + ': ' + str(exc))
                        continue
                cat.save(folder / "catalogue.json", state)
            except (UltraError, ValueError, OSError) as e:
                report["warnings"].append(str(e))
        cat.save(out / "discovery_report.json", candidates)
        # Byte-identical files across projects must not become duplicated actions.
        videos = list({r["sha256"]: r for r in videos}.values())
        playlist = playlist_url = None
        try:
            mentioned = re.search(r"https://open\.spotify\.com/playlist/[a-zA-Z0-9]{22}|spotify:playlist:[a-zA-Z0-9]{22}", args.prompt)
            explicit = args.playlist or (mentioned.group() if mentioned else None)
            if not explicit and re.search(r"\b(spotify|playlist)\b", normalize(args.prompt)):
                explicit = config.get("playlists", {}).get(request["style"])
                if not explicit:
                    raise UltraError("Playlist demandée explicitement : fournir son URL avec --playlist")
            if args.offline:
                if explicit:
                    cached = cat.read(folder / 'playlists' / (slug(request['style']) + '.json'), {})
                    if not cached or cached.get('url') != explicit:
                        raise UltraError('Offline: requested Spotify playlist has no matching complete cache')
                    playlist, playlist_url = cached, explicit
                    report['spotify'] = dict(mode='offline_cache', membership_verified=True,
                                             snapshot_scope='Previously fetched; current remote membership not checked')
                else:
                    report['spotify'] = dict(mode='offline_local', membership_verified=False)
            else:
                playlist, playlist_url, report['spotify'] = resolve_playlist(folder, config, request['style'], explicit)
            if playlist is not None:
                cat.save(out / "spotify_playlist.json", playlist)
            if report["spotify"]["mode"] == "local_fallback":
                report["warnings"].append("Spotify facultatif indisponible ; sélection locale autorisée, appartenance Spotify NON vérifiée : " + report["spotify"]["error"])
        except UltraError as e:
            report["blockers"].append(str(e))
            report["spotify"] = dict(mode="required_unavailable", membership_verified=False, error=str(e))
        music, excluded = cat.select_music(state, request["style"], playlist, mode=mode)
        from .music import audio_profile
        for row in music:
            row["usable_duration"] = audio_profile(Path(row["path"]), cache_dir=out / 'cache/audio-profiles')["usable_duration"]
            state['media'][row['path']]['usable_duration'] = row['usable_duration']
        if (not args.offline and playlist is None and not report["blockers"]
                and sum(r.get("usable_duration", r["duration"]) for r in music) - .7 * max(0, len(music) - 1)
                < request["duration_seconds"] + 1):
            from .music_sources import acquire
            print("Recherche et acquisition musicale auprès des catalogues sous licence", flush=True)
            acquisition = acquire(request['style'], request['duration_seconds'], state, folder,
                                  **({'mode': mode} if mode != 'personal' else {}))
            cat.save(out / "music_acquisition_report.json", acquisition)
            report["warnings"].extend(acquisition["errors"])
            music, excluded = cat.select_music(state, request["style"], playlist, mode=mode)
        ready = readiness(state, request["athlete"], request["duration_seconds"], videos, music, request["style"], mode=mode)
        cat.save(out / "readiness_report.json", ready)
        cat.save(
            out / "excluded_tracks.json",
            dict(history=state["used"], unconfirmed=state.get("unconfirmed_history", []), excluded=excluded, exhaustive=False),
        )
        if not videos:
            report["blockers"].append(
                "Aucune vidéo pertinente avec permission de réutilisation documentée"
            )
        elif ready["video"]["permitted_raw_shortfall_seconds"] > 5:
            report["blockers"].append(
                f"Vidéo autorisée insuffisante même avant sélection : {ready['video']['permitted_raw_seconds']:.3f} s brutes pour {request['duration_seconds']:.3f} s demandées"
            )
        if not music:
            report["blockers"].append(
                "Aucune musique autorisée, inédite dans les historiques connus et correspondant au style/Spotify"
            )
        elif ready["audio"]["selected_shortfall_seconds"] > 0.01:
            report["blockers"].append(
                f"Musique admissible insuffisante après fondus : {ready['audio']['selected_seconds_after_crossfades']:.3f} s pour {request['duration_seconds']:.3f} s demandées"
            )
        cat.save(out / "source_candidates.json", dict(videos=videos, music=music))
        if report["blockers"]:
            raise UltraError("; ".join(report["blockers"]))
        if prepare_only and playlist is None:
            from .music import arrange_playlist
            music, progression = arrange_playlist(music, cache_dir=out / 'cache/audio-profiles')
            cat.save(out / 'playlist_progression.json', progression)
            cat.save(out / 'source_candidates.json', dict(videos=videos, music=music))
        sources = []
        for video in videos:
            p = Path(video["path"])
            annotation = p.with_suffix(".actions.json")
            sources.append(
                dict(
                    path=str(p),
                    **({"annotations": str(annotation)} if annotation.exists() else {}),
                )
            )
        manifest = dict(
            editorial=True,
            athlete=request["athlete"],
            sport=request["sport"],
            style=request["style"],
            duration=f"{request['duration_seconds']}s",
            sources=sources,
            sources_only=True,
            music=[r["path"] for r in music],
            library=str(folder / "library"),
            cache_dir=str(out / "cache"),
            output_dir=str(out),
        )
        cat.save(out / 'project.json', manifest)
        if prepare_only:
            report.update(status='PREPARED', manifest=str(out / 'project.json'))
            return 0
        argv = [
            "create",
            args.prompt,
            "--spec",
            str(out / "project.json"),
            "--publish",
            "none",
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--fps",
            str(args.fps),
        ]
        if args.strict_actions:
            argv.append("--strict-actions")
        if args.semantic_model:
            argv += ["--semantic-model", args.semantic_model]
        print(
            "Rendu via le moteur create ; journal : " + str(out / "engine.log"),
            flush=True,
        )
        with (out / "engine.log").open("w") as log:
            result = subprocess.run(
                [sys.executable, "-m", "youtube_edit_ultra.cli", *argv],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if result.returncode:
            raise UltraError(
                "Le moteur create a refusé le montage : "
                + (out / "engine.log").read_text()[-1200:]
            )
        rendered = (
            out / f"{slug(request['athlete'])}-{round(request['duration_seconds'])}s"
        )
        from .quality import finalize_output
        qa = finalize_output(rendered / 'montage.mp4', request['duration_seconds'], job_dir=out,
                             width=args.width, height=args.height, fps=args.fps)
        integrity = cat.read(rendered / "action_integrity_report.json")
        if not integrity["all_selected_event_windows_preserved"]:
            raise UltraError("Action tronquée dans la timeline")
        qa["protected_action_cores_preserved"] = True
        qa["exact_action_windows_preserved"] = not manifest.get("editorial", False)
        qa["visual_duplicate_review"] = (
            "NOT_VERIFIED (only byte-identical source deduplication)"
        )
        qa["filler_segments"] = integrity["filler_segments"]
        cat.save(rendered / "verification_report.json", qa)
        source_report = cat.read(rendered / "source_report.json")
        source_report["catalogue_sources"] = [
            dict(
                r, permission=state["permissions"][r["sha256"]], identity_verified=False
            )
            for r in videos
        ]
        cat.save(rendered / "source_report.json", source_report)
        cat.save(
            rendered / "excluded_tracks.json", cat.read(out / "excluded_tracks.json")
        )
        actual = set(cat.read(rendered / "source_report.json")["music"])
        tracks = [r for r in music if r["path"] in actual]
        offset = 0.0
        for i, r in enumerate(tracks):
            r["permission"] = state["permissions"][r["sha256"]]
            r["order"] = i + 1
            r["timeline_start"] = offset
            profile = audio_profile(Path(r["path"]))
            r["source_start"] = profile["source_start"]
            r["used_seconds"] = min(profile["usable_duration"], request["duration_seconds"] - offset)
            r["source_end"] = r["source_start"] + r["used_seconds"]
            r["timeline_end"] = offset + r["used_seconds"]
            offset += r["used_seconds"] - 0.7
            state["used"].append(
                dict(
                    title=r["title"],
                    artist=r["artist"],
                    family=cat.family(r["title"]),
                    sha256=r["sha256"],
                    evidence=qa["output"],
                )
            )
        cat.save(
            rendered / "music_tracklist.json",
            dict(tracks=tracks, playlist=playlist_url, spotify_status=report["spotify"], crossfade_seconds=0.7),
        )
        credits = []
        for r in [*videos, *tracks]:
            permission = state["permissions"][r["sha256"]]
            if permission.get("credit"):
                credits.append(permission["credit"])
        if credits:
            metadata_path = rendered / "youtube_metadata.json"
            metadata = cat.read(metadata_path)
            metadata["description"] += "\n\nSources et licences :\n" + "\n".join(dict.fromkeys(credits))
            metadata["source_credits"] = list(dict.fromkeys(credits))
            cat.save(metadata_path, metadata)
        state["projects"].append(
            dict(
                prompt=args.prompt,
                path=str(rendered),
                sha256=qa["sha256"],
                status=qa["status"],
            )
        )
        report.update(
            status=qa["status"],
            rendered=str(rendered),
            quality_flags=qa["quality_flags"],
        )
        print("Export local : " + qa["output"], flush=True)
        return 0
    except (UltraError, ValueError, OSError) as e:
        report["status"] = "BLOCKED"
        if str(e) not in report["blockers"]:
            report["blockers"].append(str(e))
        print(
            "Production bloquée : " + str(e) + "\nRapport : " + str(report_path),
            flush=True,
        )
        return 2
    finally:
        cat.save(folder / "catalogue.json", state)
        cat.save(report_path, report)


def catalogue_command(args):
    folder = Path(args.state_dir).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "catalogue.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UltraError("Catalogue en cours d’utilisation") from None
        state = cat.read(folder / "catalogue.json", cat.empty())
        if args.catalogue_action == "scan":
            cat.scan(
                args.roots
                or [
                    Path.home() / x
                    for x in ["Documents", "Music", "Movies", "Downloads", "Desktop"]
                ],
                state,
            )
        elif args.catalogue_action == "authorize-url":
            from urllib.parse import urlparse

            u = urlparse(args.url)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise UltraError("URL HTTPS sans identifiants requise")
            if u.hostname == "spotify.com" or u.hostname.endswith(".spotify.com"):
                raise UltraError(
                    "Spotify fournit seulement des métadonnées ; indiquer la source audio autorisée"
                )
            if not args.evidence.strip():
                raise UltraError("Justificatif requis")
            row = dict(
                url=args.url,
                kind=args.kind,
                evidence=args.evidence,
                athlete=args.athlete,
                style=args.style,
                title=args.title,
                artist=args.artist,
            )
            row.update(_permission_from_args(args))
            row.update({k: getattr(args, k) for k in ('release_date', 'language', 'country') if getattr(args, k, None)})
            state.setdefault("authorized_urls", [])[:] = [
                r for r in state.get("authorized_urls", []) if r["url"] != args.url
            ] + [row]
        else:
            p = Path(args.path).expanduser().resolve()
            if not args.evidence.strip():
                raise UltraError("Justificatif de permission requis")
            digest = cat.sha256(p)
            cat.scan([p.parent], state)
            row = state['media'].get(str(p))
            if not row or not row.get('available') or row['sha256'] != digest:
                raise UltraError('File could not be indexed safely: ' + str(p))
            for arg, key in [('title', 'title'), ('artist', 'artist'), ('style', 'genre'),
                             ('release_date', 'release_date'), ('language', 'language'), ('country', 'country')]:
                if getattr(args, arg, None):row[key] = getattr(args, arg)
            if getattr(args, 'athlete', None):
                row['title'] = args.athlete + ' ' + row.get('title', '')
            state['permissions'][digest] = _permission_from_args(args, state['permissions'].get(digest))
        cat.save(folder / "catalogue.json", state)
        print(
            f"Catalogue : {len(state['media'])} médias ; {len(state['used'])} occurrences historiques ; {len(state['errors'])} erreurs"
        )
    return 0


def _permission_from_args(args, previous=None):
    data = cat.read(Path(args.rights_json).expanduser()) if getattr(args, 'rights_json', None) else {}
    if not isinstance(data, dict):
        raise UltraError('Rights JSON must be an object')
    mode = getattr(args, 'mode', None) or data.pop('scope', 'personal')
    for key in ('scope', 'mode', 'evidence', 'reuse', 'previous'):
        data.pop(key, None)
    return cat.permission_grant(args.evidence, mode=mode, previous=previous, **data)


def _permission_options(parser, *, local=False):
    parser.add_argument('--mode', choices=['personal', 'commercial'])
    parser.add_argument('--rights-json', help='Preuve et portée commerciale explicites en JSON')
    parser.add_argument('--release-date')
    parser.add_argument('--language')
    parser.add_argument('--country')
    if local:
        for name in ('athlete', 'style', 'title', 'artist'):
            parser.add_argument('--' + name)


def spotify_command(args):
    folder = Path(args.state_dir).expanduser().resolve()
    if args.spotify_action == "login":
        print(spotify.login_start(folder, args.client_id))
    elif args.spotify_action == "finish":
        spotify.login_finish(folder, args.callback)
    elif args.spotify_action == "list":
        for row in spotify.user_playlists(spotify.client(folder)):
            print(row["uri"] + " " + row["name"])
    else:
        data = spotify.playlist(args.playlist, spotify.client(folder))
        cat.save(folder / "playlists" / (slug(args.style) + ".json"), data)
        config = cat.read(folder / "config.json", {})
        config.setdefault("playlists", {})[args.style] = data["url"]
        cat.save(folder / "config.json", config)
        print(
            f"Playlist complète : {data['total_items']} entrées ; {len(data['unavailable'])} indisponibles/locales/non musicales"
        )
    return 0


def add_commands(sub):
    state = str(Path.home() / ".local/share/youtube-edit-ultra")
    p = sub.add_parser(
        "produce",
        help="Découvrir les médias autorisés, monter et vérifier sans publication",
    )
    p.add_argument("prompt")
    p.add_argument("--state-dir", default=state)
    p.add_argument("--root", dest="roots", action="append")
    p.add_argument("--output-dir", default="output/productions")
    p.add_argument("--playlist")
    p.add_argument("--offline", action="store_true")
    p.add_argument('--mode', choices=['personal', 'commercial'], default='personal')
    p.add_argument("--strict-actions", action="store_true")
    p.add_argument("--semantic-model")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--fps", type=int, default=30)
    p.set_defaults(func=execute)
    p = sub.add_parser(
        "catalogue", help="Indexer ou mémoriser une permission pour un fichier"
    )
    p.add_argument("--state-dir", default=state)
    actions = p.add_subparsers(dest="catalogue_action", required=True)
    s = actions.add_parser("scan")
    s.add_argument("--root", dest="roots", action="append")
    s.set_defaults(func=catalogue_command)
    s = actions.add_parser("authorize")
    s.add_argument("path")
    s.add_argument("--evidence", required=True)
    _permission_options(s, local=True)
    s.set_defaults(func=catalogue_command)
    s = actions.add_parser("authorize-url")
    s.add_argument("url")
    s.add_argument("--evidence", required=True)
    s.add_argument("--kind", choices=["video", "audio"], required=True)
    s.add_argument("--athlete")
    s.add_argument("--style")
    s.add_argument("--title")
    s.add_argument("--artist")
    _permission_options(s)
    s.set_defaults(func=catalogue_command)
    p = sub.add_parser(
        "spotify",
        help="Authentification PKCE et lecture intégrale des playlists (métadonnées)",
    )
    p.add_argument("--state-dir", default=state)
    actions = p.add_subparsers(dest="spotify_action", required=True)
    s = actions.add_parser("login")
    s.add_argument("--client-id", required=True)
    s.set_defaults(func=spotify_command)
    s = actions.add_parser("finish")
    s.add_argument("callback")
    s.set_defaults(func=spotify_command)
    s = actions.add_parser("sync")
    s.add_argument("playlist")
    s.add_argument("--style", required=True)
    s.set_defaults(func=spotify_command)
    s = actions.add_parser("list")
    s.set_defaults(func=spotify_command)
