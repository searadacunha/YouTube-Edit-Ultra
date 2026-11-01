#!/usr/bin/env python3
"""Offline metrics for HUMAN-ANNOTATED event windows and declared prediction sources.

This does not identify a goal/KO or assert footage rights. The caller provides
labels and predictions; matching is deterministic greedy 1:1 IoU.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

METHODS = ("heuristic", "vlm", "annotation")


def validate_windows(rows: object, location: str) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError(f"{location}: expected list of event windows")
    cleaned = []
    for i, entry in enumerate(rows):
        if not isinstance(entry, dict):
            raise ValueError(f"{location}[{i}]: expected object")
        start, end = entry.get("start"), entry.get("end")
        if (type(start) not in (int, float) or type(end) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(end)
                or not 0 <= start < end):
            raise ValueError(f"{location}[{i}]: invalid time window")
        label = entry.get("label")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise ValueError(f"{location}[{i}]: invalid event label")
        cleaned.append({"start": float(start), "end": float(end),
                        "label": label.strip() if label else None})
    return cleaned


def read_cases(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
        raise ValueError("Expected an object with cases array")
    if not document["cases"]:
        raise ValueError("Dataset has no evaluation cases")
    parsed = []
    for i, case in enumerate(document["cases"]):
        if not isinstance(case, dict):
            raise ValueError(f"Case {i}: expected object")
        if not isinstance(case.get("source_id"), str) or not case["source_id"].strip():
            raise ValueError(f"Case {i}: source_id is required")
        # Rights are stated by the submitter, not verified by the evaluator.
        if not isinstance(case.get("rights"), str) or not case["rights"].strip():
            raise ValueError(f"Case {i}: rights/provenance statement required")
        predictions = case.get("predictions")
        if not isinstance(predictions, dict) or not predictions:
            raise ValueError(f"Case {i}: predictions must name at least one method")
        if set(predictions) - set(METHODS):
            raise ValueError(f"Case {i}: unknown prediction method")
        parsed.append({
            "source_id": case["source_id"],
            "rights": case["rights"],
            "truth": validate_windows(case.get("truth"), f"case {i}.truth"),
            "predictions": {name: validate_windows(rows, f"case {i}.{name}")
                            for name, rows in predictions.items()},
        })
    return parsed


def iou(a: dict, b: dict) -> float:
    overlap = max(0., min(a["end"], b["end"]) - max(a["start"], b["start"]))
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return overlap / union if union > 0 else 0.0


def greedy_matches(truth: list[dict], predicted: list[dict], threshold: float) -> list[tuple[int, int]]:
    candidates = sorted(
        ((iou(a, b), i, j) for i, a in enumerate(truth)
         for j, b in enumerate(predicted) if iou(a, b) >= threshold),
        key=lambda item: (-item[0], item[1], item[2]))
    taken_t, taken_p, matches = set(), set(), []
    for _, i, j in candidates:
        if i not in taken_t and j not in taken_p:
            matches.append((i, j))
            taken_t.add(i)
            taken_p.add(j)
    return matches


def evaluate(cases: list[dict], threshold: float = 0.5) -> dict:
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("IoU threshold must be within (0, 1]")
    result = {"iou_threshold": threshold,
              "matching": "greedy one-to-one; independent of labels",
              "source_rights_independently_verified": False,
              "methods": {}}
    for method in METHODS:
        truth_n = pred_n = tp = labels_compared = labels_correct = 0
        start_errors, end_errors = [], []
        covered = 0
        for case in cases:
            if method not in case["predictions"]:
                continue  # Missing predictions are NOT treated as a zero-performing method.
            covered += 1
            truth, predictions = case["truth"], case["predictions"][method]
            truth_n += len(truth)
            pred_n += len(predictions)
            matches = greedy_matches(truth, predictions, threshold)
            tp += len(matches)
            for i, j in matches:
                t, p = truth[i], predictions[j]
                start_errors.append(abs(t["start"] - p["start"]))
                end_errors.append(abs(t["end"] - p["end"]))
                if t["label"] is not None and p["label"] is not None:
                    labels_compared += 1
                    labels_correct += t["label"] == p["label"]
        if not covered:
            continue
        fp, fn = pred_n - tp, truth_n - tp
        result["methods"][method] = {
            "cases_evaluated": covered, "truth_events": truth_n,
            "predicted_events": pred_n, "true_positive_windows": tp,
            "false_positive_windows": fp, "false_negative_windows": fn,
            "precision": tp / pred_n if pred_n else None,
            "recall": tp / truth_n if truth_n else None,
            "false_positive_fraction": fp / pred_n if pred_n else None,
            "mean_abs_start_error_seconds": statistics.mean(start_errors) if start_errors else None,
            "mean_abs_end_error_seconds": statistics.mean(end_errors) if end_errors else None,
            "label_comparisons": labels_compared,
            "label_accuracy_given_matched_and_labelled":
                labels_correct / labels_compared if labels_compared else None,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    report = json.dumps(evaluate(read_cases(options.dataset), options.iou),
                        indent=2, sort_keys=True) + "\n"
    if options.output:
        options.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
