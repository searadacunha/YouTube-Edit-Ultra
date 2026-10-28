# Measuring sports-event detection (evaluation harness, NOT a sports benchmark)

The included media test creates its own synthetic FFmpeg video. It is legally
self-generated and tests decoding, rendering, duration and full-window
preservation, **not** whether the system recognizes authentic boxing or football
events. No labelled real-world action corpus or quality claim is published yet.

`scripts/evaluate_event_detection.py` accepts independent human annotations and
the predictions for the same clips, grouped by source: `heuristic`, `vlm`,
and `annotation`. Annotations are treated as a separate source, never as proof
that the algorithm independently detected an event.

### JSON dataset schema

```json
{
  "cases": [
    {
      "source_id": "clip-001",
      "rights": "Original footage or verifiable license/citation",
      "truth": [{"start": 1.0, "end": 4.0, "label": "goal"}],
      "predictions": {
        "heuristic": [{"start": 1.1, "end": 3.9, "label": "motion_candidate"}],
        "vlm": [{"start": 1.3, "end": 4.1, "label": "goal"}]
      }
    }
  ]
}
```

The example is **illustrative**; no video or result is claimed for clip-001.
Record the source URL, license version, attribution and the rights to distribute
the test segments. Independently check those rights before publishing actual
media. Two human reviewers should annotate the start/end of each action without
seeing predictions, then adjudicate disagreements.

Run:

```sh
python scripts/evaluate_event_detection.py /path/to/licensed-corpus.json --iou 0.5
```

Metrics are window-level precision, recall, false positives, false negatives,
absolute boundary errors and label accuracy **conditional on already matched
labelled windows**. Matching uses deterministic **maximum-cardinality** one-to-one IoU assignment:
it finds the largest possible number of qualified window matches, even when
choosing the highest-overlap pair first would block another valid match.
Within a maximum-size matching, it does not optimize the sum of IoU scores.
This is an evaluation-only correction and does not alter the event detector. The code does not infer that a goal or KO
truly happened and cannot verify legal permissions. A missing method is omitted
from the report, not scored as a failure. An empty prediction list yields an
undefined precision (`null`), not an invented success rate.

### Still unverified

- No independent real-sports footage corpus is currently committed.
- No measured precision/recall for boxing or football action spotting.
- No real-video before/after runtime or semantic-quality comparison.
- No model calibration, cross-camera validation, or blinded human evaluation.

Those gaps must remain explicit until actual annotated footage and evaluation
records exist. Unit-test outcomes are not representative event-detection scores.
