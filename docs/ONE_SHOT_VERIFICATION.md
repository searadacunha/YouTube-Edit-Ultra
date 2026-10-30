# Verification record — 30 October 2026

## Executed locally

- Baseline: **95 passed**.
- Full suite in the isolated public worktree: **231 passed**, including publishing-helper regressions.
- Ruff `E9,F`, shell syntax and `git diff --check`: passed.
- Editable installation succeeded; installed `ueu --help` and `ueu create --help`
  work. The installed command resumed an already verified short fixture delivery.
- Real FFmpeg six-second one-shot fixture: acquisition/preparation, planning,
  MP4 export, 180 decoded frames, QC, thumbnail, storyboard, metadata and tracklist.
  Tests also exercise interrupted resume, concurrent-process exclusion, corruption,
  rights modes, mandatory credits and idempotent music consumption.
- Real FFmpeg audio tests cover featured intro/ambience/mute behavior, smooth
  ducking, clipping correction and identical copied H.264 packet hashes.
- The installed command, **without a disk override**, completed input preparation
  and then refused the soundtrack stage at about 10.75 GB free against the 12 GB
  floor. No new MP4 was written. This is a live storage-gate demonstration, not a
  newly completed real boxing production.

Commands:

```bash
python -m pytest
python -m ruff check src tests --select E9,F
ueu --help
ueu create --help
```

## Read-only real-media regression

Crawford V2 was fully decoded by the new verifier without re-encoding or changing
its bytes: **1,800.000 s, 54,000 frames, 1920×1080, 30 fps**, true peak **−0.5 dBFS**.
No black ≥0.5 s, freeze ≥2 s or silence ≥1 s was flagged at the configured detection
thresholds. Stream timing passed. This reference check used its historical
non-clipping limit of 0 dBFS; **new jobs require −1 dBTP**, so this does not claim the
old file already meets the new headroom target.

Reference SHA-256:
`abd83a1ebcdefe691dd4f570b784357a4955f5e32c3a066b7d03fc36f5363280`.
The reference edit plan, soundtrack and terminal banner also retained their hashes.
Three previously reviewed real-source windows were separately decoded. Neither
check is continuous human viewing/listening or fresh semantic validation of all
508 shots. No original media or final export was modified.

## Simulated and unexecuted boundaries

Owned generated fixtures contain test patterns and tones, not boxing ground truth.
Their small FFmpeg renders are real. Pytest simulates disk availability/guard
integration so these bounded fixtures can run independently of host storage.
HTTP/provider transport, GitHub publication gates and Ollama responses are mocked
where tested; that does not establish current external service availability.

No new live music/video acquisition, Spotify consent, real Ollama recognition or
new 20/30-minute one-shot boxing render completed in this mission. Insufficient
normal disk headroom and unestablished reusable action/rights evidence prevent that
claim. Commercial grants are checked against recorded scope and credits; software
cannot independently establish ownership or promise monetization.

Duplicate detection is sampled and budgeted. Timestamp alignment is not a proof
of perceptual music synchronization. Artistic acceptance remains separate.

Local logs, manifests, detailed hashes and the private rights evidence remain under
`output/one-shot-20261030/` and the original production directories, excluded from
GitHub. Obsolete generated test MP4s were removed using an exact manifest, retaining
logs and a representative fixture set. Personal files/finals were preserved.

## GitHub verification

The reviewed public integration excludes private local journal ancestry. Remote
commit and CI checks are recorded after the authorized push; the presence of this
file alone is not a claim that that push or CI has succeeded.
