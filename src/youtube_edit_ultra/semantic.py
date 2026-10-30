"""Optional on-device sports visual tagging via Ollama's Qwen3-VL.

This is a ranking aid, NOT an authenticated action spotter: a few stills
cannot prove a goal, identify a player or guarantee full buildup/follow-through.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .events import Action
from .catalogue import save, sha256
from .media import UltraError


def _validate_response(info: dict) -> dict:
    if not isinstance(info, dict):
        raise UltraError("Réponse du modèle visuel invalide : objet JSON attendu")
    intensity = info.get("intensity")
    if (type(intensity) not in (int, float) or not math.isfinite(intensity) or
            not 0 <= intensity <= 1):
        raise UltraError("Réponse du modèle visuel invalide : intensity doit être un nombre fini entre 0 et 1")
    for field in ("sports_action_visible", "is_crowd_or_graphics_only",
                  "complete_action_visible_in_these_frames"):
        if type(info.get(field)) is not bool:
            raise UltraError(f"Réponse du modèle visuel invalide : {field} doit être booléen")
    if not isinstance(info.get("event_label"), str) or not info["event_label"].strip():
        raise UltraError("Réponse du modèle visuel invalide : event_label doit être du texte")
    return info


def _frame_base64(source: str, at: float) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}",
           "-i", source, "-frames:v", "1", "-vf",
           "scale=384:-2:force_original_aspect_ratio=decrease",
           "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    cp = subprocess.run(cmd, capture_output=True, check=False)
    if cp.returncode or not cp.stdout:
        raise UltraError(f"Extraction image impossible : {source} à {at}s")
    return base64.b64encode(cp.stdout).decode("ascii")


def _ask_ollama(images: list[str], sport: str, model: str) -> dict:
    description = ("football dribble, pass, shot, goal, save, buildup, celebration"
                   if sport == "football" else
                   "boxing punches, defensive exchanges, combinations, knockdown, referee reaction")
    prompt = (f"You review three ordered frames START/MIDDLE/END from a {sport} sports clip. "
              f"Look for {description}. Do not try to identify any real person. "
              "Distinguish live action from crowd shots, replay animations, titles and stills. "
              "Use the three frames only; do NOT invent unseen action. Reply ONLY JSON: "
              '{"sports_action_visible": true, "intensity": 0.5, "event_label": "play", '
              '"is_crowd_or_graphics_only": false, "complete_action_visible_in_these_frames": false}. '
              "intensity 0..1. If uncertain, say uncertain with low intensity.")
    req = Request("http://127.0.0.1:11434/api/generate",
                  data=json.dumps({"model": model, "prompt": prompt, "images": images,
                                   "stream": False, "format": "json",
                                   "options": {"temperature": 0.0, "num_predict": 150}}).encode(),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=300) as resp:
            raw = json.loads(resp.read())
    except (URLError, TimeoutError) as exc:
        raise UltraError("Ollama indisponible (serveur local 127.0.0.1:11434). Installer Ollama, "
                         f"exécuter 'ollama pull {model}', puis relancer.") from exc
    except (ValueError, TypeError) as exc:
        raise UltraError("Enveloppe JSON du modèle visuel invalide") from exc
    try:
        if not isinstance(raw, dict):
            raise ValueError("objet JSON attendu")
        response = json.loads(raw.get("response", "{}"))
    except (ValueError, TypeError) as exc:
        raise UltraError("Réponse JSON du modèle visuel invalide") from exc
    return _validate_response(response)


def enrich(actions: list[Action], *, sport: str, model: str, cache_dir: Path,
           limit: int = 150) -> tuple[list[Action], list[dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    result, logs = [], []
    sources = {}
    count = 0
    for action in actions:
        if action.provenance not in {"heuristic", "heuristic_vlm"} or (limit > 0 and count >= limit):
            result.append(action)
            continue
        count += 1
        source = Path(action.source).resolve()
        stat = source.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if str(source) not in sources:
            sources[str(source)] = (signature, sha256(source))
        original, digest = sources[str(source)]
        if original != signature:
            raise UltraError(f"Source modifiée pendant l'analyse visuelle : {source}")
        binding = {"version": 2, "source": str(source), "sha256": digest,
                   "start": action.start, "peak": action.peak, "end": action.end,
                   "sport": sport, "model": model, "frame_width": 384}
        key = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
        cache = cache_dir / f"vlm-{key}.json"
        if cache.is_file():
            try:
                payload = json.loads(cache.read_text())
                if not isinstance(payload, dict) or payload.get("binding") != binding:
                    raise ValueError("source ou paramètres différents")
                info = _validate_response(payload["response"])
            except (OSError, ValueError, TypeError, KeyError, UltraError) as exc:
                raise UltraError(f"Cache du modèle visuel invalide : {cache}: {exc}") from exc
        else:
            times = [action.start + min(2.0, action.duration * .16), action.peak,
                     action.end - min(2.0, action.duration * .16)]
            images = [_frame_base64(action.source, t) for t in times]
            try:
                info = _validate_response(_ask_ollama(images, sport, model))
            except UltraError as exc:
                raise UltraError(f"{exc} — {source} à {action.peak:.3f}s") from exc
        after = source.stat()
        if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != original:
            raise UltraError(f"Source modifiée pendant l'analyse visuelle : {source}")
        if not cache.is_file():
            save(cache, {"binding": binding, "response": info})
        intensity = info["intensity"]
        visible = info["sports_action_visible"]
        graphics = info["is_crowd_or_graphics_only"]
        confidence = max(0.08, min(0.80, (0.35 + intensity * 0.4) if visible and not graphics else 0.1))
        label = info["event_label"][:80]
        result.append(Action(action.source, action.start, action.peak, action.end,
                             action.sport, label, confidence, "heuristic_vlm"))
        logs.append({"source": action.source, "peak": action.peak,
                     "model": model, "response": info})
    return result, logs
