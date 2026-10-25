# YASA UAST Migration Workspace

This workspace isolates the Python UAST migration from the Code Scanner application and
the follow-on DL cross-language research work.

`engine/` and `uast/` are Git submodules pinned to commits in the separately
maintained `JarvisDing-sdu/yasa-engine` and `JarvisDing-sdu/yasa-uast`
repositories. Each repository has its own `main` branch and history.

## Repository structure

```text
JarvisDing-sdu/yasa-uast-migration     public integration workspace
├── engine/ -> JarvisDing-sdu/yasa-engine (submodule)
└── uast/   -> JarvisDing-sdu/yasa-uast   (submodule)

JarvisDing-sdu/yasa-dl-cross-language private independent research repository
```

The integration repository pins exact component commits. Updating a component
therefore requires two commits: first push the component repository, then update
the corresponding submodule pointer here. The former special component branches
in this repository are retained only as recoverable history and are no longer
the active submodule remotes.

## Local Setup

Copy `config/local-tools.env.example` to `config/local-tools.env` and adjust paths if necessary. The local file is ignored and must not be committed.

## Layout

- `engine/`: YASA-Engine source and Engine-side integration tests.
- `uast/`: YASA-UAST source; Go/Python/C parser implementation belongs here.
- `workstreams/yasa-python-migration/`: parser migration documents, baseline scripts and reports.
- `workstreams/yasa-c-extension/`: C language support design, C benchmark, Juliet/CASTLE evaluation.
Private DL cross-language research remains physically available under the local
`workstreams/dl-cross-language-research/` directory, but is deliberately Git-ignored by this
public repository and managed by its own private repository.

See [workstreams/README.md](workstreams/README.md) for the public ownership boundary.

## Public repository boundary

Private workstream files and `.env` credentials must never be added to this
repository, including with `git add -f`. Enable the local commit/push guard after
cloning:

```bash
git config core.hooksPath .githooks
```

The guard checks the index and proposed pushed tree. It does not erase files
from old commits, and local hooks do not replace a review of staged changes.
