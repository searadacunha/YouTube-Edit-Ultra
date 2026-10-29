# Autonomous local production

`ultra produce "Canelo Alvarez 30 minutes reggaeton"` and `ultra produce "Terence Crawford 30 minutes R&B 2000s"` now orchestrate local discovery, historic exclusions, public search, permitted acquisition, `create` and post-render checks. No publication option is exposed by produce.

## First setup, retained across productions

Use `.venv/bin/ultra` from this checkout (or activate `.venv`). `ultra doctor` checks dependencies. State defaults to `~/.local/share/youtube-edit-ultra/`; `--state-dir` isolates another catalogue.

`ultra catalogue scan` indexes Documents, Music, Movies, Downloads and Desktop. `--root /path` on scan or produce adds a chosen scan scope without moving media. Symlink directories, RuView, Trash, dependency trees and folders containing `.ultra-ignore` are excluded. Scan errors are counted, recorded and never silently replaced with empty measurements. Damaged music-history files block production. The catalogue caches probe metadata by size/mtime and records full SHA-256 hashes. Content changes detected during scanning invalidate previous permission. Modification times are a cache assumption, not tamper detection.

Register the actual reuse permission for a local asset once:

```
ultra catalogue authorize '/absolute/path/file.mp4' --evidence 'Owned footage; permission record /path/to/record'
```

A permission is content-hash-bound, so copies reuse it. No permission is inferred from finding a file. Trusted CC publishers can be configured once in `config.json` as exact channel URLs; unknown publishers are withheld even when they declare CC BY. Metadata/title artist/style come from embedded tags, filenames/folders and adjacent yt-dlp `.info.json` files.

For an authorized download, retain its URL and evidence:

```
ultra catalogue authorize-url 'https://example.org/clip.mp4' --kind video --athlete 'Canelo Alvarez' --title 'Canelo Alvarez licensed bout' --evidence 'Written authorization record ...'
ultra catalogue authorize-url 'https://example.org/song.mp3' --kind audio --style reggaeton --title 'Exact title' --artist 'Exact artist' --evidence 'Licensed audio record ...'
```

Produce reuses yt-dlp for hosted pages and fetches permitted original HTTPS media links directly with curl, validating them with ffprobe. Existing authorized local copies are reused without contacting their media host. When more video duration is needed, public search runs three sport-specific queries (ten results each) plus up to three historical queries, with per-query 24-hour caches and explicit partial errors. Old sources/proxies/search manifests feed discovery without granting permission. Raw source duration does not guarantee sufficient usable actions. A CC BY declaration permits automatic acquisition only if the publisher's channel URL is explicitly listed in `config.json` under `trusted_cc_publishers`; otherwise an exact URL grant is required. Unknown publishers are reported without downloading. `--offline` disables video discovery/acquisition; a requested Spotify playlist still requires the API. See also the [French setup guide](AUTONOMOUS_PRODUCE.md).

## Spotify once, full pagination thereafter

Create/use your own Spotify Developer application and register exactly `http://127.0.0.1:8769/callback`. Spotify account/application access restrictions still apply.

```
ultra spotify login --client-id YOUR_CLIENT_ID
# Open the printed Spotify authorization URL, consent, then copy the final
# callback URL from the address bar (the local page need not load).
ultra spotify finish 'http://127.0.0.1:8769/callback?code=...&state=...'
ultra spotify sync 'https://open.spotify.com/playlist/0k2Chx9ptj4naPruQhmkWz' --style reggaeton
```

The callback expires after ten minutes and its state is checked. PKCE requires no client secret. Tokens and verifier are stored atomically with mode 0600 outside git; refresh tokens are retained and refreshed automatically. Do not paste callback URLs into shared logs or commit them. There is no local callback listener: `finish` completes the initial interactive authorization.

Sync persists the playlist-to-style association. Produce fetches a fresh snapshot via `/v1/playlists/{id}/items`, follows every page, validates the item count and confirms the snapshot did not change. Null, local and non-track entries are counted separately. A partial read or access failure blocks a requested playlist; cached metadata is not silently substituted. URI, artists, title, album, duration, external identifiers, position and original metadata remain in the snapshot. An explicit `produce --playlist URL` overrides the style mapping for that run.

Local audio must have permission and match an exact normalized Spotify title/version and artist credit, with a compatible duration when supplied. For R&B 2000s, the documented release year must fall in 2000–2009. Unmatched or ambiguous tracks are reported, not guessed. Spotify never supplies an MP3 and no stream extraction exists here.

Official references: [PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow), [playlist items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items), [refresh tokens](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens).

## Rendering and evidence

Each run gets a distinct output directory under `output/productions/`. `production_report.json` records roots, blockers and warnings; scan, discovery and exclusion reports remain even when blocked. The generated `project.json` explicitly orders inputs and calls the existing create CLI with no repetition and no publication. Shared analysis and segment caches stay in the persistent state directory, protected by a catalogue lock during production.

Adjacent `video.actions.json` annotations are discovered automatically. `--strict-actions` requires annotations; otherwise existing motion/scene heuristics propose action windows. `--semantic-model` uses the existing optional Ollama ranking. These do not reliably identify an athlete, detect KO outcomes or certify complete actions. Automatic exports always remain `TECHNICAL_PASS_REVIEW_REQUIRED`. Complete action windows in the selected plan are checked, while semantic completeness remains false.

A completed render produces the existing MP4, thumbnail, storyboard, edit plan, source report, integrity report, render report and metadata, plus `music_tracklist.json`, `audio_levels.json`, `verification_report.json` and full FFmpeg decode/quality logs. Verification checks H.264/audio presence, duration within five seconds, audio/video stream starts and end duration alignment, full decode, black/freeze/silence warnings and true audio peak. Timestamp alignment is not proof of musical or punch synchronization. Visual/perceptual duplicates across separate source encodings still need review. The planner's filler segments are disclosed.

Music usage persists after an actual rendered export. Historical timeline imports also conservatively reserve titles from prior versions. Byte hashes and normalized title families reject known reuse/remixes; this is not acoustic fingerprinting and may over-exclude unrelated songs sharing a title. Missing/deleted projects or unknown YouTube uploads prevent a claim of exhaustive history. Tracks are ordered deterministically from the available collection, not ranked by a trained taste/energy model.

Disk reserve before downloads is 2 GB; it does not predict a whole production's size. Codec/resolution/fps default to H.264 1080p30; lower-resolution sources can be upscaled and are reported with their original dimensions. No acquisition/render promise can bypass unavailable media, licenses, Spotify access, insufficient unique footage or insufficient soundtrack duration.

## Agent responsibilities behind one prompt

Read [the executed legacy diagnosis](LEGACY_EXECUTION_DIAGNOSIS.md). A blocked CLI is not the end of the agent's work. Reuse discovered historical URLs and query caches, inspect public source/licence pages and available local evidence, acquire permitted originals, inspect real frames and add action annotations, then resume. Do this without asking the user to locate files or manually populate a library. Request user input only for an indispensable missing account grant, permission or resource that cannot be established from accessible evidence. Never turn an official/public upload into permission by assumption.

`audio_analysis.json` supplies identities only. Join its source paths to an actual timeline before importing usage. Legacy analysis-only exclusions already in a catalogue migrate to `unconfirmed_history` and remain conservatively withheld with that explicit reason; they are not claimed as proven used. Timeline-only evidence is labelled as an export not reverified.

Soundtracks now use the measured static-gain method recovered from the 90s remix (LUFS target −18 with source true-peak ceiling −3 dBTP) before crossfades; the final mix is checked separately. Permission credits are copied into local YouTube metadata when documented.

Real-media acceptance on 29 October: two licensed/public-domain video sources and a public-domain band recording were acquired by produce; the agent annotated them and produced a 16.021-second MP4. See `output/legacy-reconstruction-20261029/real_media_acceptance.json`. This does not validate KO recognition, a 30-minute Canelo production, or complete editorial parity with the older agent-driven projects.

## Comportement vérifié le 29 octobre : accès et permissions séparés

Une demande de genre seule peut continuer avec les fichiers locaux autorisés si Spotify est absent ou inaccessible, même si une playlist de genre avait été mémorisée. Le rapport indique `local_fallback` et `membership_verified=false`. Une playlist explicitement demandée (`--playlist`, URL/URI dans le prompt, ou mention Spotify/playlist) reste obligatoire : aucune substitution silencieuse. Les règles d'exclusion des morceaux connus restent actives dans les deux modes.

`readiness_report.json` distingue fichiers techniquement accessibles, durée brute autorisée, musique admissible après fondus, preuves de permission manquantes et couverture éditoriale non vérifiée. Les durées brutes ne prouvent ni 30 minutes d'actions ni l'absence de replays. Le nom du dossier personnel n'est plus utilisé comme indice d'identité du sportif.

Recherche et acquisition utilisent le module `yt_dlp` de l'environnement Python courant lorsqu'il est installé ; le binaire global n'est qu'un recours. `doctor` affiche la commande et la version réellement choisies. Cela corrige la sélection d'une ancienne version globale ; cela ne garantit pas de résoudre un refus HTTP du fournisseur.
