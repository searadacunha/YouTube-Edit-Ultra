---
name: youtube-edit-ultra
summary: Automated sport-first 16:9 music montage creation with optional YouTube upload.
---

# YouTube-Edit-Ultra (Claude Code)

When the user says "fais un mix de Cristiano Ronaldo 30 minutes sur du hip-hop", use this local repository; avoid hand-coded one-off editing scripts.

1. Check `ultra doctor`. If missing, create `.venv`, install `pip install -e '.[all]'`, ensure FFmpeg on PATH.
2. Locate and index appropriately licensed local files under `library/videos/` and `library/music/<style>/`. Do not claim they exist without checking. Never secretly download copyrighted tracks/footage; use explicitly provided URLs only with consent.
3. Determine athlete, sport, style and duration from request. `ultra create "<user request>"` is the one command. For football and boxing, verify the full buildup, action peak and aftermath. Use known annotations or `--strict-actions` when necessary.
4. To improve automated selection on a local machine with suitable Ollama model, run with `--semantic-model qwen3-vl:2b`. Never pretend a vision-model caption is a precise action boundary.
5. Read `action_integrity_report.json`. Check selected source timestamps, incomplete actions, repeats and enough source diversity. If the user emphasizes fidelity, inspect action boundaries in actual output video before publication.
6. Respect the explicit publishing choice: **no upload by default**. When the user requests a YouTube post, use `ultra publish <mp4> --privacy <status>` or `ultra create ... --publish <status>` after checking OAuth is connected. Verify YouTube API result and explain if API project forces private.
7. Return local MP4, thumbnail, EDL and reports or their paths. Distinguish verified actions from heuristic candidates. Do not falsely claim public publication or copyright clearance.

Do not trim or speed-ramp away real actions merely to align beats. Do not transform athlete faces or physique. Do not repeat the same goal/combo unless explicitly requested. Respect source copyright and third-party software licenses.
