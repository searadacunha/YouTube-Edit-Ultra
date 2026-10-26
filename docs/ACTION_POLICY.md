# Action-integrity policy

The central invariant is **a cut never lands inside a selected protected action window**.

## Sport-specific context

| Sport | Before impact | After impact | What to retain |
|---|---:|---:|---|
| Football | 11 seconds | 15 seconds | buildup, feint, run, dribble, shot, save/goal, immediate celebration |
| Boxing | 7 seconds | 8 seconds | entry, combination, knockdown/referee decision/follow-through |
| MMA | 8 seconds | 12 seconds | setup, strike/takedown, continuation and referee action |
| Basketball | 6 seconds | 9 seconds | transition, pass, shot, basket, aftermath |

These offsets apply to a detected peak, not to an already marked entire event. They are **conservative heuristics**, not guarantees. Real clips may require more context; import explicit event boundaries whenever possible.

## Three reliability levels

1. **Manual ground truth** (`.actions.json`): exact user-supplied start/peak/end. The renderer must keep the interval intact, barring an incorrect annotation.
2. **SoccerNet-style action spotting** (`predictions` with timestamp): a pretrained specialist model's impact time plus protective sport windows. Accuracy depends on training/domain; exact full sequence is not established merely by a timestamp.
3. **Automatic motion with optional Qwen3-VL**: candidate action bursts with broad protection. False positives from camera cuts, replays and celebrations are possible. Semantic action completeness is not guaranteed.

## Hard rules

- Never cut an event in half to sync music. Beat sync scores the **impact time** after preserving the whole action.
- Never delete the aftermath of a knockout or a shot because the musical phrase ends.
- No silent repeat of goals, combinations or insertion clips. `--allow-repeat` is opt-in.
- Do not accelerate/speed-ramp the action at default settings: render at source-normal 1×.
- Do not apply face/body stylization or image synthesis to actual athletes.
- Keep original commentary/arena audio as a low layer under music.
- Publish only if explicitly requested; render works offline after the source library exists.

## Validation and reporting

`action_integrity_report.json` checks that each selected event's recorded source start/end matches exactly the planned source window, and counts filler and heuristic candidates. This is an **EDL-internal integrity check**, not proof that all real-world sports actions were found or that annotations are objectively complete.

A production-grade validation campaign would require a hold-out set of manually labeled football and boxing videos, temporal IoU for starts/ends, sporting-event recall/precision and a review of the final MP4 at every action boundary. None of those benchmarks are fabricated in this repo.
