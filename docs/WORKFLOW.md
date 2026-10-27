# Technical workflow

1. `ultra create` parses a natural-language prompt, manifest and explicit options.
2. Finds local athlete files in `library/videos`, or accepts local `--video` and rights-cleared explicit `--source` URLs.
3. Picks the soundtrack from the matching local music genre, validates that enough music exists and crossfades tracks to the target duration.
4. If `library/annotations/<video>.json` is present, loads protected actions and skips expensive heuristics for that source. Otherwise, FFmpeg subsamples to 192×108, 2fps, computes frame motion peaks and camera cuts and gives candidates sport-dependent lead/trail windows.
5. Optional `--scene-detect` runs PySceneDetect; optional `--semantic-model qwen3-vl:2b` sends three stills per candidate to a local Ollama process, ranking graphics/crowds separately from sports movements.
6. Detects musical transients with FFmpeg/NumPy by default (`--beat-engine librosa` opts into beat tracking), then chooses whole events whose impact times approximately fit that rhythm. Repeats are off by default. Missing footage is an error, not grounds for inventing events.
7. Renders each selected event as a complete clip through FFmpeg, preserving 1× movement and audio. Caches clips by source fingerprint, crop settings and time range. Concatenates segments and mixes original sound beneath the soundtrack.
8. Creates a source-derived JPEG thumbnail, sports YouTube metadata, exact cut EDL, source audit and action-integrity report.
9. A separate OAuth YouTube upload step runs only with `--publish ...` or `ultra publish ...`.

## Action JSON schema

```json
{
  "events": [
    {"start": 10.2, "peak": 17.5, "end": 29.8, "label": "lead-dribble-shot-goal-celebration", "confidence": 1.0}
  ]
}
```

The source reference is taken from the annotation filename / manifest mapping. Times are seconds from the beginning of the source video. The imported event is slightly padded to reduce boundary loss.

## SoccerNet-style predictions

```json
{
  "predictions": [
    {"position": 180000, "label": "Goal", "confidence": 0.93}
  ]
}
```

`position` is milliseconds. In combined multi-half sources, provide `half_offset` for second-half timestamps. The pretrained model is **not included**; your inference system must produce these predictions and you must satisfy the model/dataset license.

## Local files and authorization

The code does not search or crawl social platforms without specified URLs. You can keep an ongoing curated catalog of your licensed boxing bouts and football sequences in `library/videos`. If you want the simple athlete/style/duration experience, filenames should match the athlete. If you have authorized music, place it by genre under `library/music/`.

## Resources

- FFmpeg / FFprobe: mux, crop/scale, normalize and render
- librosa: analyze beats at lower audio sampling rate
- PySceneDetect: optional full cut detector
- Ollama / Qwen3-VL: optional on-device visual rankings; approximate, not an athlete-specific tracker
- SoccerNet: support for **importing** specialist action-spotting predictions (external inference)
- yt-dlp: explicit video URLs with authorization
- YouTube Data API: OAuth publishing

## Recommended validation before public upload

Watch a sample of clips at every `edit_plan.json` boundary and flag any missing lead-in/end. Confirm music license and original sports footage clearance. `ultra publish` does not bypass YouTube Content ID checks. If the requested 30 minutes cannot be populated with full actions, obtain more source footage rather than chopping goals into sub-second transitions.
