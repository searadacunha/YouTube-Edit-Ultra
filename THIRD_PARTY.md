# Third-party components and license compliance

This repository contains **original implementation code**; it does **not** vendor, relicense, or copy the source of unrelated editor repositories.

It integrates external programs/libraries via their public CLI/API under their own licenses. Copyright notices and license terms of installed dependencies continue to apply. In particular, merely renaming other people's code would not remove license obligations.

## Direct integrations

- [FFmpeg](https://ffmpeg.org/) — LGPL/GPL according to build, installed separately; FFprobe included.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Unlicense core; distributed builds may include third-party copyleft software. Optional explicit URL downloads.
- [librosa](https://github.com/librosa/librosa) — ISC license; beat analysis.
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) — BSD-3-Clause; optional shot detection.
- [OpenCV](https://github.com/opencv/opencv) — Apache-2.0, via opencv-python-headless; available for future detectors.
- [Pillow](https://github.com/python-pillow/Pillow) — HPND; source-derived thumbnail.
- [NumPy](https://github.com/numpy/numpy) — BSD-3-Clause; numerical processing.
- [PyYAML](https://github.com/yaml/pyyaml) — MIT; configuration.
- [Ollama](https://github.com/ollama/ollama) + [Qwen3-VL model](https://ollama.com/library/qwen3-vl) — optional local inference; Ollama and models carry separate terms.
- [YouTube Data API](https://developers.google.com/youtube/v3) + Google API Python libraries — YouTube publishing under Google's developer terms and OAuth.

## Relevant public editing / spotting research (not copied into this codebase)

- [DisaterPeace/cadence](https://github.com/DisaterPeace/cadence) — AGPL-3.0. Beat-synced person-focused music editing.
- [Merserk/BeatSync-Engine](https://github.com/Merserk/BeatSync-Engine) — AGPL-3.0. Audio-visual beats/scene analysis; Windows-first portable implementation.
- [ZiadAbdelkarim/beat-synced-edit](https://github.com/ZiadAbdelkarim/beat-synced-edit) — MIT. Python/FFmpeg/Claude Code workflow for beat maps and clip selection.
- [nicholsbw77/Auto-action-video-editor](https://github.com/nicholsbw77/Auto-action-video-editor) — automated beat-aligned montage GUI; license must be checked before code reuse.
- [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) — Unlicense core; audio/motion-based editing.
- [SoccerNet/sn-spotting](https://github.com/SoccerNet/sn-spotting) — external pretrained football event spotting benchmark. We accept exported predictions; no model code/weights/data is bundled.
- [roboflow/supervision](https://github.com/roboflow/supervision) — MIT; optional future object tracking integration. Not imported by this release.

You may install and compose compatible packages as permitted by their licenses. If distributing modified AGPL source from another project, retain the appropriate copyright, notices and AGPL obligations rather than removing attribution.

The linked YouTube inspiration thumbnails, soundtrack tracks and sports footage remain with their respective rights holders. They are not part of this repo's MIT grant.
