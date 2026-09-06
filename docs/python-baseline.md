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
4. Full xAST Python regression after the public fixture gap is resolved or explicitly excluded.
