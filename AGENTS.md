# YouTube-Edit-Ultra — Codex and Claude Code

Read `docs/AUTONOMOUS_WORKFLOW.md` before production. Both agents follow that same contract.

- Use `ultra produce "<athlete> <duration> <music style>"` for autonomous discovery, local catalogue, permitted acquisition, existing rendering engine and output verification. Run `ultra doctor` first.
- State lives in `~/.local/share/youtube-edit-ultra/`; scan Documents, Music, Movies, Downloads, Desktop without copying files. Never touch RuView or Trash. `.ultra-ignore` excludes synthetic fixtures or unrelated trees.
- Local presence, a public URL, an official uploader and Content ID acceptance do not grant reuse permission. Register evidence once with `ultra catalogue authorize` or `authorize-url`. Automatic CC BY acquisition also requires a configured trusted publisher. A licence declaration is not independently verified ownership.
- Spotify is authenticated, paginated metadata only. Never extract audio from Spotify. Use `ultra spotify login/finish/sync`; keep tokens private, out of git and logs.
- Never repeat music or sports actions automatically. Read history exclusions, acquisition warnings, production and verification reports. Incomplete historical coverage is not an assurance of no reuse.
- Automatic motion/scene/vision results are candidates. `--strict-actions` requires annotations. Neither annotations nor a green synthetic test prove correct boxer identity or KO recognition. Inspect actual actions and boundaries before calling an export editorially complete.
- Preserve outputs and media. No automatic publication, deletion, git history rewrite or push. Append verified work, exact evidence, limits and next step to JOURNAL_AGENTS.md.
- Test changes with `.venv/bin/python -m pytest`; use a new `--basetemp` for retained fixtures. Do not run live Spotify authorization or mutate another project's credentials during tests.

- Reprise historique : read `docs/LEGACY_EXECUTION_DIAGNOSIS.md`. On a blocked run, continue source/licence research and real-frame annotation autonomously before requesting a missing resource. Preserve failed-run reports. Analysis-only music records are not proven usage; do not promote motion or a successful test into a verified KO.
- Current acceptance: read `docs/PRODUCTION_VALIDATION.md`. Distinguish technical access from missing permission evidence. A genre preference may fall back to authorized local audio when Spotify is unavailable; explicit playlist requests may not. Use readiness reports to report separate duration deficits. A test count or a successful short-source acquisition never validates a 30-minute production.
