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

## Documentary mode (`ueu documentary`, added 31/10/2026)

Installed and actually used, each in the isolated `.venv-doc` (Python 3.12) except pysubs2, which the main package imports:

- [mlx-audio](https://github.com/Blaizzy/mlx-audio) 0.6.3 — MIT; Apple-Silicon TTS runtime (MLX 0.32.4).
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) weights `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit` (deleted after creating one synthetic reference voice) and `…-1.7B-Base-4bit` — Apache-2.0. The narrator is either a voice designed from a text description or a real person's voice cloned from their own recording with their consent (recorded in the spec's `voice.credit` and disclosed on upload with `synthetic_media`). Its speaker embeddings also serve the resemblance check and `diarize`.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 1.2.1 — MIT, with `Systran/faster-whisper-small` (MIT); word timestamps and spoken-number checks. Audio is decoded by FFmpeg because its PyAV path fails with PyAV 17+.
- [pysubs2](https://github.com/tkarabela/pysubs2) 1.9.1 — MIT; ASS/SRT export (Python 3.12 here, satisfying recent versions).
- Mixkit music under the Mixkit Stock Music Free License (YouTube videos allowed; no re-registration on rights-management services); licence page saved with the project.

Evaluated, **not installed**: [whisperX](https://github.com/m-bain/whisperX) (BSD-2-Clause; its French wav2vec2 aligner is ~1.2 GB, impossible under the 12 GB floor; faster-whisper word timings aligned to the known script were enough), [chatterbox](https://github.com/resemble-ai/chatterbox) (MIT; needs a reference recording of a real voice for French), [mmpose](https://github.com/open-mmlab/mmpose) (Apache-2.0; mmcv build — rtmlib/RTMW already on this Mac was kept as the lighter option and was not needed), [Boxing_Tracking_Project](https://github.com/Bohdanvtk/Boxing_Tracking_Project) and [combat-sport-analyser](https://github.com/akhellad/combat-sport-analyser) (**no licence**: code not reusable; the latter also depends on AGPL Ultralytics), [boxe.ml](https://github.com/leonardosm14/boxe.ml) (MIT but YOLOv8/AGPL + TensorFlow, experimental), [boxing-fight-video-analysis](https://github.com/piotr-stefanski/boxing-fight-video-analysis) (MIT; fixed overhead Olympic cameras, not broadcast footage). BoxComm (arXiv 2604.04419) informed the split between descriptive, tactical and contextual narration; its dataset was not downloaded.

You may install and compose compatible packages as permitted by their licenses. If distributing modified AGPL source from another project, retain the appropriate copyright, notices and AGPL obligations rather than removing attribution.

The linked YouTube inspiration thumbnails, soundtrack tracks and sports footage remain with their respective rights holders. They are not part of this repo's MIT grant.
