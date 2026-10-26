"""EDL planner: beat-aware selection, atomic events, no action-internal cuts."""
from __future__ import annotations

import bisect
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from .events import Action
from .media import UltraError


@dataclass(frozen=True)
class Edit:
    source: str
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float
    label: str
    source_peak: float | None
    provenance: str
    confidence: float

    @property
    def duration(self) -> float:
        return self.source_end - self.source_start

    def as_dict(self) -> dict:
        return asdict(self)


def nearest_beat_distance(t: float, beats: list[float]) -> float:
    if not beats:
        return 0.5
    i = bisect.bisect_left(beats, t)
    return min((abs(t - beats[j]) for j in (i - 1, i) if 0 <= j < len(beats)), default=0.5)


def clashes(a: Action, others: list[Edit], margin: float = 0.0) -> bool:
    return any(e.source == a.source and a.start < e.source_end + margin and a.end > e.source_start - margin
               for e in others)


def find_filler(duration: float, source_durations: dict[str, float], actions: list[Action],
                edits: list[Edit], at: float) -> Edit | None:
    """Find neutral non-annotated footage for a very short duration remainder.

    This is not semantically validated as a sports event.
    """
    by_source: dict[str, list[Action]] = defaultdict(list)
    for e in actions:
        by_source[e.source].append(e)
    for source, total in sorted(source_durations.items(), key=lambda it: -it[1]):
        occupied = sorted((e.start, e.end) for e in by_source.get(source, []))
        end = 0.0
        for start, stop in occupied + [(total, total)]:
            if start - end >= duration + 0.2:
                a, b = end + 0.1, end + 0.1 + duration
                if not any(x.source == source and x.source_start < b and a < x.source_end for x in edits):
                    return Edit(source, round(a, 3), round(b, 3), round(at, 3),
                                round(at + duration, 3), "neutral_context", None, "filler", 0.0)
            end = max(end, stop)
    return None


def plan_edit(actions: list[Action], beats: list[float], target: float,
              source_durations: dict[str, float], *, allow_repeat: bool = False,
              fps: int = 30, max_filler: float = 18.0) -> list[Edit]:
    if not actions:
        raise UltraError("Aucune séquence sportive repérée. Fournir des annotations .actions.json ou davantage de vidéos.")
    if fps <= 0:
        raise UltraError("FPS incorrect")
    unique = sorted({(a.source, a.start, a.end, a.peak): a for a in actions}.values(),
                    key=lambda a: (a.source, a.start))
    used: Counter[tuple[str, float, float]] = Counter()
    from_each: Counter[str] = Counter()
    edits: list[Edit] = []
    t = 0.0
    # Every segment is a whole atomic action, never a beat-sized fragment.
    while t < target - 1 / fps:
        remain = target - t
        fit = [a for a in unique if a.duration <= remain + 0.0001
               and (allow_repeat or not used[(a.source, a.start, a.end)])
               and (allow_repeat or not clashes(a, edits, margin=0))]
        if not fit:
            break

        def score(a: Action) -> tuple[float, float, float]:
            # Musical impact, rich action context, variety; never trim action just to fit.
            beat_miss = nearest_beat_distance(t + (a.peak - a.start), beats)
            fairness = from_each[a.source] * 0.07
            repeat_penalty = used[(a.source, a.start, a.end)] * 15
            event_bonus = min(1.0, a.duration / 25.0)
            return (a.confidence * 3.0 + event_bonus - beat_miss * 1.4
                    - fairness - repeat_penalty,
                    a.duration, -a.start)
        picked = max(fit, key=score)
        used[(picked.source, picked.start, picked.end)] += 1
        from_each[picked.source] += 1
        duration = picked.duration
        edits.append(Edit(picked.source, picked.start, picked.end, round(t, 3),
                          round(t + duration, 3), picked.label, picked.peak,
                          picked.provenance, picked.confidence))
        t += duration
        if len(edits) >= 1000:
            raise UltraError("Limite de 1 000 événements dépassée")
    left = target - t
    if left > 0.025:
        if left > max_filler:
            remaining = sum(a.duration for a in unique if not used[(a.source, a.start, a.end)])
            raise UltraError(f"Matière sportive insuffisante : {t / 60:.2f} minutes sélectionnées sur {target / 60:.2f}. "
                             f"Ajouter des sources/actions (non utilisées : {remaining / 60:.1f} min). "
                             "Aucune action ne sera coupée pour atteindre la durée.")
        filler = find_filler(left, source_durations, unique, edits, t)
        if filler is None:
            raise UltraError(f"Impossible de combler les {left:.2f} dernières secondes sans couper une action ; "
                             "fournir davantage de plans de contexte ou modifier la durée.")
        edits.append(filler)
    return edits


def integrity_report(edits: list[Edit], actions: list[Action], target: float) -> dict:
    protected = {(a.source, a.start, a.end): a for a in actions}
    failures = []
    for e in edits:
        if e.provenance == "filler":
            continue
        if (e.source, e.source_start, e.source_end) not in protected:
            failures.append(e.as_dict())
    annotation_count = sum(1 for e in edits if e.provenance in {"annotation", "SoccerNet"})
    heuristic_count = sum(1 for e in edits if e.provenance.startswith("heuristic"))
    return {
        "requested_seconds": target,
        "assembled_seconds": round(edits[-1].timeline_end, 3) if edits else 0,
        "events_total": len(actions), "events_selected": len(edits) - sum(e.provenance == "filler" for e in edits),
        "annotation_or_model_events_selected": annotation_count,
        "heuristic_candidates_selected": heuristic_count,
        "cuts_inside_selected_event_windows": len(failures),
        "all_selected_event_windows_preserved": len(failures) == 0,
        "semantic_completeness_guaranteed": False,
        "reason_semantic_limit": "Même une fenêtre conservée entière peut manquer le début/fin réels de l'action si la détection est heuristique ou les annotations sont incorrectes.",
        "filler_segments": sum(e.provenance == "filler" for e in edits),
        "violations": failures,
    }
