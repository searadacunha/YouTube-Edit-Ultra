# Reconstruction and recovery evidence — 2026-10-29

The old workflow was a collection of project scripts plus human/agent selection and review, not an already complete generic one-command service.

| Stage | Existing evidence | Reused approach |
|---|---|---|
| Public discovery | `../Marcos-Maidana-Reggaeton/scripts/search_sources.py`, `../Latino-Boxing-Kings/scripts/find_sources.py`, `../Haaland-Ragnar/scripts/find_sources.py` | yt-dlp `ytsearch`, metadata, bounded cached search |
| Acquisition | Each project's `scripts/download_sources.py`; Haaland/Maidana `download_hd.py` | yt-dlp, retained provenance, explicit failures, disk checks; existing Ultra download helpers |
| Music discovery | Maidana `scripts/music_search.py`, `download_music.py`, `inventory_music.py` | YouTube Music search and local inventories historically; new production only uses documented permission, never assumes an official upload grants reuse |
| Musical analysis | Latino `scripts/analyze_audio.py`; Haaland `scripts/analyze_audio.py`; `../Boxing-Tubeviz/remix_hiphop90s.py` | FFmpeg, transient/beat analysis, finite nonrepeating soundtrack |
| Assembly/review | Maidana `scripts/edit.py`, Latino `scripts/edit_full.py`, Haaland `scripts/render.py`, `verify.py` | Existing Ultra planner/renderer, source windows at original speed, metadata and source-derived images |
| Source honesty | Latino `scripts/download_sources.py:69`, Haaland `scripts/manifest.py:38` | Historical manifests explicitly did not infer a publication licence from a public download |

Historical sources were inspected, not executed or modified. Music histories are imported from actual timeline/mix/source-report formats, not candidate libraries; no assertion that every earlier upload is covered. Former versions are conservatively excluded too.

## Why the media are missing

`~/FILE_INDEX.md:354-368` records authorized cleanup on 26 October: Trash emptied through Finder, then 793 old media/cache/contact-sheet files and finished-project music libraries removed. The preserved manifest is `~/Documents/Systeme/sauvegardes/cleanup_old_videos_20261026.txt`. Later entries record permanent deletion of Flavio and Quaresma projects. A deleted source path in an old timeline is not an available media file.

Read-only checks on 29 October: `~/.Trash` was empty; `tmutil destinationinfo` returned `No destinations configured`; `tmutil listlocalsnapshots /` listed three macOS update snapshots and no ordinary dated Time Machine snapshot. Those system snapshots are not evidence of recoverable personal video files. No restoration, Trash modification, purge, external-volume mounting or low-level recovery was attempted. External/offline backups and original licensed downloads may still be available, but were not established.

The initial live catalogue scan accidentally included retained synthetic pytest fixtures. A `.ultra-ignore` marker now excludes them. The initial catalogue is preserved as `~/.local/share/youtube-edit-ultra/catalogue.before-test-exclusion.json`; a clean rescan found 129 audio/video files, 154 historical track occurrences across 22 recognized files, zero scan errors. Counts are a dated observation, not a permanent guarantee.

Real public search for Canelo returned five candidates, including DAZN and Netflix Sports. All five had an absent licence field, so none was downloaded. Live evidence: `output/produce-live-validation/20261029-102702-491000/discovery_report.json`. One existing Mayweather-Canelo full fight is 720p25, but reuse permission was not documented. No source was marked authorized merely because an earlier project used it.
