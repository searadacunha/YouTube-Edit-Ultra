# Documentary mode — `ueu documentary --spec projects/<name>.yaml`

Narrated analysis films (12-16 min) built from an evidence-bound spec, reusing the job checkpoints, disk floor and `finalize_output` of the montage pipeline. `ueu create`, `ultra` and their outputs are unchanged.

## Spec
- `chapters[].blocks[]`: `text` (displayed subtitles), optional `say` (spelling sent to the voice: numbers, acronyms, names), `claims` (`verified_fact` with `facts` ids, `technical_interpretation`, `prediction`, `rhetorical_hook`; `unverified_claim` is never narrated), `visuals`.
- Visual types: `clip` (`src`, `t` = seconds in the original upload, optional `speed`, `zoom`, `overlays`, `audio`, `subs: top`), `freeze` (`at`), `card` (`title`, `chapter`, `stat`, `table`, `compare`, `quote`), `split` (`left`/`right`). Every footage visual needs `action`, `confidence` and an honest `provenance`: `agent_frame_review` means sampled frames seen by an agent; `visual_review`/`human_review` are refused.
- Film keys: `description`, chapter `title` (YouTube chapters), `voice.credit` (voice-over disclosure line), `names.final` (default `documentary.mp4`), `rights: {decided_by, decided_on, note}` (who claims fair use for the footage, and when; required to build `sources_report.json`). Nothing film-specific lives in the engine.
- A block lasts `lead + voice + breathe`; clips are never shortened or sped up, only cards/freezes without `duration` stretch. A missing visual is an error, not a silent loop.

## Steps (resumable)
`sources` (uploader metadata → `sources_report.json`, rights = claim, never licence) → `voice` (Qwen3-TTS Base cloning `voice.ref_audio`: a VoiceDesign voice, or a consented recording; `ref_text: null` = x-vector, timbre only, safer across languages; `scripts/doc_voice.py` in `.venv-doc`) → `align` (faster-whisper word times mapped on the script) → plan, ASS/SRT, `evidence_ledger.json`, `script_fr.md`, `youtube_metadata.md` → HD windows (`--download-sections`, each matched to the reviewed 144p proxy by motion correlation, refused under r = 0.5) → `--preview START SECONDS` test → full render (one rawvideo pipe into x264 + one FLAC mix: voice −17 dBFS, music −14 dB under speech, ambience ducked, −16 LUFS, limiter) → `finalize_output` (full decode, black/freeze/silence, true peak ≤ −1 dBTP) → `quality_report.json`.

## Voice tools (`.venv-doc/bin/python -I scripts/doc_voice.py …`)
- `diarize --audio interview.m4a --lang fr --output diar.json`: two-speaker split by Qwen3 speaker embeddings, to cut a clean reference of one voice. Clusters are not identities: listen before choosing.
- `qc --jobs jobs.json --ref ref.m4a:133.9-151 --other ref.m4a:14.8-31.7 --output qc.json`: per block, ASR match (Whisper `small` by default: `base` misheard Spanish numbers), negations in the script vs heard (fr/en/es/pt), resemblance to the reference voice and to a contrast voice. `CHECK` lines need listening.
- Dubbed track on an existing edit: translate the blocks, write `jobs.json` items with `max_seconds` = the block's slot in `edit_plan.json` (`end - vo_start - 0.1`) and `trim_pauses`; `tts` tries up to 6 seeds and keeps the shortest take, `OVER` lines need a shorter text or a light `atempo`; then `qc`, then `documentary.mix(spec, plan, files, out)` with the same plan for an identical music/ambience bed.

## Limits
Contact sheets and detectors propose; they do not prove that a punch landed. Voice quality is measured (ASR, pitch), not listened to. Fair use is a claim: Content ID can still claim, demonetise or block.
