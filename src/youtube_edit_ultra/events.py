"""Sport-specific atomic action windows and honest event provenance."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .media import UltraError
from .spec import SPORT_PRESETS


@dataclass(frozen=True)
class Action:
    source: str
    start: float
    peak: float
    end: float
    sport: str = "generic"
    label: str = "action"
    confidence: float = 0.2
    provenance: str = "heuristic"  # annotation / SoccerNet / heuristic

    @property
    def duration(self) -> float:
        return self.end - self.start

    def as_dict(self) -> dict:
        return asdict(self)


def make_action(source: Path, start: float, peak: float, end: float, duration: float,
                sport: str, label: str, confidence: float = 0.9,
                provenance: str = "annotation", padding: float = 0.5) -> Action:
    start = max(0.0, float(start) - padding)
    end = min(duration, float(end) + padding)
    peak = float(peak)
    if not 0 <= start <= peak <= end <= duration + 0.001 or end - start < 0.15:
        raise UltraError(f"Action incohérente ({source.name}): {start}-{peak}-{end} / {duration}")
    return Action(str(source.resolve()), round(start, 3), round(peak, 3), round(end, 3),
                  sport, label, min(max(float(confidence), 0), 1), provenance)


def from_json(path: Path, source: Path, duration: float, sport: str) -> list[Action]:
    """Supported: {events:[{start,peak,end,label}]} or SoccerNet predictions."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = data.get("events", data.get("predictions", []))
    elif isinstance(data, list):
        items = data
    else:
        raise UltraError(f"Format annotations non reconnu: {path}")
    if not isinstance(items, list):
        raise UltraError(f"'events' doit être une liste: {path}")
    result = []
    for e in items:
        if not isinstance(e, dict):
            continue
        if "position" in e and "start" not in e:
            # SoccerNet output: position is in milliseconds relative to half.
            peak = float(e["position"]) / 1000
            if str(e.get("half", "1")) == "2" or str(e.get("gameTime", "")).startswith("2 -"):
                # Caller must supply source timing offsets for combined full matches.
                peak += float(e.get("half_offset", 0.0))
            pre = SPORT_PRESETS[sport]["lead"]
            post = SPORT_PRESETS[sport]["trail"]
            result.append(make_action(source, max(0, peak - pre), peak,
                        min(duration, peak + post), duration, sport, str(e.get("label", "event")),
                        float(e.get("confidence", 0.65)), "SoccerNet", padding=0))
        else:
            start = float(e.get("start", e.get("start_time", 0)))
            end = float(e.get("end", e.get("end_time", 0)))
            peak = float(e.get("peak", (start + end) / 2))
            result.append(make_action(source, start, peak, end, duration, sport,
                                     str(e.get("label", "action")),
                                     float(e.get("confidence", 1.0)), "annotation"))
    return result


def validate_no_overlap(actions: Iterable[Action], *, max_span: float = float("inf")) -> list[Action]:
    """If two action windows overlap, merge them rather than cutting a combination."""
    grouped: dict[str, list[Action]] = {}
    for action in actions:
        grouped.setdefault(action.source, []).append(action)
    merged = []
    for _, events in grouped.items():
        events.sort(key=lambda e: e.start)
        for action in events:
            if (not merged or merged[-1].source != action.source or
                action.start > merged[-1].end + 0.05 or
                action.end - merged[-1].start > max_span):
                merged.append(action)
                continue
            prev = merged.pop()
            stronger = action if action.confidence > prev.confidence else prev
            merged.append(Action(prev.source, prev.start, stronger.peak,
                                 max(prev.end, action.end), prev.sport,
                                 "+".join(dict.fromkeys([prev.label, action.label])),
                                 max(prev.confidence, action.confidence),
                                 "annotation" if "annotation" in {prev.provenance, action.provenance}
                                 else prev.provenance))
    return merged


def find_annotation(source: Path, library: Path) -> Path | None:
    choices = [source.with_suffix(".actions.json"),
               library / "annotations" / (source.stem + ".json"),
               library / "annotations" / (source.stem + ".actions.json")]
    return next((x for x in choices if x.is_file()), None)
