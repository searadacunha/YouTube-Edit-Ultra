"""One-command natural-language sport montage workflow."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .events import from_json, find_annotation, validate_no_overlap
from .media import UltraError, audio_library, check_binaries, download_explicit, download_audio_explicit, fingerprint, probe, slug, video_library
from .music import build_soundtrack, extract_beats, soundtrack_playlist
from .planner import integrity_report, plan_edit
from .render import render_edits
from .semantic import enrich
from .spec import Settings, detect_sport, load_manifest, parse_duration, parse_prompt
from .thumbnail import create_thumbnail, create_storyboard
from .vision import analyze
from .youtube import upload


def _path(v: str | Path, base: Path) -> Path:
    v = Path(v).expanduser()
    return (base / v).resolve() if not v.is_absolute() else v.resolve()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _build_settings(args: argparse.Namespace, manifest: dict, base: Path) -> Settings:
    parsed = parse_prompt(args.prompt or "")
    # Explicit fields override all guesses, even if the prompt is vague.
    athlete = args.athlete or manifest.get("athlete") or parsed["athlete"]
    sport = args.sport or manifest.get("sport") or (detect_sport(athlete) if parsed["sport"] == "generic" else parsed["sport"])
    style = args.style or manifest.get("style") or parsed["style"]
    duration_value = args.duration or manifest.get("duration")
    duration = parse_duration(duration_value) if duration_value else parsed["duration_seconds"]
    lib = _path(args.library or manifest.get("library", "library"), base)
    output_root = _path(args.output_dir or manifest.get("output_dir", "output"), base)
    out = output_root / f"{slug(athlete)}-{int(round(duration))}s"
    return Settings(athlete=athlete, sport=sport, style=style,
                    duration_seconds=duration, output=out, library=lib,
                    allow_download=args.allow_download, allow_repeat=args.allow_repeat,
                    allow_music_repeat=args.repeat_music, publish=args.publish,
                    width=args.width, height=args.height, fps=args.fps,
                    scene_detect=args.scene_detect, created_from=args.prompt or "",
                    title=args.title or manifest.get("title"))


def _collect_videos(args: argparse.Namespace, manifest: dict, settings: Settings,
                    base: Path) -> tuple[list[Path], dict[str, Path]]:
    videos: set[Path] = set(video_library(settings.library, settings.athlete, all_library=args.all_library))
    annotations: dict[str, Path] = {}
    urls = list(args.source or [])
    for v in args.video or []:
        videos.add(_path(v, base))
    for entry in manifest.get("sources", []):
        if isinstance(entry, str):
            if entry.startswith(("http://", "https://")):
                urls.append(entry)
            else:
                videos.add(_path(entry, base))
        elif isinstance(entry, dict):
            if entry.get("url"):
                urls.append(str(entry["url"]))
            if entry.get("path"):
                p = _path(entry["path"], base)
                videos.add(p)
                if entry.get("annotations"):
                    annotations[str(p)] = _path(entry["annotations"], base)
    if urls and not args.allow_download:
        raise UltraError("URLs fournies mais téléchargement désactivé. Ajouter --allow-download --rights-confirmed.")
    if urls and not args.rights_confirmed:
        raise UltraError("Confirmer avoir les droits/autorisations pour chaque source distante : --rights-confirmed")
    if urls:
        videos.update(download_explicit(urls, settings.library / "downloads"))
    final = sorted(p.resolve() for p in videos)
    if not final:
        raise UltraError(f"Aucune vidéo de {settings.athlete!r} dans {settings.library / 'videos'}. "
                         "Ajouter des MP4 nommés avec le sportif, --video, ou des URLs explicites autorisées.")
    for p in final:
        if not p.is_file():
            raise UltraError(f"Vidéo introuvable : {p}")
    return final, annotations


def _collect_music(args: argparse.Namespace, manifest: dict, settings: Settings,
                   base: Path) -> list[Path]:
    music = [_path(p, base) for p in (args.music or [])]
    music += [_path(p, base) for p in manifest.get("music", [])]
    urls = list(args.music_source or []) + list(manifest.get("music_urls", []))
    if urls:
        if not args.allow_download or not args.rights_confirmed:
            raise UltraError("Téléchargement audio exige --allow-download --rights-confirmed. Les musiques doivent être autorisées.")
        music.extend(download_audio_explicit(urls, settings.library / "downloads" / "music"))
    if not music:
        music = audio_library(settings.library, settings.style)
    return list(dict.fromkeys(music))


def _thumbnail_and_metadata(settings: Settings, edits: list, audio: list[Path]) -> tuple[Path, dict]:
    display = f"{settings.athlete.upper()} | ULTIMATE {settings.sport.upper()} MIX ({settings.style.upper()})"
    title = settings.title or display
    # Prefer an action with a documented peak; no synthetic face/body changes.
    strongest = max((x for x in edits if x.source_peak is not None),
                    key=lambda e: e.confidence, default=edits[0])
    thumbnail = create_thumbnail(strongest, settings.athlete, settings.output / "thumbnail.jpg",
                                 width=settings.width, height=settings.height)
    tags = [settings.athlete, f"{settings.sport} highlights", f"{settings.style} mix",
            "sports edits", "sports music", "full actions", "YouTube Edit Ultra"]
    desc = (f"{settings.athlete} • {settings.sport.capitalize()} highlights • "
            f"{settings.duration_seconds / 60:g} minute music mix\n\n"
            "Music and sports action assembled with YouTube-Edit-Ultra. "
            "Full sports sequences take priority over rapid beat cuts.\n\n"
            "Soundtrack files selected: " + ", ".join(p.stem for p in audio) + "\n\n"
            "Music and footage require the relevant permissions for distribution.\n"
            f"#Sports #Highlights #{slug(settings.athlete).replace('-', '')}")
    meta = {"title": title[:100], "description": desc, "tags": tags,
            "categoryId": "17", "madeForKids": False}
    write_json(settings.output / "youtube_metadata.json", meta)
    return thumbnail, meta


def create(args: argparse.Namespace) -> int:
    manifest_path = Path(args.spec).expanduser().resolve() if args.spec else None
    manifest = load_manifest(manifest_path) if manifest_path else {}
    base = manifest_path.parent if manifest_path else Path.cwd()
    settings = _build_settings(args, manifest, base)
    check_binaries()
    settings.output.mkdir(parents=True, exist_ok=True)
    cache_dir = settings.output / "cache"
    videos, forced_annotations = _collect_videos(args, manifest, settings, base)
    music = _collect_music(args, manifest, settings, base)
    # Preflight duration before spending time scanning sources.
    soundtrack_playlist(music, settings.duration_seconds, allow_repeat=settings.allow_music_repeat)
    print(f"YouTube-Edit-Ultra | {settings.athlete} | {settings.sport} | {settings.style} | {settings.duration_seconds/60:.2f} min")
    print(f"Sources : {len(videos)} vidéos, {len(music)} pistes")
    actions, source_durations, analysis_meta = [], {}, []
    for video in videos:
        info = probe(video)
        if not info["has_video"]:
            raise UltraError(f"Source sans vidéo : {video}")
        source_durations[str(video)] = info["duration"]
        annotation = forced_annotations.get(str(video)) or find_annotation(video, settings.library)
        if annotation:
            parsed = validate_no_overlap(from_json(annotation, video, info["duration"], settings.sport))
            actions.extend(parsed)
            analysis_meta.append({"source": str(video), "annotation": str(annotation),
                                  "events": len(parsed), "semantic_source": "external_annotations"})
            print(f"Annotations: {video.name}, {len(parsed)} actions")
        elif args.strict_actions:
            raise UltraError(f"--strict-actions : annotations absentes pour {video.name}")
        else:
            print(f"Analyse sport (heuristique): {video.name}")
            candidates, stats = analyze(video, cache_dir / "vision", settings.sport,
                                        scene_detect=settings.scene_detect)
            actions.extend(candidates)
            analysis_meta.append(stats)
    if args.semantic_model:
        print(f"Analyse visuelle locale : {args.semantic_model}")
        actions, semantic_logs = enrich(actions, sport=settings.sport, model=args.semantic_model,
                                        cache_dir=cache_dir / "semantic", limit=args.semantic_limit)
        write_json(settings.output / "semantic_analysis.json", semantic_logs)
    if args.dry_run:
        # A beat grid at 100 BPM exercises the planner without rendering music.
        beats = [i * .6 for i in range(int(settings.duration_seconds / .6) + 2)]
        soundtrack = None
    else:
        soundtrack = cache_dir / "soundtrack.m4a"
        chosen = build_soundtrack(music, settings.duration_seconds, soundtrack,
                                  repeat=settings.allow_music_repeat)
        music = chosen
        beats = extract_beats(soundtrack, engine=args.beat_engine)
    print(f"Actions candidates : {len(actions)} | Beats : {len(beats)}")
    edits = plan_edit(actions, beats, settings.duration_seconds, source_durations,
                      allow_repeat=settings.allow_repeat, fps=settings.fps)
    report = integrity_report(edits, actions, settings.duration_seconds)
    write_json(settings.output / "action_integrity_report.json", report)
    write_json(settings.output / "edit_plan.json", [e.as_dict() for e in edits])
    write_json(settings.output / "source_report.json", {
        "inputs": [{"path": str(p), "fingerprint": fingerprint(p)} for p in videos],
        "music": [str(p) for p in music], "analysis": analysis_meta,
        "origin": settings.created_from, "sport": settings.sport, "style": settings.style})
    if args.dry_run:
        print(f"Plan validé, {len(edits)} sections. Rapports : {settings.output}")
        return 0
    result = render_edits(edits, soundtrack, settings.output / "montage.mp4",
                          cache_dir / "segments", width=settings.width,
                          height=settings.height, fps=settings.fps,
                          source_volume=settings.source_volume,
                          music_volume=settings.music_volume)
    thumbnail, metadata = _thumbnail_and_metadata(settings, edits, music)
    storyboard = create_storyboard(edits, settings.output / "storyboard.jpg")
    write_json(settings.output / "render_report.json", result)
    print(f"Vidéo : {result['output']} | miniature : {thumbnail} | storyboard : {storyboard}")
    if settings.publish != "none":
        uploaded = upload(settings.output / "montage.mp4", title=metadata["title"],
                          description=metadata["description"], tags=metadata["tags"],
                          privacy=settings.publish, thumbnail=thumbnail)
        print(f"YouTube : {uploaded['url']} (statut demandé : {settings.publish})")
    return 0


def init(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    for name in ("library/videos", "library/music/hip-hop", "library/music/reggaeton",
                 "library/music/funk-brasileiro", "library/annotations", "output"):
        (root / name).mkdir(parents=True, exist_ok=True)
    print(f"Bibliothèque créée : {root}. Déposer les MP4 et pistes audio avant 'ultra create'.")
    return 0


def doctor(args: argparse.Namespace) -> int:
    for name in ("python", "ffmpeg", "ffprobe", "yt-dlp", "gh"):
        print(f"{name:8s}: {shutil.which('python3' if name == 'python' else name) or 'non installé'}")
    for module in ("numpy", "librosa", "cv2", "scenedetect", "googleapiclient", "yt_dlp"):
        try:
            __import__(module)
            state = "oui"
        except ImportError:
            state = "option non installée"
        print(f"{module:16s}: {state}")
    return 0


def publish(args: argparse.Namespace) -> int:
    video = Path(args.video).expanduser().resolve()
    metadata_file = Path(args.metadata).expanduser().resolve() if args.metadata else video.parent / "youtube_metadata.json"
    meta = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.is_file() else {}
    title = args.title or meta.get("title") or video.stem
    desc = args.description or meta.get("description", "Sports music montage")
    thumb = Path(args.thumbnail) if args.thumbnail else video.parent / "thumbnail.jpg"
    result = upload(video, title=title, description=desc, tags=meta.get("tags", []),
                    privacy=args.privacy, thumbnail=thumb)
    print(result["url"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ultra", description="Sport-first beat-synchronized video editor")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="Préparer les dossiers sources")
    p.add_argument("directory", nargs="?", default=".")
    p.set_defaults(func=init)
    p = sub.add_parser("doctor", help="Afficher les dépendances")
    p.set_defaults(func=doctor)
    p = sub.add_parser("create", help="Fabriquer un mix MP4 et éventuellement le publier")
    p.add_argument("prompt", nargs="?", default="", help="Ex. 'Cristiano Ronaldo 30 minutes hip-hop'")
    p.add_argument("--spec", help="Fichier YAML de projet")
    p.add_argument("--athlete", help="Nom exact du sportif")
    p.add_argument("--sport", choices=["boxing", "football", "mma", "basketball", "generic"])
    p.add_argument("--duration", help="Ex. 30m, 1h15, 90s")
    p.add_argument("--style", help="Sous-dossier de la musique : hip-hop, funk-brasileiro...")
    p.add_argument("--library")
    p.add_argument("--output-dir")
    p.add_argument("--video", action="append", help="Fichier MP4 local (répétable)")
    p.add_argument("--music", action="append", help="MP3/WAV/FLAC local (répétable)")
    p.add_argument("--music-source", action="append", help="URL explicite de musique téléchargeable avec autorisation")
    p.add_argument("--source", action="append", help="URL explicite d'une vidéo réutilisable")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--rights-confirmed", action="store_true")
    p.add_argument("--all-library", action="store_true", help="Inclure tous les clips de library/videos")
    p.add_argument("--strict-actions", action="store_true", help="Exiger des actions annotées")
    p.add_argument("--semantic-model", metavar="MODEL", help="Ollama local, ex. qwen3-vl:2b (aucune API payante)")
    p.add_argument("--semantic-limit", type=int, default=150, help="Nombre de fenêtres envoyées au modèle, 0 = toutes")
    p.add_argument("--scene-detect", action="store_true", help="PySceneDetect complet (plus lent)")
    p.add_argument("--allow-repeat", action="store_true", help="Répéter des actions seulement si choisi")
    p.add_argument("--repeat-music", action="store_true", help="Reboucler la playlist si trop courte")
    p.add_argument("--publish", choices=["none", "private", "unlisted", "public"], default="none")
    p.add_argument("--title", help="Titre YouTube")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--beat-engine", choices=["fast", "librosa"], default="fast",
                   help="fast=FFmpeg+NumPy; librosa=beat tracker plus lent au premier démarrage")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=create)
    p = sub.add_parser("publish", help="Uploader un montage existant")
    p.add_argument("video")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--metadata")
    p.add_argument("--thumbnail")
    p.set_defaults(func=publish)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UltraError, ValueError, FileNotFoundError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
