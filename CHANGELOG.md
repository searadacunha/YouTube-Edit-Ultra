# Changelog

Notable repository changes, not a promise of release packaging or production acceptance.

## Unreleased — 2026-10-31

### Added

- `ueu documentary --spec`: spec-driven voice-over, script-aligned subtitles, footage/card/split compositions, evidence ledger, shot/narration alignment and technical reports. The MLX voice runtime is an external Apple-Silicon setup.
- `--stage plan`, short `--preview` exports and optional proxy layout renders for documentary projects.
- `ultra insert-image`: short silent H.264 still-image inserts with a provenance sidecar, not automatically approved annotations.
- `documentary` optional dependency for `pysubs2` in the main package.
- Optional YouTube `containsSyntheticMedia` disclosure via `synthetic_media` in upload JSON metadata.

### Changed

- Updated disk-guard configuration/script lookup to user configuration paths.
- CI now installs the documentary extra while continuing Python 3.11–3.13 testing.
- Documentation distinguishes checkpointed sports highlights, explicit-input edits and spec-driven documentaries; adds a card-only YAML starter.

### Scope and limitations

- Documentary source preparation, review proxies, matched HD windows, rights evidence and consented/synthetic voice references remain external prerequisites.
- Local QC is technical, not proof of accurate boxer identification, complete action recognition, artistic approval, copyright permission or monetization.
