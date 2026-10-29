# Production validation — 29 October 2026

**Status: NOT_VALIDATED_30MIN.** No new 30-minute sports export was produced. Passing code tests and a successful acquisition do not establish complete sporting actions, musical coherence or editorial quality.

## Executed corrections

- Discovery and downloads use the active Python environment's `yt_dlp` module, falling back to PATH only when the module is absent. On the audited Mac, this selects version 2026.10.21 instead of the global 2026.07.04. `doctor` displays the selected command and version.
- A genre-only request can use authorized local audio when an optional saved Spotify association is unavailable. Explicit playlist requests remain strict. Reports never claim Spotify membership for local fallback.
- The home directory name no longer identifies an athlete. File metadata and paths below that directory remain candidate evidence, not visual verification.
- Preflight reports technical availability separately from reuse evidence and editorial coverage. Insufficient raw authorized video or eligible music duration is reported before starting a render.

The earlier uncommitted orchestrator, catalogue, authenticated Spotify pagination, history imports, direct-media download, loudness measurement and shared agent instructions are included in this implementation. It reuses the existing `create` engine.

## Real execution

An exact source permission recorded by the user on 21 October was recovered from the older source review. `ultra produce "Mike Tyson 30 minutes hip-hop"` acquired that source with the normal downloader. The resulting interview is 62.974 seconds, 3840×2160 at 50 fps (the source advertises upscaling), 47,766,469 bytes. Full FFmpeg `-xerror` decode completed with exit code 0. SHA-256: `deb5aa5f0d30c6491129ff7635847cd0cfc0f65aa33ab1b585c7b51d5ae8044b`.

The old journal recorded a 403 on this source. The current acquisition succeeds; the changed downloader version alone is not proven to explain the server's earlier response. A second production run reused the authorized local copy. Three public discovery queries returned 29 distinct candidates without search errors; those results do not grant reuse permission.

The 30-minute attempt blocks: only 62.974 seconds of authorized raw video, all from an interview, and no eligible authorized hip-hop soundtrack. The raw shortfall is 1,737.026 seconds; verified sporting-action coverage has not been established at all. No new short demonstration was presented as validation.

## What remains inaccessible or unestablished

The current inventory found no audio/video files inside the three old Maidana, Latino and Haaland projects. Their selected preserved manifests reference respectively 575, 42 and 50 missing absolute media paths, including intermediate windows, mixes and exports. These are reference counts, not counts of distinct fights or downloadable originals.

Long local combat files and 51 hip-hop MP3s remain elsewhere. Twelve of the MP3 title families occur in the accessible usage history; 39 do not. Absence from that partial history is not proof of never-used status. Their reuse permissions have not been established. A missing permission record is separate from technical accessibility and does not establish that permission could never be obtained.

Canelo's existing full-fight source is technically accessible (3,823.978 seconds); no reuse grant was located. No local reggaeton audio matched the style inventory. The optional Spotify connection now yields a warning, not the production blocker. For an explicitly requested Spotify playlist, authenticated complete membership verification is still required.

## Required next resources

1. For existing local combats, obtain or recover the applicable permission from the recording owner/broadcaster, including the intended editing/use scope. Record that evidence once against the existing files; no redownload or manual library preparation is needed.
2. For the music, obtain an authorized file and permission covering the intended montage use, or identify such evidence for the existing files. Select enough nonrepeated eligible audio to cover 1,800 seconds after crossfades. A Spotify reference or a locally present MP3 is not that evidence.
3. For deleted originals, restore from an accessible backup, or obtain the original through the rights holder's authorized delivery/download route. Retained manifests supply source URLs and time ranges, not the missing bytes. No access restriction should be bypassed.
4. After those inputs become accessible, inspect identity, full action boundaries and perceptual duplicates, render, decode the entire export and review its transitions, mix, thumbnail and metadata. Raw source duration alone cannot satisfy this gate.
5. Spotify-only setup, when requested: use an owned Developer app, register `http://127.0.0.1:8769/callback`, provide its public Client ID, and consent via `ultra spotify login/finish`. No client secret is needed. Local genre-based production does not depend on this step. See [official PKCE documentation](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow).

## Evidence boundary

The local audit bundle is `output/final-validation-20261029/`: exact inventories and missing paths, source permissions and ffprobe/decode results, real blocked production reports, Spotify setup details and test logs. Media, tokens and native session archives are not published in this repository.

70 automated tests pass. Targeted E9/F lint on changed code/tests and `git diff --check` pass. Repository-wide E9/F lint still reports six pre-existing unused imports in untouched files. No real 30-minute export, full action validation, perceptual duplicate review or end-to-end Spotify consent has passed in this audit.

See [historical execution diagnosis](LEGACY_EXECUTION_DIAGNOSIS.md) for the exact old scripts, executed commands, native result locations and proxy/HD, soundtrack and FFmpeg mechanisms. Proxy-to-HD planning, editorial music ranking and automatic semantic action verification are still not fully restored by the CLI.
