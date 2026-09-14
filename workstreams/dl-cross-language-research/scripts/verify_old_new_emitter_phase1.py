#!/usr/bin/env python3
"""Verify runtime and new-parser round-trip after old/new UAST emission.

Prerequisite: build_old_new_emitter_phase1.py has produced uast.old/new.json
and source.old/new.py for every Phase 1 case.
"""

import argparse
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

from build_old_new_emitter_phase1 import first_difference, semantic_canonicalize


def run(command: list[str]) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    return result, time.perf_counter() - started


def runtime_equal(left: Any, right: Any, *, tolerance: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            runtime_equal(a, b, tolerance=tolerance) for a, b in zip(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            runtime_equal(left[key], right[key], tolerance=tolerance) for key in left
        )
    return left == right


def error_text(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", default="node")
    parser.add_argument("--python", required=True)
    parser.add_argument(
        "--new-parser-cli",
        default=str(root / "workstreams/yasa-python-migration/scripts/parse_new_python_uast.js"),
    )
    parser.add_argument(
        "--cases-dir",
        default=str(root / "workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed"),
    )
    parser.add_argument("--absolute-tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir).resolve()
    summary: dict[str, Any] = {
        "total": 0,
        "oldRuntimePassed": 0,
        "newRuntimePassed": 0,
        "oldRoundtripSemanticUastPassed": 0,
        "newRoundtripSemanticUastPassed": 0,
        "fullyPassed": 0,
        "absoluteTolerance": args.absolute_tolerance,
        "timingSeconds": {"oldRuntime": 0.0, "newRuntime": 0.0, "oldReparse": 0.0, "newReparse": 0.0},
        "cases": [],
    }

    for expected_path in sorted(cases_dir.glob("DL*/expected.json")):
        case_dir = expected_path.parent
        old_uast = case_dir / "uast.old.json"
        new_uast = case_dir / "uast.new.json"
        old_source = case_dir / "source.old.py"
        new_source = case_dir / "source.new.py"
        old_roundtrip = case_dir / "uast.old.roundtrip.new-parser.json"
        new_roundtrip = case_dir / "uast.new.roundtrip.new-parser.json"
        case: dict[str, Any] = {"case": case_dir.name}
        summary["total"] += 1
        required = [old_uast, new_uast, old_source, new_source]
        missing = [str(path.name) for path in required if not path.exists()]
        if missing:
            case.update(stage="input", error=f"run build_old_new_emitter_phase1.py first; missing {missing}")
            summary["cases"].append(case)
            continue

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        for side, source, timing_key in [
            ("old", old_source, "oldRuntime"),
            ("new", new_source, "newRuntime"),
        ]:
            result, elapsed = run([args.python, str(source)])
            summary["timingSeconds"][timing_key] += elapsed
            if result.returncode:
                case.update(stage=f"{side}-runtime", error=error_text(result))
                break
            try:
                actual = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                case.update(stage=f"{side}-runtime-json", error=str(error))
                break
            passed = runtime_equal(expected, actual, tolerance=args.absolute_tolerance)
            case[f"{side}RuntimePassed"] = passed
            if passed:
                summary[f"{side}RuntimePassed"] += 1
        else:
            for side, source, output, timing_key in [
                ("old", old_source, old_roundtrip, "oldReparse"),
                ("new", new_source, new_roundtrip, "newReparse"),
            ]:
                result, elapsed = run([
                    args.node, args.new_parser_cli,
                    "--input", str(source), "--output", str(output),
                ])
                summary["timingSeconds"][timing_key] += elapsed
                if result.returncode or not output.exists():
                    case.update(stage=f"{side}-reparse", error=error_text(result))
                    break
                original = old_uast if side == "old" else new_uast
                difference = first_difference(
                    semantic_canonicalize(json.loads(original.read_text(encoding="utf-8"))),
                    semantic_canonicalize(json.loads(output.read_text(encoding="utf-8"))),
                )
                passed = difference is None
                case[f"{side}RoundtripSemanticUastPassed"] = passed
                if passed:
                    summary[f"{side}RoundtripSemanticUastPassed"] += 1
                else:
                    case[f"{side}RoundtripDifference"] = difference
            else:
                case["fullyPassed"] = all([
                    case.get("oldRuntimePassed"),
                    case.get("newRuntimePassed"),
                    case.get("oldRoundtripSemanticUastPassed"),
                    case.get("newRoundtripSemanticUastPassed"),
                ])
                if case["fullyPassed"]:
                    summary["fullyPassed"] += 1
        summary["cases"].append(case)

    summary["timingSeconds"] = {key: round(value, 6) for key, value in summary["timingSeconds"].items()}
    (cases_dir / "phase1-old-new-emitter-runtime-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["fullyPassed"] == summary["total"] else 1)


if __name__ == "__main__":
    main()
