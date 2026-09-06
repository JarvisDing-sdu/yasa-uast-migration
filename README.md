# YASA UAST Migration Workspace

This workspace isolates the Go and Python UAST migration from the Code Scanner application.

`engine/` and `uast/` are Git submodules pinned to official upstream commits. Changes remain focused in their respective repositories so they can be prepared as upstream pull requests.

## Baseline

- `engine/` is pinned to official upstream `249420d`.
- `uast/` is pinned to official upstream `07e3823`.
- The prior local Engine baseline, including C support changes, is preserved in local branch `migration/local-engine-baseline` at `1012bbc`.
- Legacy parser binaries stay outside this workspace and are used only for compatibility baselines.

## Local Setup

Copy `config/local-tools.env.example` to `config/local-tools.env` and adjust paths if necessary. The local file is ignored and must not be committed.

## Layout

- `engine/`: YASA-Engine source and Engine-side integration tests.
- `uast/`: YASA-UAST source; Go/Python parser implementation belongs here.
- `fixtures/`: small source fixtures and golden UAST JSON added during migration.
- `scripts/`: reproducible regression and benchmark commands.
- `docs/`: compatibility notes and experiment results.
