# One-prompt local production

```bash
ueu create "Terence Crawford — R&B 2000s — 30 minutes"
ueu create "Canelo Álvarez — Reggaeton — 30 minutes"
ueu create "Naoya Inoue — Japanese hip-hop — 20 minutes"
```

`ueu create` orchestrates discovery, authorized acquisition, source validation, reviewed action selection, playlist construction, music analysis, planning, mixing, export, quality control and delivery. It returns a verified local MP4 when the required inputs exist, or a persisted blocker. It never publishes to YouTube.

**Reviewed action boundaries remain a prerequisite.** Motion and sampled visual analysis propose candidates; they cannot certify boxer identity, complete combinations or a knockout's aftermath. Missing or unverified annotations block the one-shot job. Technical checks do not establish continuous human viewing or artistic acceptance.

## Installation and commands

Install Python 3.11+, FFmpeg and ffprobe, then from this checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[all]'
ultra doctor
ueu --help
```

After changes to console entry points, rerun the editable install. `ultra create`, `ultra produce`, catalogue commands and explicit publishing remain available. The checkpointed one-shot interface is `ueu create`.

| Command or option | Behavior |
|---|---|
| `ueu create "athlete, style, duration"` | Create or reuse the matching job |
| `ueu resume output/jobs/JOB` | Resume saved options and verified checkpoints |
| `ueu status output/jobs/JOB` | Print the saved manifest without running production |
| `--root /media/library` | Choose scan roots; repeat for several roots |
| `--state-dir /path/state` | Separate persistent catalogue and permissions |
| `--output-dir /path/jobs` | Job parent directory; default `output/jobs` |
| `--offline` | Local inputs; explicit Spotify playlists require a matching complete cached snapshot |
| `--playlist URL` | Bind selection to requested Spotify playlist metadata |
| `--mode personal` | Default: documented permission for the intended personal use |
| `--mode commercial` | Explicit commercial scope for every audiovisual and musical asset |
| `--desktop` | Additional verified Desktop delivery when safe |
| `--new-job` | Distinct job instead of reusing its stable identifier |
| `--width`, `--height`, `--fps` | Override default 1920×1080 at 30 fps |

Use `ueu create --help` for the installed interface. This command exposes no repeat, publication or disk-floor override. Resume after correcting a blocker; create a new job when verified checkpoint artifacts or input bytes change. An interrupted render restarts its render stage, not acquisition and planning from scratch.

## Discovery and rights

State defaults to `~/.local/share/youtube-edit-ultra/`. Scans normally inspect Documents, Music, Movies, Downloads and Desktop without copying media. RuView, Trash, symlink directories, dependency trees and `.ultra-ignore` folders are excluded. Errors and incomplete historical coverage remain in reports.

Local files, public URLs, official channels and successful Content ID checks do not establish permission. Register actual evidence once; grants are bound to content hashes:

```bash
ultra catalogue authorize /media/owned-bout.mp4 --athlete 'Terence Crawford' \
  --evidence 'Actual permission record and scope'
ultra catalogue authorize /media/authorized-song.flac --style rnb \
  --title 'Exact title' --artist 'Exact artist' --release-date 2004 \
  --evidence 'Actual music permission record and scope'
ultra catalogue authorize-url 'https://example.org/permitted-clip.mp4' \
  --kind video --athlete 'Terence Crawford' --title 'Licensed bout' \
  --evidence 'Actual authorization for this URL and use'
```

These demonstrate the schema; they are not grants for example assets. Preserve actual documents and their scope. `authorize` and `authorize-url` accept `--mode commercial --rights-json /path/rights.json`. Commercial evidence requires a licence, `rights_verified_by`, `rights_verified_at`, explicit `commercial_use`, `adaptation`, `distribution` and `monetization` booleans, and `credit` when attribution is required. Both footage and music must qualify. The software checks recorded scope; it cannot authenticate ownership or guarantee platform monetization. Delivery does not declare `monetizable=true`.

Public video search and historical source/query manifests aid discovery. Downloads use yt-dlp or original HTTPS links, bounded retries, validation and caches. Unknown permission remains a blocker. A declared CC licence permits personal-mode acquisition only for explicitly configured trusted publishers; it is not silently promoted to a commercial grant. No DRM, authentication or geographical restriction bypass is provided.

Source container duration is only a preflight measure, not unique reviewed-action coverage. Full source decode and sampled cross-file perceptual comparisons precede planning. Dedupe prefers longer protected cores and retains different sampled endings. Short clips, alternate angles, crops and events between samples remain limitations.

## Music

Authorized local audio is preferred. When insufficient, genre requests can discover publisher-licensed music through Mixkit and Free Stock Music, retaining available licence/page evidence. Failure of one provider or track does not suppress remaining candidates. A catalogue declaration alone cannot satisfy commercial mode.

**R&B 2000s requires dated 2000–2009 recordings; modern stock tracks are not substitutes.** Japanese hip-hop requires matching music metadata. Insufficient admissible music is reported rather than relabelled or repeated.

Playlist coverage uses measured audible bounds and 0.7-second crossfades. Known used content hashes and title families are excluded; incomplete history is disclosed. Selection and ordering are deterministic, not a trained taste model. Static gain targets −18 LUFS with a source ceiling of −3 dBTP. Final AAC output is measured separately.

Spotify provides metadata only. A genre request can use authorized local music when optional Spotify access fails. An explicitly requested playlist remains binding. Initial PKCE setup, if needed:

```bash
ultra spotify login --client-id YOUR_CLIENT_ID
ultra spotify finish 'http://127.0.0.1:8769/callback?code=...&state=...'
ultra spotify sync 'https://open.spotify.com/playlist/PLAYLIST_ID' --style reggaeton
```

Use the actual printed URL and callback; keep tokens and callbacks out of shared logs and git. Retrieval checks pagination and completeness. No Spotify audio extraction exists. An offline playlist cache is a prior snapshot, not proof of current remote membership.

## Actions, narrative and audio

Adjacent `.shots.json` files supply reviewed safe margins and protected cores. `.actions.json` supplies whole reviewed windows. One-shot production requires explicit accepted provenance (`annotation`, `visual_review`, `visual_sample_review` or `human_review`) in the real evidence. Do not rename generated motion windows as reviewed. Optional `source_sha256` binds annotations to source bytes.

Missing boundaries produce `review_required.json` and, where scanning is needed, candidate files in `review/`. The agent may inspect available footage and add verified boundaries. If that cannot be completed, report the exact blocker; never invent annotations to make the job pass.

See [editorial workflow](EDITORIAL_WORKFLOW.md) for the schema. Reviewed `kind: intro` and `kind: outro` context can be reserved at the opening and closing. Complete cores take priority over beats; long actions remain possible. Bounded backtracking recovers some greedy dead ends, but failure is not an exhaustive proof of impossibility.

Default music structure analysis uses portable FFmpeg/NumPy without historical repositories or downloaded models. Explicit `legacy_music_root` retains compatibility with the older backend. Caches are bound to content, track boundaries and backend version. No beat grid is invented for music without measurable transients.

| `audio_intent` | Streaming mix behavior |
|---|---|
| `auto` | Legacy intro/insert labels mute source audio; ordinary ambience remains subdued |
| `mute` | Source muted, music retained |
| `ambience` | Source retained even for intro/insert labels, with ordinary ambience cap |
| `featured` | Marked source audio retained with bounded gain and smooth 7 dB music duck |

Featured intent is explicit metadata, not speech recognition. Its source gain is limited to 2×. Ordinary ambience stays at least 20 dB below unducked music. Sample-aligned mixing uses one temporary FLAC and limits before integer quantization. The legacy segment renderer rejects explicit intents it cannot implement.

## Checkpoints and storage

The manifest records stage states, attempts, options, errors, artifact hashes and worker process groups. Completed stages are reused only while their artifacts match. Catalogue/job locks prevent concurrent writers; surviving workers prevent duplicate execution. Repeating a completed job verifies its delivery and avoids consuming music twice.

The common floor is **12 GB free after the estimated operation**. Heavy subprocesses use the installed disk-guard reservation manager when available; downloads and FFmpeg stages check capacity. With about 11 GB free, a new job may correctly block before rendering. The code never lowers the floor or adds `--accord`. An earlier project-specific exception does not authorize a new one.

Streaming avoids per-shot MP4 copies. Temporary paths are unique, interrupted outputs remain inspectable and existing files are not overwritten. Audio repair budgets a separate MP4, copies the encoded video stream and checks its packet hash. Cleanup after verified delivery is limited to explicitly owned job temporaries. Sources, previous finals and unrelated files remain protected; reusable analysis caches are retained.

Delivery is under `output/jobs/JOB/ATHLETE-DURATIONs/`, with a clean athlete/style/duration MP4 name. `--desktop` creates a safe reference or guarded copy, preserves conflicts and verifies the result. `delivery.json` gives its actual path and hash.

| Evidence | Purpose |
|---|---|
| `manifest.json`, `REPORT.txt` | Job state, blocker, checkpoints and resume command |
| Source/acquisition/readiness reports | Provenance, permission evidence and coverage |
| `source_integrity.json`, `shots.json`, `shot_duplicates.json` | Decode results, protected windows, sampled exclusions |
| `edit_plan.json`, `music_structure.json`, `music_tracklist.json` | Selected intervals, music analysis and actual usage |
| `render_inputs.json`, `render_report.json` | Export inputs and technical settings |
| `verification_report.json`, decode logs, `duplicate_report.json` | Final measurements and limits |
| `delivery.json`, thumbnail, storyboard, YouTube metadata | Verified delivery and prepared supporting artifacts |

Source/job reports live at the job root; render/delivery artifacts live in the athlete-duration directory. A blocked run may have only the evidence produced before its failing stage.

## Quality gate

Finalization requires MP4/H.264 8-bit 4:2:0, AAC, square pixels, requested dimensions/fps, full audio/video decode, container duration within 0.15 s and frame count within one frame. Stream starts must agree within `max(0.05 s, 2/fps)` and stream durations within 0.15 s. Timestamps do not prove musical or punch synchronization.

The gate rejects detected black intervals ≥0.5 s, freezes ≥2 s and silence ≥1 s at its recorded thresholds, or true peak above −1 dBTP. Intentional effects can trigger conservative flags and require examination. True-peak failures alone allow up to two automatic audio-only corrections with remeasurement and identical encoded video packets. Other defects are not silently repaired. Action-core integrity and sampled final duplicates must also pass; exhausting the duplicate budget blocks delivery.

`COMPLETE_TECHNICAL` means the technical job finished. It does not assert continuous human viewing, action-recognition accuracy, artistic acceptance or guaranteed monetization. No automatic upload occurs.

## Reproducible tests and historical evidence

```bash
python -m pip install -e '.[dev]'
python -m ruff check --select E9,F src tests
ueu --help
python -m pytest
```

CI uses Python 3.11, 3.12 and 3.13 with FFmpeg. Tests include real short synthetic exports, one-shot delivery, interruption/resume, changed checkpoints, differently encoded duplicates, true-peak recovery with unchanged video packets and explicit audio intents. Fixtures are owned test assets excluded from the real catalogue.

Network/provider and Ollama boundaries are simulated where used; tests do not prove live availability or model accuracy. Disk conditions and guard integration are simulated, without granting a live disk-floor exception. Crawford V2 originals remain unchanged. Exact real-media checks and their limits belong in the session verification report, not inferred from green fixtures.

Historical evidence remains in [PRODUCTION_VALIDATION.md](PRODUCTION_VALIDATION.md), [LEGACY_EXECUTION_DIAGNOSIS.md](LEGACY_EXECUTION_DIAGNOSIS.md) and the project journal. Agent-driven past productions do not prove that arbitrary new athlete/style requests can bypass missing rights, review or resources.
