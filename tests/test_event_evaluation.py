"""Window metrics are synthetic unit tests, not sports-event performance results."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/evaluate_event_detection.py"
spec = importlib.util.spec_from_file_location("event_evaluation", PATH)
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


def test_one_to_one_matching_and_boundary_errors():
    cases = [{"source_id": "synthetic", "rights": "generated fixture",
              "truth": [{"start": 1., "end": 3., "label": "goal"}],
              "predictions": {
                  "heuristic": [{"start": 1.1, "end": 3.1, "label": "motion"},
                                {"start": 1.1, "end": 3.1, "label": "motion"}],
                  "vlm": [{"start": 10., "end": 12., "label": "goal"}]}}]
    result = evaluator.evaluate(cases)
    heuristic = result["methods"]["heuristic"]
    assert (heuristic["true_positive_windows"], heuristic["false_positive_windows"],
            heuristic["false_negative_windows"]) == (1, 1, 0)
    assert heuristic["precision"] == pytest.approx(0.5)
    assert heuristic["recall"] == pytest.approx(1)
    assert heuristic["mean_abs_start_error_seconds"] == pytest.approx(0.1)
    assert heuristic["label_accuracy_given_matched_and_labelled"] == 0
    assert result["methods"]["vlm"]["precision"] == 0
    assert "annotation" not in result["methods"]


def test_missing_method_not_counted_as_zero_and_empty_predictions_expose_undefined_precision():
    cases = [
        {"truth": [{"start": 1., "end": 2.}], "predictions": {"heuristic": []}},
        {"truth": [{"start": 1., "end": 2.}], "predictions": {"vlm": []}},
    ]
    result = evaluator.evaluate(cases)
    assert result["methods"]["heuristic"]["cases_evaluated"] == 1
    assert result["methods"]["vlm"]["cases_evaluated"] == 1
    assert result["methods"]["heuristic"]["precision"] is None
    assert result["methods"]["heuristic"]["recall"] == 0


def test_reject_bad_annotation_and_unsupported_methods(tmp_path):
    data = {"cases": [{"source_id": "x", "rights": "original test fixture",
                       "truth": [{"start": 2., "end": 1.}],
                       "predictions": {"heuristic": []}}]}
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid time window"):
        evaluator.read_cases(path)
    data["cases"][0]["truth"] = []
    data["cases"][0]["predictions"] = {"oracle": []}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown prediction method"):
        evaluator.read_cases(path)
