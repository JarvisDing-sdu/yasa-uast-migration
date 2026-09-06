# YASA UAST Migration Workspace

This workspace isolates the Go and Python UAST migration from the Code Scanner application.

`engine/` and `uast/` are independent upstream Git clones so changes can be prepared as focused upstream pull requests. They intentionally remain separate repositories rather than nested copies.

## Baseline

- `engine/` is on `migration/local-engine-baseline`, based on upstream `d4f31f6` with the existing local Engine changes applied as an uncommitted working tree.
- `uast/` is on `migration/local-engine-compatible`, based on `v0.2.13`, matching the Engine's parser package dependency range.
- Legacy parser binaries stay outside this workspace and are used only for compatibility baselines.

## Local Setup

Copy `config/local-tools.env.example` to `config/local-tools.env` and adjust paths if necessary. The local file is ignored and must not be committed.

## Layout

- `engine/`: YASA-Engine source and Engine-side integration tests.
- `uast/`: YASA-UAST source; Go/Python parser implementation belongs here.
- `fixtures/`: small source fixtures and golden UAST JSON added during migration.
- `scripts/`: reproducible regression and benchmark commands.
- `docs/`: compatibility notes and experiment results.
