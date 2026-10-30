<div align="center">

<img src="docs/assets/youtube-edit-ultra.svg" width="960" alt="YOUTUBE EDIT ULTRA — red play logo">

# YouTube-Edit-Ultra

**Sports highlights with complete action windows, music and source audio.**

A local Python + FFmpeg editor for boxing, football and other sports. One command finds permitted sources, selects music, preserves reviewed action windows, renders and checks an MP4, then delivers it with an inspectable edit plan. Missing sources, rights, action review or disk capacity produce an explicit blocker.

[![Quality checks](https://github.com/searadacunha/YouTube-Edit-Ultra/actions/workflows/ci.yml/badge.svg)](https://github.com/searadacunha/YouTube-Edit-Ultra/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[Videos](#video-spotlight) · [Quick start](#quick-start) · [Commands](#commands) · [Action annotations](#action-annotations) · [Publishing](#optional-youtube-publishing) · [Français](#démarrage-en-français)

</div>

## Video spotlight

Skills, goals and music. Click a thumbnail to watch on YouTube.

<table>
  <tr>
    <td align="center" valign="top" width="33%">
      <a href="https://www.youtube.com/watch?v=nzWTKsrIfm0">
        <img src="https://img.youtube.com/vi/nzWTKsrIfm0/maxresdefault.jpg" width="400" alt="Cristiano Ronaldo — Danza Kuduro, skills and goals 2014">
      </a>
      <br><strong>Cristiano Ronaldo</strong>
      <br><sub>Danza Kuduro · Skills &amp; goals</sub>
      <br><br><strong>23.5M+ views</strong>
      <br><sub><a href="https://www.youtube.com/@kiano7hd">KIANO7HD</a></sub>
    </td>
    <td align="center" valign="top" width="33%">
      <a href="https://www.youtube.com/watch?v=KaJ7rc0uNTU">
        <img src="https://img.youtube.com/vi/KaJ7rc0uNTU/maxresdefault.jpg" width="400" alt="Neymar Jr — Balada Boa, sublime skills mix">
      </a>
      <br><strong>Neymar Jr</strong>
      <br><sub>Balada Boa · Skills mix</sub>
      <br><br><strong>17.1M+ views</strong>
      <br><sub><a href="https://www.youtube.com/@KHDfootball">KHDfootball</a></sub>
    </td>
    <td align="center" valign="top" width="33%">
      <a href="https://www.youtube.com/watch?v=QmpilIF6PG0">
        <img src="https://img.youtube.com/vi/QmpilIF6PG0/maxresdefault.jpg" width="400" alt="Kylian Mbappé — Ramenez la coupe à la maison, skills and goals 2024">
      </a>
      <br><strong>Kylian Mbappé</strong>
      <br><sub>Ramenez la coupe à la maison</sub>
      <br><br><strong>19.5M+ views</strong>
      <br><sub><a href="https://www.youtube.com/@resheditz">resheditz ツ</a></sub>
    </td>
  </tr>
</table>

<sub>YouTube view counts captured on 27 October 2026 · <a href="docs/VIDEO_GALLERY.md">Video credits &amp; source data</a></sub>

> **Local export is the default.** Uploading requires an explicit command.
>
> **Reviewed action boundaries are required by the one-shot pipeline.** Motion peaks and sampled model responses can suggest highlights; they cannot verify a goal, a knockout or an athlete's identity. Technical success is not artistic acceptance or continuous human viewing.

## What it does

| Input | Processing | Output |
|---|---|---|
| Local footage, or explicit authorized URLs | Motion candidates or imported action annotations | H.264 MP4 at original 1× speed |
| Local tracks, ordered playlist or explicit audio URLs | Crossfades, transient detection and impact alignment | Music mixed with original stadium/ring audio |
| Athlete, sport and target duration | Whole-window selection with source interval reuse disabled by default | Edit plan, source report and integrity report |
| Optional local Ollama model | Ranks candidate clips from sampled frames | Recorded model responses |

Football, boxing, MMA, basketball and generic presets provide different amounts of context around detected motion. The planner preserves each **selected window**; annotation quality determines whether that window contains the complete real-world action.

## Autonomous production

```bash
ueu create "Terence Crawford — R&B 2000s — 30 minutes"
ueu create "Canelo Álvarez — Reggaeton — 30 minutes"
ueu create "Naoya Inoue — Japanese hip-hop — 20 minutes"
```

`ueu` coordinates discovery → acquisition → validation → playlist → planning → mix →
export → quality control → delivery. Catalogue permissions and song history persist.
Each job records stage checkpoints, artifact hashes, logs and a readable report.

```bash
ueu status output/jobs/JOB_DIRECTORY
ueu resume output/jobs/JOB_DIRECTORY
```

Defaults are personal use, H.264/AAC, 1080p30 and local delivery. `--mode commercial`
requires recorded commercial scope for both music and footage; it does not guarantee
monetization. `--desktop` requests safe additional Desktop delivery. R&B 2000s is
not replaced with modern stock music. Spotify is optional metadata, never an audio source.

See [the autonomous workflow](docs/AUTONOMOUS_WORKFLOW.md) for permissions, reviewed
annotations, disk requirements and exact gates. `ultra create` and `ultra produce`
remain compatible legacy interfaces. `ueu create` never publishes.

## Quick start

### macOS: Apple Silicon or Intel

Install [Homebrew](https://brew.sh/) if needed, then run:

```bash
brew install ffmpeg python@3.12
git clone https://github.com/searadacunha/YouTube-Edit-Ultra.git
cd YouTube-Edit-Ultra
bash scripts/bootstrap_mac.sh
source .venv/bin/activate
ultra doctor
ueu --help
```

The bootstrap detects Python 3.11+ on your `PATH` or at standard Homebrew locations. To choose an interpreter explicitly:

```bash
ULTRA_PYTHON=/path/to/python3.12 bash scripts/bootstrap_mac.sh
```

Clone the repository before running its scripts. No downloaded ZIP or global `ultra` installation is assumed. Activate `.venv` again in each new terminal.

### Linux or manual installation

Install Python 3.11+, `ffmpeg` and `ffprobe`, then:

```bash
git clone https://github.com/searadacunha/YouTube-Edit-Ultra.git
cd YouTube-Edit-Ultra
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[all]'
ultra init
ultra doctor
ueu --help
```

For local editing without downloads, scene detection or uploads, install with `python -m pip install -e .` instead. Extras are `download`, `scenes` and `youtube`; `all` includes all three.

### Launch screen

Open the **YOUTUBE EDIT ULTRA** launch screen and command overview:

```bash
ultra
```

Display just the terminal logo:

```bash
ultra banner
```

The logo appears automatically in interactive terminals. Use `ultra --no-banner doctor` to hide it for one command, or set `NO_COLOR=1` to disable colors. Redirected output and CI runs stay free of the automatic banner.

### Run the one-shot workflow

After installation, run one of the `ueu create` examples above. Authorized existing
assets and reviewed sidecars are discovered automatically; available permitted
downloads require no manual assembly. A missing grant or unreviewed action boundary
is recorded in the job's `REPORT.txt` and JSON evidence. See the [setup and annotation
contract](docs/AUTONOMOUS_WORKFLOW.md) to register actual evidence once.

Outputs live under `output/jobs/JOB_DIRECTORY/ATHLETE-DURATIONs/`. The cleanly named
MP4 is accompanied by `delivery.json`, `verification_report.json`, `edit_plan.json`,
`music_tracklist.json`, a thumbnail, storyboard and YouTube metadata. The job root
holds `manifest.json`, `REPORT.txt`, source reports and resumable caches.

Disk checks preserve the normal **12 GB free-space floor after each estimated heavy
operation**. With only 11 GB free, the job can correctly block before rendering.
It never lowers the floor or deletes personal media or previous finals.

### Existing explicit-input workflow

Add athlete-named footage to `library/videos/`, for example `Cristiano_Ronaldo_2008.mp4`. Add music to `library/music/hip-hop/`, `reggaeton/` or `funk-brasileiro/`.

```bash
# Inspect the action selection and reports before rendering.
ultra create "Cristiano Ronaldo 30 min hip-hop" --dry-run

# Render with the same inputs.
ultra create "Cristiano Ronaldo 30 min hip-hop"
```

The 30-minute example requires enough source actions and music. Choose a shorter duration for a small library. The tool reports insufficient material instead of silently repeating video or music.

For this legacy `ultra create` command, outputs are written under `output/cristiano-ronaldo-1800s/`:

| File | Purpose |
|---|---|
| `montage.mp4` | Final video with mixed audio |
| `thumbnail.jpg` | Actual source frame with a title |
| `storyboard.jpg` | Contact sheet for visual review |
| `edit_plan.json` | Exact source and timeline intervals |
| `action_integrity_report.json` | Window preservation, provenance and filler counts |
| `source_report.json` | Source paths, fingerprints, music and analysis details |
| `render_report.json` | Export duration, dimensions and audio status |
| `youtube_metadata.json` | Prepared title, description and tags |

`--dry-run` writes the plan and source/integrity reports. It still probes inputs and scans footage, but skips MP4/music rendering and uses a synthetic beat grid. The final render can therefore choose a different action order based on the real soundtrack.

## Commands

| Task | Command |
|---|---|
| One-shot production | `ueu create "Terence Crawford, R&B 2000s, 30 minutes"` |
| Resume a job | `ueu resume output/jobs/JOB_DIRECTORY` |
| Inspect saved status | `ueu status output/jobs/JOB_DIRECTORY` |
| One-shot options | `ueu create --help` |
| Prepare library folders | `ultra init` |
| Show installed dependencies | `ultra doctor` |
| Boxing edit | `ultra create "Mike Tyson 20 minutes rap US" --sport boxing` |
| Brazilian funk football edit | `ultra create "Ricardo Quaresma 30 minutes funk do brasil" --sport football` |
| Require annotation files | `ultra create "Ronaldo 5 min hip-hop" --strict-actions` |
| Load an explicit project | `ultra create --spec examples/ronaldo.yml` |
| Inspect all options | `ultra create --help` |

Select tracks explicitly to control their order:

```bash
ultra create "Naoya Inoue 10 minutes j-pop" \
  --music library/music/j-pop/song1.mp3 \
  --music library/music/j-pop/song2.mp3
```

In the legacy explicit-input CLI, `--repeat-music` permits looping the playlist and `--allow-repeat` permits reusing source intervals. Both are disabled by default and are not exposed by the one-shot command. One-shot production adds sampled perceptual duplicate checks across sources and on the final video; alternate angles, crops and events between samples can still escape detection.

## Action annotations

Put annotations beside a source as `Cristiano_Ronaldo_2008.actions.json`, or in `library/annotations/Cristiano_Ronaldo_2008.json`:

```json
{
  "provenance": "visual_review",
  "events": [
    {"start": 115.0, "peak": 122.6, "end": 136.0, "label": "dribble_shot_goal"},
    {"start": 228.5, "peak": 234.2, "end": 245.2, "label": "run_and_cross"}
  ]
}
```

Times are seconds from the start of the source. Imported windows receive up to 0.5 seconds of padding; overlapping windows are merged. Music alignment affects selection and ordering, never a cut inside the selected window.

The example provenance must describe an actual review. The one-shot job requires explicit accepted provenance and blocks unreviewed candidates. Optional `source_sha256` binds evidence to source bytes. Fine `.shots.json` files add safe margins, protected cores, intro/outro tags and `audio_intent`; see [the editorial schema](docs/EDITORIAL_WORKFLOW.md).

Legacy `--strict-actions` requires annotation files and also accepts SoccerNet-style predictions. It does **not** turn predicted context into verified ground truth. No unreviewed duration filler is used by default.

See the [action policy](docs/ACTION_POLICY.md) for reliability levels and the [technical workflow](docs/WORKFLOW.md) for the SoccerNet schema. A specialist spotting model and weights are not bundled.

### Optional visual ranking

With [Ollama](https://ollama.com/) running locally:

```bash
ollama pull qwen3-vl:2b
ultra create "Cristiano Ronaldo 30 min hip-hop" --semantic-model qwen3-vl:2b
```

The model ranks sampled still frames; it does not reliably identify athletes or establish complete action boundaries. `--semantic-limit 0` examines every candidate. `--scene-detect` adds a separate full-resolution scene scan. `--beat-engine librosa` selects the slower beat tracker; the default transient detector uses FFmpeg and NumPy.

### Explicit URL input

```bash
ultra create "Ronaldo 5 min hip-hop" \
  --source 'https://example.org/rights-cleared-clip.mp4' \
  --allow-download --rights-confirmed
```

Use `--music-source URL` for authorized audio URLs in this explicit-input CLI. Its downloads are restricted to the URLs supplied, cached by URL and retain request order. `ueu create` separately performs catalogue discovery and authorized acquisition from the athlete/style request.

For repeatable projects, edit [`examples/ronaldo.yml`](examples/ronaldo.yml). Manifest paths resolve relative to the YAML file. The example points back to the repository's `library/` and `output/` directories; replace its placeholder media paths with your files.

## Optional YouTube publishing

1. Enable YouTube Data API v3 in your Google Cloud project and create an OAuth **Desktop** client.
2. Save its JSON as `~/.config/youtube-edit-ultra/client_secret.json`.
3. Upload with your account:

```bash
ultra publish output/cristiano-ronaldo-1800s/montage.mp4 --privacy private
```

`private` is the default. Choose `--privacy unlisted` or `--privacy public` explicitly when ready. `ultra create ... --publish private` can upload immediately after rendering.

Successful upload IDs are stored in `montage.youtube.json` to prevent duplicate submissions of that path. Re-running `publish` after success returns the saved video; it does not change that video's visibility. Verify uploads in YouTube Studio before retrying an interrupted upload that has no saved ID. Google project restrictions and Content ID can affect availability; requested visibility is not a guarantee of public publication.

## Limits that matter

- The scanner finds movement candidates, including possible camera pans, graphics and replays. No measured goal/KO recognition accuracy is claimed.
- The integrity report verifies planned window boundaries. It cannot establish whether the source annotations cover the real beginning and end of every action.
- Exact duration plus whole actions can be impossible even when total footage is long enough. Add usable windows or adjust the target duration.
- Accessible media is not automatically reusable. Permissions and commercial scope need evidence; neither the programme nor a green quality report guarantees monetization.
- Finalization checks full decode, requested geometry/fps, duration within 0.15 s, decoded frames within one frame, stream timestamps, black/freeze/silence flags and true peak ≤−1 dBTP. Audio-only correction preserves encoded video packets. Other defects and incomplete duplicate scans block delivery.
- Long H.264 renders consume CPU time and disk space. Streaming export avoids per-shot MP4 copies; analysis caches and optional model data still occupy storage. Exact duration plus protected actions can also exhaust the bounded planner search.

## Démarrage en français

Clone le dépôt, lance `bash scripts/bootstrap_mac.sh`, puis active `source .venv/bin/activate`. Lance `ueu create "Terence Crawford — R&B 2000s — 30 minutes"`. Le programme orchestre le parcours et livre un MP4 vérifié, ou explique le blocage. Les permissions et limites d'actions réellement revues restent nécessaires; aucun accès public ne les remplace.

`ueu resume CHEMIN_DU_JOB` reprend les étapes vérifiées après interruption. `ueu status CHEMIN_DU_JOB` affiche l'état. Les vidéos et rapports se trouvent dans `output/jobs/`. Le plancher disque reste à 12 Go; aucune publication n'est automatique.

## Development

```bash
python -m pip install -e '.[dev]'
python -m ruff check --select E9,F src tests
ueu --help
python -m pytest
```

FFmpeg is required for the media integration tests. CI runs Python 3.11, 3.12 and 3.13, Ruff E9/F and the installed `ueu` entry point. Real short synthetic exports test one-shot delivery, interruption/resume, audio intent, clipping recovery with unchanged video packets, duplicates and quality failures. HTTP/provider, Ollama and disk conditions are simulated where relevant; these tests do not demonstrate live provider availability or semantic boxing recognition. Existing Crawford V2 media remains unchanged.

[Technical workflow](docs/WORKFLOW.md) · [Action policy](docs/ACTION_POLICY.md) · [Maintainer publishing notes](docs/GITHUB.md) · [Third-party components](THIRD_PARTY.md)

**License:** [MIT](LICENSE), copyright Benjamin Da Cunha. Input media and third-party dependencies retain their respective rights and licenses.

Historical production evidence, restored components and real-media acceptance: [legacy execution diagnosis](docs/LEGACY_EXECUTION_DIAGNOSIS.md). The real-media demonstration is 16 seconds; synthetic tests and this demo do not certify KO recognition or a 30-minute production.

Historical long-form evidence and its review limits remain in [production validation](docs/PRODUCTION_VALIDATION.md) and the project journal. Agent-driven past exports do not establish that every new athlete/style request can run without missing rights, action review or adequate storage. See [current workflow and test boundaries](docs/AUTONOMOUS_WORKFLOW.md).

Implementation evidence: [one-shot audit](docs/ONE_SHOT_AUDIT.md) · [executed checks and limits](docs/ONE_SHOT_VERIFICATION.md).
