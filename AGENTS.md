# YouTube-Edit-Ultra — Codex and Claude Code

Read [docs/AUTONOMOUS_WORKFLOW.md](docs/AUTONOMOUS_WORKFLOW.md) before production and [docs/EDITORIAL_WORKFLOW.md](docs/EDITORIAL_WORKFLOW.md) for annotations or revisions. These are the shared production contract.

## Production and resumption

- Prefer `ueu create "<athlete> — <style> — <duration>"`, then `ueu status JOB` / `ueu resume JOB`. Run `ultra doctor` first. Reinstall the editable package after console-entrypoint changes. Preserve the `ultra` interfaces and the Stop-Bullshiting banner.
- Inspect the existing manifest, journal, running workers, reports and input hashes before resuming. Reuse verified checkpoints; do not rerun acquisition or rebuild an accepted soundtrack/thumbnail merely because the video stage failed. A changed verified artifact requires a new job.
- State normally lives in `~/.local/share/youtube-edit-ultra/`; jobs in `output/jobs/`. Catalogue scans do not copy media. Never touch RuView or Trash. Mark generated fixtures and unrelated trees with `.ultra-ignore`.
- Review the actual blocker, then continue available source/evidence research or frame review within the user's authorized task. Do not ask the user to coordinate downloads or assembly. Missing indispensable permissions, access, reviewed boundaries or capacity remain explicit blockers, never invented success.

## Rights and musical constraints

- Local presence, public access, an official uploader or Content ID acceptance is not permission. Retain URL, metadata, actual evidence and intended scope. Register hash-bound grants with `ultra catalogue authorize` / `authorize-url`; do not turn a project-specific private-use decision into a general publication grant.
- Personal mode still requires evidence. Commercial mode requires explicit licence, reviewer/date, adaptation, distribution and monetization scope for both music and footage, plus required credit. Recorded evidence does not guarantee ownership or monetization. No access-control or DRM bypass.
- Spotify is authenticated, fully paginated metadata only. Genre requests can use admissible local audio when optional Spotify access fails; explicit playlists remain binding. Offline playlist caches are prior snapshots. Keep OAuth tokens and callbacks private and outside git.
- Licensed catalogue music can fill a genre request, but modern stock is not a historical R&B 2000s recording. Preserve decade, language/style constraints and known title-family exclusions. Never repeat music or sports actions automatically. Missing history is not evidence of no reuse.

## Editorial evidence and audio

- One-shot jobs require explicit reviewed action provenance. Motion, scene and sampled Ollama results remain candidates, regardless of confidence or file format. Preserve provenance on import/merge. Do not label motion boundaries reviewed without seeing the action.
- Protect complete combinations and KO aftermath over beat placement. Use reviewed `.shots.json` cores/margins, optional source SHA-256, contextual intro/outro tags and explicit audio intent. Long cores are allowed; do not split them to satisfy a cut-rate target.
- Portable FFmpeg/NumPy music analysis is default. `legacy_music_root` is only an explicit compatibility backend. Do not assume other historical repositories exist or invent rhythm/downbeats.
- `audio_intent` accepts `auto`, `mute`, `ambience`, `featured`. Featured audio must be an explicit editorial choice, not guessed dialogue detection. Its gain is bounded and music ducks smoothly; ordinary ambience keeps its 20 dB cap. Final true peak must still be measured.
- A technical pass, source-window report, contact sheet or synthetic test does not establish boxer identity, complete actions or artistic acceptance. Describe the actual visual/listening sample. For long artistic revisions, examine a short opening where resources allow; preserve rejected previews and previous finals.

## Storage and completion

- Keep the normal 12 GB remaining-space floor. Estimates and installed disk-guard reservations precede heavy writes. Never lower `reserve_bytes` / `DISKGUARD_FLOOR_BYTES`, add `--accord`, split a blocked operation or reuse an earlier exception to evade the guard.
- Preserve originals and final outputs. Streaming uses one bounded MP4 and an audio temporary, not per-shot MP4 copies. Audio recovery copies video packets and verifies their hash before delivery. Only explicitly owned job temporaries may be cleaned after verified delivery; no personal file deletion.
- Read final full-decode/quality logs, duration/frame/geometry checks, true-peak result, sampled duplicate report and action-core integrity. Incomplete checks block delivery. `COMPLETE_TECHNICAL` is not artistic acceptance, continuous human viewing or guaranteed monetization.
- No publication or external mutation is implied by local export. Git commits/pushes are permitted only within the user's authorized task; do not rewrite history. Append verified work, exact evidence, limitations and next steps to `JOURNAL_AGENTS.md` under the common protocol.

## Development and historical references

Run `.venv/bin/python -m ruff check --select E9,F src tests`, the installed `ueu --help`, and relevant `.venv/bin/python -m pytest` checks. Use isolated fixtures and state; never mutate live credentials/catalogues in tests. Separate real short FFmpeg exports from simulated HTTP/Ollama/disk conditions and historical-media checks. Leave Crawford V2 source/final files unchanged during regression work.

Read [docs/LEGACY_EXECUTION_DIAGNOSIS.md](docs/LEGACY_EXECUTION_DIAGNOSIS.md) and [docs/PRODUCTION_VALIDATION.md](docs/PRODUCTION_VALIDATION.md) for historical evidence. Import manifests as data; do not run old downloaders blindly. Analysis-only tracks are not proven usage. Past agent-driven productions do not certify arbitrary unattended 30-minute requests.
