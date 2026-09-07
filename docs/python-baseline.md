# Python UAST Baseline

Date: 2026-09-06

## Official Versions

- YASA-Engine: `v0.3.2` (`249420d`)
- YASA-UAST: `v0.2.18` (`07e3823`)
- Engine runtime: `runtime/yasa-engine-v0.3.2/yasa-engine-linux-x64`
- Python UAST runtime: `runtime/uast-v0.2.18/uast4py-linux-amd64`
- Test interpreter: Python 3.10.12

The runtime binaries are downloaded from official releases and ignored by Git.

## Unit Tests

The official `parser-Python/test/test_compat_keywords.py` suite passed.

| Coverage | Result |
| --- | --- |
| `async` import identifier compatibility | Pass |
| `await` variable compatibility | Pass |
| `async` function name compatibility | Pass |
| Normal `async def` handling | Pass |
| Ordinary Python parsing | Pass |
| Type node identifier serialization | Pass |
| Real syntax-error rejection | Pass |
| Mixed async syntax best-effort handling | Pass |

Result: `8 passed, 0 failed`.

The upstream `run_regression.py` references a `chatbot_backend` fixture that is not present in the public `v0.2.18` checkout, so it is excluded from this baseline rather than reported as a parser failure.

## Source/Binary UAST Equivalence

`scripts/verify_python_uast_baseline.py` parses each source file with both the official Python source parser and the official `uast4py-linux-amd64` binary. It removes only `sourcefile` before structural comparison.

| Input | Source nodes | Binary nodes | Normalized SHA-256 | Equal |
| --- | ---: | ---: | --- | --- |
| Official type-annotation fixture | 886 | 886 | `7354addefad6e02763817d32a284407a5328195578919663bca7025432996397` | Yes |
| xAST `assign_expression_stmt_001_T.py` | 46 | 46 | `048368e8a6cd4efe7cbe390c285680d4c9994c95dba2dbf21f4de2d03c0f99a9` | Yes |

Generated JSON and summaries are stored locally under `artifacts/python-uast-baseline/` and are ignored by Git.

## Engine Smoke Test

The official Engine scanned the official xAST Python case `assign_expression_stmt_001_T.py` with the official Python test rule configuration.

| Metric | Result |
| --- | --- |
| Files analyzed | 1 |
| Findings | 1 |
| SARIF | Generated |
| Data-flow trace | `taint_src -> result -> taint_sink -> os.system` |
| Total time | 612 ms |

The SARIF report is stored locally at `artifacts/smoke-python/report.sarif`.

## Full xAST Python 3 Engine Regression and Performance Baseline

Date: 2026-09-07

This is the migration-before baseline for the official Engine Python xAST regression. It uses the existing external `uast4py` path; no Node.js Python parser has been introduced.

| Input / environment | Value |
| --- | --- |
| xAST branch | `main-forYasaTest` |
| xAST branch commit | `32a74f8dec9dcacfd99a9053ebd8b545a34e09c7` |
| Prepared input | `engine/test/python/benchmarks/sast-python3/case/` |
| Python files | 606 |
| Deterministic input-tree SHA-256 | `62a62ed07a3317322ceda4268ef57012305e77cfe94c286d34eeb803b2b51ae0` |
| Engine execution | source checkout at `v0.3.2` (`249420d`) via `npm run test-python` |
| Parser binary | `runtime/yasa-engine-v0.3.2/uast4py-linux-amd64` |
| Parser binary SHA-256 | `2ca48ab0d74c373679b7142d246030483c3464303404dc2212ad2fa8270b1106` |
| Rule configuration | `engine/test/python/rule_config_xast_python3.json` |
| Rule configuration SHA-256 | `3f015699ced3f5278c8a5ca3903eb4a9f130ea393d6daa313563b65fb2282dd1` |

The official test passed: `332 passing`. Its full finding snapshot comparison passed: expected findings `332`, actual findings `332`.

| Scan metric | Result |
| --- | ---: |
| Files analyzed | 606 |
| Lines of code | 17,440 |
| Findings | 332 |
| Marked sources | 1,993 |
| Matched sinks | 3,682 |
| Entry points | 1,295 |
| Engine total time | 8,605 ms |
| Engine parse time | 2,969 ms |
| Parse-code time | 1,589 ms |
| Preload time | 23 ms |
| Process-module time | 1,333 ms |
| Start-analysis time | 1,428 ms |
| Symbol-interpretation time | 3,103 ms |
| Shell wall-clock time | 10.44 s |
| Peak RSS (`/usr/bin/time -v`) | 456,596 KiB (about 446 MiB) |
| Trace-hop accuracy reported by test | 93.67% (1,391 / 1,485), 332 findings |

The detailed SARIF, scan summary, and diagnostics are retained locally under `engine/test/python/report/`; that directory is intentionally ignored by Git. The prepared benchmark directory is also ignored by Git and is recreated by `test/python/prepare-python-benchmark.ts`.

## Broad Python Rule Scan (Supplementary Observation, Not Sufficient for d)

Date: 2026-09-07

The fixed `taint_src -> os.system` test rule above is sufficient for task c, but it is not a product-style security rule set. This separate scan records a migration-before observation using the release's broader Python rule configuration.

| Input / environment | Value |
| --- | --- |
| Input | Same prepared xAST Python 3 corpus: 606 files / 17,440 LOC |
| Rule configuration | `runtime/yasa-engine-v0.3.2/example-rule-config/rule_config_python.json` |
| Rule configuration SHA-256 | `410ade9a71f419c56cb2e85fc38929bdb7807eaf0804161d007762caad4cdb2b` |
| Loaded checkers | `taint_flow_python_input`, `taint_flow_python_input_inner`, `taint_flow_python_django_input` |
| Rule entries | 64 source entries, 63 sink entries |
| Parser | Same external `uast4py` binary as the full xAST regression baseline |

| Scan metric | Result |
| --- | ---: |
| Findings | 42 |
| Marked sources | 2,661 |
| Matched sinks | 22,084 |
| Entry points | 1,295 |
| Engine total time | 19,694 ms |
| Engine parse time | 5,924 ms |
| Start-analysis time | 1,470 ms |
| Symbol-interpretation time | 11,718 ms |
| Shell wall-clock time | 21.07 s |
| Peak RSS (`/usr/bin/time -v`) | 421,732 KiB (about 412 MiB) |
| SARIF SHA-256 | `c73c92b576195114cb5fdbf05880c897cd184c400fc7842c73ef3720064f12f2` |

The detailed result is locally retained under `artifacts/xast-python3-full-rule-baseline/`. A candidate parser can be compared with the same rule configuration and input; compare the finding identities, sink locations, and traces as well as the total count of 42.

This broad-rule scan of the xAST corpus is not sufficient for task d. The Python xAST cases are used by YASA's c regression with a standardized synthetic source/sink probe; they were not designed as an oracle for this product-style rule configuration. A separately fixed open-source Python application corpus containing real framework/API sources and sinks is needed to establish task d's old-versus-new comparison.

The 42-finding count is expected for this input/rule combination, but it is not a coverage claim. The broad configuration has no `taint_src` source entry, while most xAST data-flow samples intentionally use the artificial `taint_src` name. The 332-finding small-rule result measures that synthetic source; the 42-finding broad-rule result measures only the cases where xAST happens to exercise a configured real API/framework source and sink.

Current migration scope decision: Go is out of scope. A separately fixed real-world Python application corpus is required for task d if product-rule coverage, rather than parser non-regression, must be assessed.

## Re-run Commands

```bash
PARSER_ROOT=uast/parser-Python
PYTHON="$PARSER_ROOT/.venv/bin/python"

"$PYTHON" "$PARSER_ROOT/test/test_compat_keywords.py"

"$PYTHON" scripts/verify_python_uast_baseline.py \
  --source-parser-root "$PARSER_ROOT" \
  --binary runtime/uast-v0.2.18/uast4py-linux-amd64 \
  --source "$PARSER_ROOT/test/test_type_annotations.py" \
  --out-dir artifacts/python-uast-baseline/type-annotations
```

## Acceptance Baseline

Before replacing the Python external parser, a candidate Node.js implementation must preserve:

1. The official compatibility unit-test result.
2. Normalized UAST equality for the two recorded fixtures.
3. The xAST smoke finding and SARIF trace.
4. The recorded full xAST Python 3 regression: 332 findings / 332 passing assertions, with no unexpected finding or trace change.
5. The recorded full-regression performance envelope, unless an approved implementation tradeoff changes it.
