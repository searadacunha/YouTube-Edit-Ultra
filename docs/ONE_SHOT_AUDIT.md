# One-command audit and implementation — 30 October 2026

## Result and acceptance boundary

`ueu create "Terence Crawford — R&B 2000s — 30 minutes"` now orchestrates
acquisition, validation, music preparation, editorial planning, streaming export,
quality control, bounded audio repair and delivery. Each stage has a persistent
checkpoint; the same request resumes rather than creating another export.

This is an operational **conditional** pipeline, not a validated universal boxing
recognizer. It can complete without individual step commands when enough permitted
music and reviewed action windows are available. Motion/scene/VLM candidates alone
cannot certify a five-punch combination, the end of a KO, or boxer identity. Without
established boundaries it saves candidates and blocks explicitly. The absolute
“any boxer + any genre → finished video without any prior evidence” criterion
remains unfulfilled. Missing rights and disk space are also genuine blockers.

## Audit coverage

Reviewed the local package, CLI entry points, dependencies, tests, agent contracts,
configuration, bootstrap/publishing scripts, remote ancestry and CI. Inspected the
Crawford V2 preparation/render/QC evidence and immutable reference files. Baseline:
95 tests passed. The remote contained earlier public code; four later local commits
also contained private production notes. The public integration starts from the
remote branch and excludes that private ancestry, while preserving it locally.

| Area | Reused | Changes and remaining limits |
|---|---|---|
| Discovery | Public metadata queries, local catalogue, authorized URLs, yt-dlp | Current-content validation invalidates stale permissions; withdrawn grants stay withdrawn; unfinished yt-dlp component files cannot masquerade as final downloads. No DRM/access bypass. Live provider availability remains external. |
| Music | Licensed-provider discovery, Spotify metadata, history exclusions, loudness and crossfades | Personal/commercial scopes; historical release-year gate; Japanese language/country metadata; explicit playlist order; inferred onset-density progression for automatic playlists. Estimated tempo and section structure do not establish harmonic compatibility. |
| Actions | Reviewed windows, editorial planner, original 1× speed | Whole protected cores, long combinations, exact-duration fallback, optional tagged intro/outro. Explicit provenance required in one-shot. No reliable automatic identity/action recognizer is bundled. |
| Repetitions | Source interval bookkeeping | Content-bound perceptual samples across sources and final cuts. Longer complete cores take precedence over embedded short versions; different endings survive. Sampling may miss crops, replays at another angle or transformed copies. Budget exhaustion blocks, rather than claiming complete coverage. |
| Audio | Existing streamed PCM ambience and soundtrack normalization | Limiter automatic gain disabled; `auto/mute/ambience/featured` intent; smooth 7 dB music ducking around featured source audio; bounded source gain; true-peak QC and measured repair. Audio repair copies H.264 packets unchanged. |
| Export | FFmpeg H.264/AAC, source thumbnail and storyboard | Unique partials, no-overwrite publication, full decode, expected geometry/rate/frame count, stream timing, black/freeze/silence checks. Bad storyboard extraction fails visibly. |
| Recovery | Existing catalogue and caches | Central manifest, per-stage hashes, process-group liveness, locks held through error reporting, interruption checkpoints, idempotent music use, final-file revalidation. Changed inputs/checkpoints require a new job; live children never trigger a duplicate render. |
| Storage | Installed disk-guard and 12 GB floor | Estimated reservations, single streamed encode, hard-linked final delivery, optional APFS clone, owned temporary cleanup after QC. No automatic floor exception or deletion of personal files. |
| Privacy/CI | GitHub Actions and existing repository | Python 3.11–3.13 tests, Ruff, installed CLI smoke checks. Publisher never stages arbitrary files or creates a public repository; outgoing-history guard includes private notes/media. Private evidence stays local. |

## Crawford lessons incorporated

The earlier +1.2 dBFS output was repaired with audio attenuation and video stream
copy. The new engine prevents unintended limiter gain and measures **encoded** true
peak, since a pre-encoder limiter alone does not prove absence of AAC overshoot.
New deliveries target at most −1 dBTP and recheck repaired artifacts. Repair is
bounded, hash-bound and storage-guarded; failure never overwrites the original.
See FFmpeg's [limiter implementation](https://ffmpeg.org/doxygen/8.1/af__alimiter_8c.html)
for the automatic-level option that required disabling.

Selected-window integrity and sampled pHash checks are not complete perceptual
review. The one-shot report records that distinction instead of equating successful
encoding with artistic or semantic acceptance. Black/freeze/silence candidates and
uncertain actions block delivery; only the measured audio-level fault has an
automated repair path. Arbitrary editorial defects are not silently “fixed”.

## Review findings fixed before publication

- A competing resume could overwrite a running job's manifest after failing its lock.
- A completed-file shortcut could skip missing QA/metadata/tracklist artifacts.
- Distinct output roots or explicit playlist requests could share an unsuitable job ID.
- Interruption could let a different job consume music before the first resumed.
- One-shot metadata omitted licence-required credits.
- Revoked URL permissions and unfinished yt-dlp fragments could be accepted.
- Motion extraction could deadlock on stderr or accept partial frames; model/cache
  corruption and failed storyboard frames lacked adequate errors.

Regression tests cover these cases. Existing `ultra create`, `ultra produce`,
catalogue and Spotify interfaces remain; no old script was deleted without caller
proof. The Stop-Bullshiting banner and existing media were not changed.

See [verification record](ONE_SHOT_VERIFICATION.md), [usage](AUTONOMOUS_WORKFLOW.md)
and [public GitHub workflow](GITHUB.md).
