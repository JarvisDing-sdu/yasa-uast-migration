#!/usr/bin/env python3
"""Build the old/new UAST -> Python emitter evidence for Phase 1 cases.

For each source.py, this script constructs both required paths without letting
the emitter read source.py, expected.json, or any previous output:

  old uast4py binary -> uast.old.json -> emitter -> source.old.py
  new Tree-sitter parser -> uast.new.json -> emitter -> source.new.py

It also records a direct canonical UAST comparison. Runtime execution is
deliberately a separate next-stage check.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


LOCATION_KEYS = {"loc", "sourcefile"}


def canonicalize(value: Any) -> Any:
    """Remove only source-position information, retaining semantic fields."""
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: canonicalize(item)
            for key, item in sorted(value.items())
            if key not in LOCATION_KEYS
        }
    return value


def semantic_canonicalize(value: Any) -> Any:
    """Normalize the known JSON spelling variance for float literals.

    JSON has one generic numeric type. The old binary serializes a Python
    ``float`` whose value is integral as ``1.0``; JSON.parse in the Node path
    serializes the same UAST float literal as ``1``.  ``literalType=float`` is
    preserved in both trees and is the semantic discriminator.  This helper
    keeps the strict comparison separate while normalizing that wire-format
    variance for the semantic comparison.
    """
    if isinstance(value, list):
        return [semantic_canonicalize(item) for item in value]
    if isinstance(value, dict):
        result = {
            key: semantic_canonicalize(item)
            for key, item in sorted(value.items())
            if key not in LOCATION_KEYS
        }
        if result.get("type") == "Literal" and result.get("literalType") == "float":
            numeric = result.get("value")
            if isinstance(numeric, (int, float)) and not isinstance(numeric, bool):
                result["value"] = {"semanticFloat": repr(float(numeric))}
        if result.get("type") == "Literal" and result.get("literalType") == "number":
            numeric = result.get("value")
            if isinstance(numeric, (int, float)) and not isinstance(numeric, bool):
                result["value"] = {"semanticInteger": str(int(numeric))}
            elif isinstance(numeric, str) and numeric.isdigit():
                result["value"] = {"semanticInteger": numeric}
        return result
    return value


def first_difference(left: Any, right: Any, path: str = "$") -> str | None:
    if type(left) is not type(right):
        return f"{path}: type {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return f"{path}: old-only={sorted(set(left) - set(right))}, new-only={sorted(set(right) - set(left))}"
        for key in left:
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: length {len(left)} != {len(right)}"
        for index, (old_item, new_item) in enumerate(zip(left, right)):
            difference = first_difference(old_item, new_item, f"{path}[{index}]")
            if difference:
                return difference
        return None
    return None if left == right else f"{path}: {left!r} != {right!r}"


def run(command: list[str]) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    return result, time.perf_counter() - started


def error_text(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", default="node")
    parser.add_argument("--old-binary", required=True)
    parser.add_argument(
        "--new-parser-cli",
        default=str(root / "workstreams/yasa-python-migration/scripts/parse_new_python_uast.js"),
    )
    parser.add_argument(
        "--emitter-cli",
        default=str(root / "uast/emitter-Python/src/cli.js"),
    )
    parser.add_argument(
        "--cases-dir",
        default=str(root / "workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed"),
    )
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir).resolve()
    summary: dict[str, Any] = {
        "total": 0,
        "oldParsed": 0,
        "newParsed": 0,
        "oldEmitted": 0,
        "newEmitted": 0,
        "strictCanonicalUastEqual": 0,
        "semanticCanonicalUastEqual": 0,
        "sourceTextEqual": 0,
        "timingSeconds": {"oldParse": 0.0, "newParse": 0.0, "oldEmit": 0.0, "newEmit": 0.0},
        "cases": [],
    }

    for source in sorted(cases_dir.glob("DL*/source.py")):
        case_dir = source.parent
        old_uast = case_dir / "uast.old.json"
        new_uast = case_dir / "uast.new.json"
        old_source = case_dir / "source.old.py"
        new_source = case_dir / "source.new.py"
        old_report = case_dir / "emitter.old.report.json"
        new_report = case_dir / "emitter.new.report.json"
        case: dict[str, Any] = {"case": case_dir.name}
        summary["total"] += 1

        result, elapsed = run([
            args.old_binary,
            "--rootDir", str(source.resolve()),
            "--singleFileParse",
            "--output", str(old_uast.resolve()),
            "-j1",
        ])
        summary["timingSeconds"]["oldParse"] += elapsed
        if result.returncode or not old_uast.exists():
            case.update(stage="old-parse", error=error_text(result))
            summary["cases"].append(case)
            continue
        summary["oldParsed"] += 1

        result, elapsed = run([
            args.node,
            args.new_parser_cli,
            "--input", str(source.resolve()),
            "--output", str(new_uast.resolve()),
        ])
        summary["timingSeconds"]["newParse"] += elapsed
        if result.returncode or not new_uast.exists():
            case.update(stage="new-parse", error=error_text(result))
            summary["cases"].append(case)
            continue
        summary["newParsed"] += 1

        result, elapsed = run([
            args.node, args.emitter_cli,
            "--input", str(old_uast), "--output", str(old_source), "--report", str(old_report),
        ])
        summary["timingSeconds"]["oldEmit"] += elapsed
        if result.returncode:
            case.update(stage="old-emit", error=error_text(result))
            summary["cases"].append(case)
            continue
        summary["oldEmitted"] += 1

        result, elapsed = run([
            args.node, args.emitter_cli,
            "--input", str(new_uast), "--output", str(new_source), "--report", str(new_report),
        ])
        summary["timingSeconds"]["newEmit"] += elapsed
        if result.returncode:
            case.update(stage="new-emit", error=error_text(result))
            summary["cases"].append(case)
            continue
        summary["newEmitted"] += 1

        old_payload = json.loads(old_uast.read_text(encoding="utf-8"))
        new_payload = json.loads(new_uast.read_text(encoding="utf-8"))
        strict_difference = first_difference(canonicalize(old_payload), canonicalize(new_payload))
        case["strictCanonicalUastEqual"] = strict_difference is None
        if strict_difference is None:
            summary["strictCanonicalUastEqual"] += 1
        else:
            case["strictCanonicalDifference"] = strict_difference

        semantic_difference = first_difference(
            semantic_canonicalize(old_payload), semantic_canonicalize(new_payload)
        )
        case["semanticCanonicalUastEqual"] = semantic_difference is None
        if semantic_difference is None:
            summary["semanticCanonicalUastEqual"] += 1
        else:
            case["semanticCanonicalDifference"] = semantic_difference

        case["sourceTextEqual"] = old_source.read_text(encoding="utf-8") == new_source.read_text(encoding="utf-8")
        if case["sourceTextEqual"]:
            summary["sourceTextEqual"] += 1
        case["oldFidelityStatus"] = json.loads(old_report.read_text(encoding="utf-8"))["status"]
        case["newFidelityStatus"] = json.loads(new_report.read_text(encoding="utf-8"))["status"]
        summary["cases"].append(case)

    summary["timingSeconds"] = {key: round(value, 6) for key, value in summary["timingSeconds"].items()}
    (cases_dir / "phase1-old-new-emitter-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["newEmitted"] == summary["total"] else 1)


if __name__ == "__main__":
    main()
