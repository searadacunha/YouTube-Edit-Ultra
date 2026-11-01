# Narrated documentary mode

`ueu documentary --spec FILE.yaml` is a separate, spec-driven, local renderer for spoken analysis films. It combines Qwen3-TTS speech, word-timed subtitles, cards, annotated footage, freezes, slow motion and split screens. It reuses job checkpoints and technical finalization, **not** the source discovery/authorization machinery of `ueu create`.

An encoded file or a complete evidence ledger does not verify the truth of the narration, a boxer's identity, the full action, the voice's perceived quality or publishing rights.

## Installation

Install the main package with Python 3.11+ and FFmpeg/FFprobe, using the repository's normal quick start. In its activated `.venv`, install subtitles:

```bash
python -m pip install -e '.[documentary]'
ueu documentary --help
```

The currently implemented Qwen3-TTS backend is based on **Apple Silicon and MLX**. It is not part of `.[all]` or `scripts/bootstrap_mac.sh`; Intel macOS and Linux do not have a documented equivalent voice backend in this repository. In the repository root, prepare a separate Python 3.12 environment:

```bash
python3.12 -m venv .venv-doc
.venv-doc/bin/python -m pip install --upgrade pip
.venv-doc/bin/python -m pip install 'mlx-audio==0.6.3' 'faster-whisper==1.2.1'
```

These versions match the recorded integration, not a guarantee for every future runtime. Voice weights and Whisper models are external downloads; check their terms and available disk space first. `pysubs2` runs in the main `.venv`; `.venv-doc` owns MLX and faster-whisper. Neither environment nor the downloaded model is committed.

## Minimal project (no footage)

The tracked [starter YAML](../examples/documentary.example.yml) has two graphic-card blocks and no media or fact claims. It helps validate the spec/voice/render flow without implying that an athlete was identified by the software.

```bash
mkdir -p projects output/documentary-demo/audio
cp examples/documentary.example.yml projects/demo.yaml
# Supply a synthetic or consented WAV at output/documentary-demo/audio/voice-reference.wav
ueu documentary --spec projects/demo.yaml --stage plan
ueu documentary --spec projects/demo.yaml --preview 0 8 --proxy
ueu documentary --spec projects/demo.yaml
```

The `output` key is resolved **relative to the YAML**, then `voice.ref_audio` and `music[].path` are resolved **relative to that output folder**. Conversely, `voice.python` and `voice.script` are relative to the YAML directory. The example works unchanged whether saved in `examples/` or copied into root-level `projects/`. A card-only preview does not need a proxy file; the `--proxy` flag matters when footage is present.

To generate an original, synthetic reference voice on an Apple-Silicon machine:

```bash
.venv-doc/bin/python -I scripts/doc_voice.py design \
  --model mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit \
  --instruct 'Voix française claire, posée, énergique' \
  --text 'Bienvenue dans cette analyse sportive.' \
  --out output/documentary-demo/audio/reference --seeds 1,2
# Listen to the candidates; select one yourself:
cp output/documentary-demo/audio/reference/design_seed1.wav \
   output/documentary-demo/audio/voice-reference.wav
```

For cloning a person's voice, use only a recording supplied with their consent and identify that choice in `voice.credit`. Generated speech must be listened to: ASR scores and speaker similarity are quality signals, not listening.

## YAML fields and media contract

| Field | Required meaning |
|---|---|
| `title`, `description`, `output`, `video` | Title, copy, output folder, width/height/fps |
| `duration_range: [min, max]` | Acceptance range in seconds for the measured plan; not an instruction to trim real actions |
| `voice` | `python`, `script`, `model`, `ref_audio`; optional `ref_text`, `lang`, `asr_lang`, `tempo`, `target_wpm`, `trim_pauses`, `credit` |
| `chapters[].id/title/blocks[]` | Ordered chapters; every block needs a distinct `id`, nonempty `text` and at least one visual |
| `blocks[].say` | Optional alternative spoken spelling; `text` remains the exact subtitle/script text |
| `blocks[].claims[]` | `cat`: `verified_fact`, `technical_interpretation`, `prediction` or `rhetorical_hook` |
| `facts` | Optional list of JSON files under the output folder; `verified_fact` needs a matching fact ID with `status: verified` |
| `sources` / `sources_file` | Source metadata; a present `sources_file` JSON replaces inline `sources` |
| `music[].path` | Local audio relative to output; no audio is extracted from Spotify |

Each filmed `clip`, `freeze` or `split` part needs `src`, `action`, `confidence` between 0 and 1, and a truthful `provenance`; clips use `t: [start, end]` in seconds of the original. Optional `boxer`, together with block `subject` and `require_boxer: true`, enables a name-match check against the declared labels, not visual identity recognition. Only `card` visuals are exempt from footage metadata. `agent_frame_review` means sampled frames actually examined by an agent; `visual_review` and `human_review` are explicitly rejected as agent-supplied provenance.

For footage reports, each referenced source needs at least `url`, `channel`, `title`, `fight`, `fight_date`, `credit`, and `rights.status`. These are records **you must verify**, not a mechanism for acquiring rights. Do not set `status` to a licensed value unless the licence exists. The optional rights decision `{decided_by, decided_on, note}` records a legal/use decision, not an automatic permission or guarantee that fair use applies.

A facts JSON file is an array of objects such as `{ "id": "f1", "status": "verified", "claim_fr": "…", "value": "…", "sources": ["…"] }`. `verified_fact` references these IDs in `claims[].facts`. `unverified_claim` does not belong in narration: the parser refuses unsupported claim categories.

### Prepared footage is not automatically fetched

The film renderer expects review proxies under `<output>/sources/proxies/<source-id>.mp4`. For full-resolution clips, it reads a pre-existing `<output>/sources/hd_index.json` linking source windows to local HD segments and match metrics; the separate `fetch_hd` implementation can build such an index within a prepared workflow, but **`ueu documentary` does not invoke it automatically**. A bare URL in the YAML is source metadata, not a download request. Build and inspect real source windows and rights evidence before the final run.

Visuals include `clip` (optional `speed`, `zoom`, `overlays`, `audio`, `subs: top`), `freeze` (time `at`), `card` (`title`, `chapter`, `stat`, `table`, `compare`, `quote` or `image` variants) and `split`. Keep clip intervals consistent with their annotated actions. Slow motion repeats actual frames without fabricating interpolated action; it must be visibly identified in the edit.

## Stages, output and review

```bash
ueu documentary --spec projects/film.yaml --stage plan
ueu documentary --spec projects/film.yaml --preview 45 12 --proxy
ueu documentary --spec projects/film.yaml --preview 45 12
ueu documentary --spec projects/film.yaml
```

`--stage plan` **does invoke TTS and ASR alignment**; it validates and writes the timeline, subtitles and reporting data but not the final MP4. `--preview START SECONDS` exports a short MP4 and `.preview.json`; `--proxy` is a lower-resolution layout check, not a replacement for the HD preview. Final output goes to the configured output folder (default filename `documentary.mp4`). Re-running a spec reuses eligible voice/render checkpoints.

The output folder includes `job/manifest.json`, `audio/voice_jobs.json`, `audio/align*.json`, `edit_plan.json`, `evidence_ledger.json`, `shot_narration_alignment.json`, ASS/SRT subtitles, `script_fr.md`, `youtube_metadata.md` and `quality_report.json` after the corresponding stages succeed. Source clips, proxies, model weights and voice references are not distributed in the repository.

Narration speed can be tuned via `voice.tempo` (FFmpeg `atempo` preserves pitch) or `target_wpm` with `max_tempo`; pause trimming is optional. Review actual audio, name pronunciation, dropped negations, subtitle timing and which athlete is visible during each sentence. The standalone helper also offers `qc`, `diarize` and `design` modes; see `scripts/doc_voice.py --help` or its subcommand help.

Production checks verify decode, duration/frames, black/freeze/silence flags and measured final true peak (limit −1 dBTP). They do not certify artistic acceptance or legal reuse. The ordinary **12 GB remaining-space floor** applies.

## Upload is separate

`ueu documentary` writes `youtube_metadata.md` for editorial review and **does not upload**. The `ultra publish` command instead consumes JSON metadata. For a permitted upload involving realistic synthetic or cloned speech, include `"synthetic_media": true` in that JSON and pass `--metadata`; review actual YouTube disclosure obligations. A fair-use claim may still receive Content ID claims, monetization restrictions or a block. Rights, platform decisions and voice consent remain separate from the technical render.
