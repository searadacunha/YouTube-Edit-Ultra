"""Optional on-device sports visual tagging via Ollama's Qwen3-VL.

This is a ranking aid, NOT an authenticated action spotter: a few stills
cannot prove a goal, identify a player or guarantee full buildup/follow-through.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .events import Action
from .media import UltraError, fingerprint


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
    try:
        response = json.loads(raw.get("response", "{}"))
    except (ValueError, TypeError) as exc:
        raise UltraError("Réponse JSON du modèle visuel invalide") from exc
    return response


def enrich(actions: list[Action], *, sport: str, model: str, cache_dir: Path,
           limit: int = 150) -> tuple[list[Action], list[dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    result, logs = [], []
    count = 0
    for action in actions:
        if action.provenance not in {"heuristic", "heuristic_vlm"} or (limit > 0 and count >= limit):
            result.append(action)
            continue
        count += 1
        key = hashlib.sha256(f"{fingerprint(Path(action.source))}:{action.start}:{action.peak}:{action.end}:{model}".encode()).hexdigest()[:24]
        cache = cache_dir / f"vlm-{key}.json"
        if cache.is_file():
            info = json.loads(cache.read_text())
        else:
            times = [action.start + min(2.0, action.duration * .16), action.peak,
                     action.end - min(2.0, action.duration * .16)]
            images = [_frame_base64(action.source, t) for t in times]
            info = _ask_ollama(images, sport, model)
            cache.write_text(json.dumps(info, indent=2), encoding="utf-8")
        raw_intensity = info.get("intensity", 0.0)
        try:
            intensity = min(1.0, max(0.0, float(raw_intensity)))
        except (ValueError, TypeError):
            intensity = 0.0
        visible = info.get("sports_action_visible", False) is True
        graphics = info.get("is_crowd_or_graphics_only", False) is True
        confidence = max(0.08, min(0.80, (0.35 + intensity * 0.4) if visible and not graphics else 0.1))
        label = str(info.get("event_label") or action.label)[:80]
        result.append(Action(action.source, action.start, action.peak, action.end,
                             action.sport, label, confidence, "heuristic_vlm"))
        logs.append({"source": action.source, "peak": action.peak,
                     "model": model, "response": info})
    return result, logs
