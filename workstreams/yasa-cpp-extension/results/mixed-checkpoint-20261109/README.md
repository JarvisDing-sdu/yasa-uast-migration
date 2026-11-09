# 2026-11-09 mixed scanning checkpoint

User explicitly requested merging this development checkpoint into main, with future improvements deferred. The entry remains experimental and opt-in. This merge is not a claim that real-project mixed scanning is release-ready.

`summary.json` records the fresh pre-merge checks and today's unchanged legacy baselines. `mixed-score.json` is the exact independent frozen-fixture score object. Scores are confined to those fixtures and do not establish real-project vulnerability precision or recall.

Full compiler output, raw successful and failed scans, source snapshots, CPU/allocation diagnostics and checksums remain preserved outside Git history. All 25,197 regular files in that archive were verified against their SHA-256 index. Existing baselines and gold labels remain unchanged. The 135 MB compressed archive is not added to the repository.

Open blocker: all 15 selected zlib translation units parse, but full dataflow analysis can exhaust the heap. Required library bodies or taint propagation were not removed to obtain a passing result; speculative shared-memory changes were not adopted.
