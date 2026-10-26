<div align="center">

# YouTube-Edit-Ultra

### One prompt. Your athlete. Your music. Your duration. A complete sports montage.

**Sport first. Music second. Never cut the goal, knockout, combination or celebration just to hit a beat.**

[Getting started](#quick-start) · [How it works](#sports-first-editing) · [YouTube publication](#youtube-publishing) · [FR](#démarrage-en-français)

</div>

---

> **The pitch:** “Cristiano Ronaldo · 30 minutes · American hip-hop” → local source discovery → source analysis → action-safe timeline → music mixing → export `montage.mp4`, `thumbnail.jpg`, YouTube title/description/tags → **optional** YouTube publication.
>
> After one-time setup and adding footage/music to your library, no timeline editing is required.

## Inspiration: the kind of edits this project targets

<p align="center">
  <a href="https://www.youtube.com/watch?v=Yq7Yy8H5J-8"><img src="https://img.youtube.com/vi/Yq7Yy8H5J-8/hqdefault.jpg" width="46%" alt="Cristiano Ronaldo 2007–08 dribbling, skills and runs — YouTube video" /></a>
  <a href="https://www.youtube.com/watch?v=j6FpcvSor8g"><img src="https://img.youtube.com/vi/j6FpcvSor8g/hqdefault.jpg" width="46%" alt="Cristiano Ronaldo Unstoppable — skills and goals music video" /></a>
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=Yq7Yy8H5J-8">Ronaldo 2007/08 — Skills/Runs (Teo CRi, 13M+ views)</a> · <a href="https://www.youtube.com/watch?v=j6FpcvSor8g">Ronaldo — Unstoppable / Sia (10M+ views reported)</a>
</p>

Use those public YouTube videos as **visual and pacing references**. The images are linked YouTube thumbnails, not included source footage; view counts reflect publicly reported figures and can change. **This project does not download or redistribute example videos by default.**

## What is included

| Stage | Feature |
|---|---|
| Input | One natural-language prompt, local footage/music library or explicit source URLs |
| Acquisition | Optional `yt-dlp` for **specific, rights-cleared video and music URLs**; no browser tokens/cookie extraction |
| Sport recognition | Scene/motion analysis; optional PySceneDetect; sport-specific lead-in/follow-through; optional local Qwen3-VL scoring; SoccerNet-style predictions or precise action annotations |
| Music | Fast FFmpeg/NumPy transient map by default, optional `librosa` beat tracking, soundtrack playlist and crossfades |
| Editing | **Atomic action protection**: an event is never shortened to match the soundtrack, including buildup and aftermath |
| Sound | Music plus preserved stadium/crowd/ring audio, lower in the mix |
| Video | Natural colors, original 1× speed, original athlete, H.264 16:9 / configurable output |
| Publish | Local MP4, thumbnail and metadata **by default**. OAuth resumable YouTube upload only when requested |
| Reports | `edit_plan.json`, `action_integrity_report.json`, `source_report.json`, `render_report.json` |
| Costs | Runs locally; optional Ollama model is local; no paid editing API is mandatory |
| Safety | No song-content fingerprint evasion, no Content ID bypass, no implicit public uploads |

### Sports supported

**Football:** buildup → dribble → shot/pass → goal/save → celebration. The planner prefers complete sequences to aggressive cuts. It can import action-spotting events exported in SoccerNet-style JSON for goal, shot, foul, etc.

**Boxing:** entry → jab/cross/combination → knockdown/defense → referee reaction. Nearby action windows are joined rather than cut mid-exchange.

Presets also exist for MMA, basketball and generic sports. Sports detection alone is **not** equivalent to knowing the athlete's identity or guaranteeing every action is complete; see the accuracy note below.

## Quick start

**macOS** (also works on Linux with FFmpeg):

```bash
brew install ffmpeg python@3.12 gh          # macOS; install your system equivalents on Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[all]'
ultra init
ultra doctor
```

On Mac, `./scripts/bootstrap_mac.sh` performs the installation automatically.

Place your video files under `library/videos/` (include the athlete's name in the file name, e.g. `Cristiano_Ronaldo_2008.mp4`) and music under a genre folder, such as `library/music/hip-hop/`.

Then run:

```bash
ultra create "Cristiano Ronaldo 30 minutes hip-hop"
```

Output:

```text
output/cristiano-ronaldo-1800s/
├── montage.mp4
├── thumbnail.jpg
├── storyboard.jpg               # source-frame contact sheet for QA
├── youtube_metadata.json
├── edit_plan.json
├── action_integrity_report.json
├── source_report.json
└── render_report.json
```

No posting happens unless you explicitly add `--publish` or run `ultra publish`.

### Concrete examples

```bash
# 30-minute Ronaldo music mix (music & footage already in local library)
ultra create "Cristiano Ronaldo 30 min hip-hop" --semantic-model qwen3-vl:2b

# Mike Tyson — boxing combinations with conservative long actions
ultra create "Mike Tyson 20 minutes rap US" --sport boxing

# Quaresma x Brazilian funk — export locally, with NO mid-goal cuts
ultra create "Ricardo Quaresma 30 minutes funk do brasil" --sport football

# Inoue x J-pop (individual music files explicitly selected)
ultra create "Naoya Inoue 30 minutes j-pop" --music "library/music/j-pop/song1.mp3" \
  --music "library/music/j-pop/song2.mp3" --repeat-music

# Optional publication (authorizes YouTube OAuth; see instructions below)
ultra create "Marcos Maidana 30min reggaeton" --publish private

# Plan only: show chosen actions and verify cuts WITHOUT rendering MP4
ultra create "Cristiano Ronaldo 30 min hip-hop" --dry-run
```

`--repeat-music` is explicit because duplicating songs should never happen silently. Repeating video actions is disabled unless `--allow-repeat` is requested; by default, footage that is too short yields a clear error.

## Sports-first editing

```text
              ATHLETE / SPORT / MUSIC / DURATION
                              |
                  LIBRARY + EXPLICIT SOURCES
                              |
             FFmpeg / optional yt-dlp ingest
                              |
                   Sports footage analysis
          ┌───────────────────┼────────────────────┐
    low-res motion      scene detection      athlete-specific
    + cut candidate     (PySceneDetect)      action timestamps
                                              (SoccerNet/JSON)
          └───────────────────┼────────────────────┘
                              |
             OPTIONAL Ollama Qwen3-VL tagging
                              |
      ATOMIC EVENT WINDOWS (buildup/impact/resolution)
                              |
             Music beats, segments, crossfades
                              |
                ACTION-FIRST EDIT PLANNER
       score alignment; NEVER split an event window
                              |
       FFmpeg renders exact event windows at 1× speed
                              |
       Mix natural ambience + music; thumbnail; metadata
                              |
                     LOCAL MP4 (default)
                              |
                YouTube OAuth (optional only)
```

Most beat-only editors make cuts on **every musical transient**. For sports, the creative constraint is different:

1. **Preserve full events.** Dribbles must reach the shot; combinations must show the continuation; goals must retain the outcome. Annotated event windows are immutable.
2. **Align impacts, not mid-action cuts.** Select an event order whose key moments land near musical beats where possible; otherwise preserve the action instead of forcing perfect beat alignment.
3. **Retain sports atmosphere.** Original commentary, punches, ball contact and crowd sound can sit beneath the soundtrack.
4. **No invisible recycling.** Avoid duplicate goals, the same replay, or the same insertion repeated throughout the edit.
5. **No face/body regeneration.** Only actual source frames are used, with natural framing and a source-derived thumbnail.

### Accuracy and integrity (important)

The default scanner uses **motion, cuts and broad context windows**. It is an efficient *candidate finder*, not a fully trained goal/knockout detector. It cannot know with certainty whether a football move finished in a goal, which boxer hit, or whether a true action began before its detected peak. On broadcast footage, replays, camera pans and crowd reactions can trigger false candidates.

For much stronger action integrity, annotate actual action boundaries:

`library/annotations/Cristiano_Ronaldo_2008.json`:

```json
{
  "events": [
    {"start": 115.0, "peak": 122.6, "end": 136.0, "label": "dribble_shot_goal_celebration"},
    {"start": 228.5, "peak": 234.2, "end": 245.2, "label": "run_and_cross"}
  ]
}
```

Use `--strict-actions` to **forbid heuristic events** when all genuine action boundaries must be verified. The planner never cuts the specified windows. This protects annotated bounds; it cannot validate incorrect or incomplete human annotations. The report deliberately sets `semantic_completeness_guaranteed: false` for this reason.

### Higher-accuracy local video understanding

Install [Ollama](https://ollama.com/) and the small visual model:

```bash
ollama pull qwen3-vl:2b
ultra create "Cristiano Ronaldo 30min hip-hop" --semantic-model qwen3-vl:2b
```

This local model examines a few still frames per candidate to rank actions versus crowd/graphics. Use `--semantic-limit 0` to tag all candidates (significantly slower). It **does not independently determine reliable action boundaries**. The optional SoccerNet integration accepts externally generated spotting predictions in JSON: the spotting model and pretrained weights are not bundled. See [Action Integrity Policy](docs/ACTION_POLICY.md).

### Explicit URL ingest

```bash
ultra create "Ronaldo 30 min hip-hop" \
  --source 'https://example.org/rights-cleared-clip.mp4' \
  --allow-download --rights-confirmed
```

Audio can also be obtained from an explicitly supplied authorized URL with `--music-source URL --allow-download --rights-confirmed`. Only explicitly listed URLs are downloaded. The owner/user is responsible for rights to source footage and music and for compliance with source services' terms. An artist or music *style* is **not an authorization to download commercial tracks or publish them to YouTube**. Local library inputs make the one-prompt experience possible without hidden credential handling or arbitrary web scraping.

### YAML projects

For more control, start with [`examples/ronaldo.yml`](examples/ronaldo.yml):

```bash
ultra create --spec examples/ronaldo.yml
```

The YAML can list video paths, URLs and per-video annotation files plus an exact music playlist; CLI flags override the main settings.

## YouTube publishing

The default is **local only**. Publishing requires your own YouTube Data API OAuth Desktop client:

1. Enable the YouTube Data API v3 for a Google Cloud project and download an OAuth Desktop `client_secret.json`.
2. Put it at `~/.config/youtube-edit-ultra/client_secret.json` (never commit it).
3. Run `ultra publish output/<project>/montage.mp4 --privacy private` to sign into your own account once.
4. When ready, use `--privacy unlisted` or `--privacy public` for a new upload, or `ultra create ... --publish public`.

YouTube API projects created after July 28, 2020 that have **not passed YouTube's compliance audit** may be forced to upload videos as **private**, even if `public` is requested. The tool never claims that an upload is public without checking YouTube Studio. Content ID copyright claims/blocking and music licensing remain applicable. Publishing is an explicit choice, not mandatory.

The uploader stores returned video IDs in `montage.youtube.json` to avoid duplicate posts when invoked again after a successful upload. If a network failure occurs before Google returns an ID, manual checking in YouTube Studio may still be necessary before retrying.

## Démarrage en français

1. Dépose tes **vidéos sources** dans `library/videos/` avec le nom du sportif dans le fichier.
2. Dépose les **musiques autorisées** dans `library/music/hip-hop/`, `library/music/reggaeton/`, etc.
3. Lance `ultra create "Cristiano Ronaldo 30 minutes hip-hop"`.
4. Récupère `montage.mp4`, `thumbnail.jpg`, `storyboard.jpg`, `edit_plan.json`, les rapports d'intégrité et les informations YouTube dans `output/`.
5. Si tu souhaites publier, utilise `--publish private|unlisted|public` avec ton compte YouTube connecté.

**Priorité absolue : l'action sportive.** En cas de conflit entre une coupe musicale et la fin d'un but, d'un KO ou d'un enchaînement, le programme privilégie la fin de l'action. Si la bibliothèque contient trop peu de matière, il affiche une erreur au lieu d'inventer ou de répéter des actions.

## Quality / limitations

- Designed for local macOS (including Apple Silicon) and Linux, on CPU, with FFmpeg and Python 3.11+. A 30-minute H.264 montage can take substantial disk space and processing time.
- `--semantic-model` requires a running local Ollama model, `--beat-engine librosa` may incur slow initial numba compilation, and optional `--scene-detect` repeats a full decode.
- Beat alignment optimizes approximate event impacts, **not** every cut at every beat; sports integrity wins.
- Accurate athlete identification, multi-player tracking, true goal/KO classification and match-wide event recall require a specialist pre-trained detector plus valid ground truth; they are **not guaranteed** by the included heuristic code.
- Fully automated production of named-athlete music mixes needs a **pre-authorized source library**. No software can conjure licensed source footage and songs from only a name without additional access or rights.
- No third-party AGPL sources are vendored; see [third-party components and license notes](THIRD_PARTY.md). Runtime tools retain their own licenses.

## Contributing / tests

```bash
pip install -e '.[dev]'
pytest -q
```

To publish this source repository to your GitHub account, run [`scripts/publish_github.sh`](scripts/publish_github.sh) after `gh auth login`; details in [`docs/GITHUB.md`](docs/GITHUB.md).

See [`docs/WORKFLOW.md`](docs/WORKFLOW.md), [`docs/ACTION_POLICY.md`](docs/ACTION_POLICY.md), and the ready-to-use [Claude Code skill](.claude/skills/youtube-edit-ultra/SKILL.md).

**License:** MIT for this project's original source files. Dependencies, example video thumbnails and input media retain their respective rights and licenses.
