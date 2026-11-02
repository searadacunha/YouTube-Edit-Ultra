# YouTube-Edit-Ultra — Codex and Claude Code

Read [docs/AUTONOMOUS_WORKFLOW.md](docs/AUTONOMOUS_WORKFLOW.md) before music-highlight production, [docs/EDITORIAL_WORKFLOW.md](docs/EDITORIAL_WORKFLOW.md) for annotations or revisions, and [docs/DOCUMENTARY_MODE.md](docs/DOCUMENTARY_MODE.md) before narrated analysis films. The workflows share evidence and storage constraints but expose different entry points.

## Production and resumption

- Prefer `ueu create "<athlete> — <style> — <duration>"`, then `ueu status JOB` / `ueu resume JOB`. Run `ultra doctor` first. Reinstall the editable package after console-entrypoint changes. Preserve the `ultra` interfaces and the Stop-Bullshiting banner.
- Inspect the existing manifest, journal, running workers, reports and input hashes before resuming. Reuse verified checkpoints; do not rerun acquisition or rebuild an accepted soundtrack/thumbnail merely because the video stage failed. A changed verified artifact requires a new job.
- State normally lives in `~/.local/share/youtube-edit-ultra/`; jobs in `output/jobs/`. Catalogue scans do not copy media. Never touch RuView or Trash. Mark generated fixtures and unrelated trees with `.ultra-ignore`.
- Review the actual blocker, then continue available source/evidence research or frame review within the user's authorized task. Do not ask the user to coordinate downloads or assembly. Missing indispensable permissions, access or capacity remain explicit blockers, never invented success. For personal offline edits with explicit local --root paths, --attest-local-media records the user's attestation (not independent rights verification); --auto-actions can use heuristic windows without pretending they were reviewed.

## Documentary-specific guardrails

- `ueu documentary --spec FILE.yaml` reads a film spec; unlike `ueu create`, it does not acquire or review footage automatically. Do not claim `--stage plan` is dependency-free: it runs voice synthesis and alignment. Keep the dedicated Apple-Silicon `.venv-doc` outside git.
- Use factual claim categories and referenced verified facts. `agent_frame_review` describes sampled frames examined by an agent; never label them `human_review` or assert boxer identity or action completeness without actual evidence.
- Treat local voice references and project YAML as private. Obtain consent for voice imitation, review the generated narration by listening, and prepare explicit YouTube synthetic-media disclosure on authorized publication. The documentary output's `youtube_metadata.md` is not the upload CLI's JSON metadata file.
- For documentary clips, keep review proxies and matching HD windows separate from montage action sidecars. A short `--proxy` preview tests layouts; it is not equivalent to final HD quality control.

## Rights and musical constraints

- Local presence, public access, an official uploader or Content ID acceptance is not permission. Retain URL, metadata, actual evidence and intended scope. Register hash-bound grants with `ultra catalogue authorize` / `authorize-url`; do not turn a project-specific private-use decision into a general publication grant.
- Personal mode normally requires evidence. Explicit --attest-local-media may record the user's attestation for relevant media in explicit local --root paths, for personal edits only; never describe it as independently verified. Commercial mode requires explicit licence, reviewer/date, adaptation, distribution and monetization scope for both music and footage, plus required credit. No access-control or DRM bypass.
- Spotify is authenticated, fully paginated metadata only. Genre requests can use admissible local audio when optional Spotify access fails; explicit playlists remain binding. Offline playlist caches are prior snapshots. Keep OAuth tokens and callbacks private and outside git.
- Licensed catalogue music can fill a genre request, but modern stock is not a historical R&B 2000s recording. Preserve decade, language/style constraints and known title-family exclusions. Never repeat music or sports actions automatically. Missing history is not evidence of no reuse.

## YouTube blocking

Measured on three uploads of one football montage (November 2026). Local export is unaffected; this is about what happens once a video is uploaded. Avoiding a block is not permission: the rights rules above still apply.

- Decide at source selection, before any render. One blocked match blocks the whole video, however short the shot.
- For a video meant for YouTube, exclude UEFA competitions, FIFA competitions and Ligue 1. Each blocked the video worldwide. Official club and fan compilations carry these matches too, so filter shot by shot on the competition, not by channel.
- LALIGA footage blocks by territory, not worldwide. A LALIGA-only cut had 20 such claims and lost 39 countries, including France, Canada and Australia. Tell the user this before rendering when those audiences matter. Official presentation footage and the music claims measured so far had no effect.
- No claim on one upload clears nothing: four Champions League matches unflagged on the second upload blocked the third. A competition never measured, such as a domestic cup, is excluded rather than tried.
- Enforce this in the plan with an allowlist of competitions. A shot outside it fails the plan; a shot never disappears silently.
- Upload as private and wait until Studio has finished its checks. YouTube warns that publishing earlier can bring a strike or limit visibility. The first readings move: one video went from 249 to 210 countries minutes after publication.
- Keep the sources until that verdict. Read it from `playabilityStatus`, yt-dlp, `availableCountries` and Studio `/video/ID/claims`. oEmbed 200 does not prove playback. Report blocked countries and the audience share Studio gives.
- Removing the footage is the only fix. Do not hide it from Content ID by mirroring, cropping, changing pitch or speed, or adding overlays.

## Editorial evidence and audio

- One-shot jobs prefer reviewed action provenance. Opt-in --auto-actions may use motion candidates when no sidecar exists, keeping provenance='heuristic' and an unverified report. Preserve provenance on import/merge. Do not label motion boundaries reviewed without seeing the action.
- Protect complete combinations and KO aftermath over beat placement. Use reviewed `.shots.json` cores/margins, optional source SHA-256, contextual intro/outro tags and explicit audio intent. Long cores are allowed; do not split them to satisfy a cut-rate target.
- Portable FFmpeg/NumPy music analysis is default. `legacy_music_root` is only an explicit compatibility backend. Do not assume other historical repositories exist or invent rhythm/downbeats.
- `audio_intent` accepts `auto`, `mute`, `ambience`, `featured`. Featured audio must be an explicit editorial choice, not guessed dialogue detection. Its gain is bounded and music ducks smoothly; ordinary ambience keeps its 20 dB cap. Final true peak must still be measured.
- A technical pass, source-window report, contact sheet or synthetic test does not establish boxer identity, complete actions or artistic acceptance. Describe the actual visual/listening sample. For long artistic revisions, examine a short opening where resources allow; preserve rejected previews and previous finals.

## Storage and completion

- The normal 12 GB remaining-space floor protects other processes, including PolySentinel. The shared installed disk-guard configuration is outside this repository: do not silently change other processes' reservations. Reduce intermediates, safely clean verified job-owned temporaries or choose a separate output volume. Never label a capacity-blocked export complete.
- Preserve originals and final outputs. Streaming uses one bounded MP4 and an audio temporary, not per-shot MP4 copies. Audio recovery copies video packets and verifies their hash before delivery. Only explicitly owned job temporaries may be cleaned after verified delivery; no personal file deletion.
- Read final full-decode/quality logs, duration/frame/geometry checks, true-peak result, sampled duplicate report and action-core integrity. Incomplete checks block delivery. `COMPLETE_TECHNICAL` is not artistic acceptance, continuous human viewing or guaranteed monetization.
- No publication or external mutation is implied by local export. Git commits/pushes are permitted only within the user's authorized task; do not rewrite history. Append verified work, exact evidence, limitations and next steps to `JOURNAL_AGENTS.md` under the common protocol.

## Development and historical references

Run `.venv/bin/python -m ruff check --select E9,F src tests`, the installed `ueu --help`, and relevant `.venv/bin/python -m pytest` checks. Use isolated fixtures and state; never mutate live credentials/catalogues in tests. Separate real short FFmpeg exports from simulated HTTP/Ollama/disk conditions and historical-media checks. Leave Crawford V2 source/final files unchanged during regression work.

Read [docs/LEGACY_EXECUTION_DIAGNOSIS.md](docs/LEGACY_EXECUTION_DIAGNOSIS.md) and [docs/PRODUCTION_VALIDATION.md](docs/PRODUCTION_VALIDATION.md) for historical evidence. Import manifests as data; do not run old downloaders blindly. Analysis-only tracks are not proven usage. Past agent-driven productions do not certify arbitrary unattended 30-minute requests.
