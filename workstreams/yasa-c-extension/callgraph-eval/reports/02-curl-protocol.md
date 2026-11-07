# Large C callgraph benchmark protocol

Project: complete configured libcurl library, fixed source SHA and CMake configuration. User Engine at merged main e2f89d9, CodeGraph released v1.6.2.

Inputs are the actual libcurl translation units plus project headers and generated configuration headers, preserving original relative paths. CLI/tests/examples and third-party dependency implementations are excluded. Both analyzers receive the same source tree. Yasa receives the build target defines/include paths via its supported C preprocessing options; unsupported build options and potential differences must be recorded. CodeGraph uses its normal source indexing interface. No analyzer algorithms will be changed to improve this run's results.

Reference compiler covers every eligible TU. All internal definitions and direct edges are collected before checking predictions, including symbols either analyzer misses. Canonical identities retain source file and function name, resolving external prototypes to compiled definitions, keeping same-named static definitions distinct. System/dependency functions are external and inventoried rather than counted as project definitions.

Primary metric is direct-call resolution on active compiler-known direct callsites. Correct synthesized indirect edges must not count as direct false positives: compiler-known indirect sites are a separate frame. Sites on lines with both direct and indirect calls are matched by columns where reliable, otherwise excluded with counts. Report compiler coverage, evaluable frame size and omitted/unknown/unattributable predictions explicitly. Report deduplicated internal function-pair precision/recall and callsite-level counts separately where attribution supports it. Extra targets in inactive configuration are documented separately.

Indirect-call quality is measured only on an analyzer-blind curated set of real internal callback sites, supported by source registrations/assignments and build activation. Caller-supplied external callback universes are not falsely treated as complete internal gold. Freeze this subset before reading predictions; never label its recall as overall indirect recall.

Keep all versions, raw outputs, compiler commands, score scripts, mismatches and logs. Time actual runs; only compare elapsed performance if hardware workload/setup/order are stated and serial runs have no concurrent reference/build workload. Real application scalability (completion/failure/resource issues) is part of observed results.
