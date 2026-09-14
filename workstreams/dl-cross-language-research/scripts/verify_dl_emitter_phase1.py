#!/usr/bin/env python3
"""Verify deterministic Python UAST emission on the phase-1 PyTorch corpus.

For every case this script performs both independent checks:

1. UAST -> Python -> execution, compared with the recorded runtime oracle.
2. UAST -> Python -> uast4py, compared after location-only canonicalization.

The emitter receives only ``source.uast.json``.  It never reads ``source.py`` or
``expected.json``; those files are used here solely by the test harness.
"""

import argparse
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any


LOCATION_KEYS = {"loc", "sourcefile"}


def canonicalize(value: Any) -> Any:
    """Remove source-position data while preserving all semantic UAST fields."""
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: canonicalize(item)
            for key, item in sorted(value.items())
            if key not in LOCATION_KEYS
        }
    return value


def first_difference(left: Any, right: Any, path: str = "$") -> str | None:
    """Return a compact path-oriented explanation for the first difference."""
    if type(left) is not type(right):
        return f"{path}: type {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            missing = sorted(set(left) - set(right))
            extra = sorted(set(right) - set(left))
            return f"{path}: missing={missing}, extra={extra}"
        for key in left:
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: length {len(left)} != {len(right)}"
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = first_difference(left_item, right_item, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if left != right:
        return f"{path}: {left!r} != {right!r}"
    return None


def runtime_equal(left: Any, right: Any, *, absolute_tolerance: float) -> bool:
    """Compare JSON values recursively, allowing only bounded float drift."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=0.0, abs_tol=absolute_tolerance)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            runtime_equal(left[key], right[key], absolute_tolerance=absolute_tolerance)
            for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            runtime_equal(a, b, absolute_tolerance=absolute_tolerance)
            for a, b in zip(left, right)
        )
    return left == right


def run(command: list[str]) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    return result, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", default="node")
    parser.add_argument("--emitter", default="uast/emitter-Python/src/cli.js")
    parser.add_argument("--python", required=True)
    parser.add_argument("--binary", required=True, help="Existing uast4py executable")
    parser.add_argument(
        "--cases-dir",
        default="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed",
    )
    parser.add_argument("--absolute-tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    cases_root = Path(args.cases_dir)
    summary: dict[str, Any] = {
        "total": 0,
        "emitted": 0,
        "runtimePassed": 0,
        "canonicalUastPassed": 0,
        "fullyPassed": 0,
        "fidelityStatusCounts": {"canonical": 0, "ambiguous": 0, "lossy": 0},
        "absoluteTolerance": args.absolute_tolerance,
        "timingSeconds": {"emit": 0.0, "execute": 0.0, "reparse": 0.0},
        "cases": [],
    }

    for source_uast in sorted(cases_root.glob("DL*/source.uast.json")):
        case_dir = source_uast.parent
        case_result: dict[str, Any] = {"case": case_dir.name}
        summary["total"] += 1
        generated_source = case_dir / "roundtrip.py"
        fidelity_report = case_dir / "fidelity-report.json"
        roundtrip_uast = case_dir / "roundtrip.uast.json"

        emit, elapsed = run([
            args.node,
            args.emitter,
            "--input", str(source_uast),
            "--output", str(generated_source),
            "--report", str(fidelity_report),
        ])
        summary["timingSeconds"]["emit"] += elapsed
        if emit.returncode:
            case_result.update(stage="emit", error=emit.stderr.strip())
            summary["cases"].append(case_result)
            continue
        summary["emitted"] += 1
        try:
            fidelity = json.loads(fidelity_report.read_text(encoding="utf-8"))
            fidelity_status = fidelity["status"]
            case_result["fidelityStatus"] = fidelity_status
            case_result["ambiguityKinds"] = sorted({
                item["kind"] for item in fidelity.get("ambiguities", [])
            })
            case_result["lossKinds"] = sorted({
                item["kind"] for item in fidelity.get("losses", [])
            })
            if fidelity_status in summary["fidelityStatusCounts"]:
                summary["fidelityStatusCounts"][fidelity_status] += 1
        except (KeyError, OSError, json.JSONDecodeError) as error:
            case_result.update(stage="fidelity-report", error=str(error))
            summary["cases"].append(case_result)
            continue

        execute, elapsed = run([args.python, str(generated_source)])
        summary["timingSeconds"]["execute"] += elapsed
        if execute.returncode:
            case_result.update(stage="execute", error=execute.stderr.strip())
            summary["cases"].append(case_result)
            continue
        try:
            actual = json.loads(execute.stdout)
            expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
            runtime_passed = runtime_equal(
                expected, actual, absolute_tolerance=args.absolute_tolerance
            )
        except (OSError, json.JSONDecodeError) as error:
            case_result.update(stage="runtime-compare", error=str(error))
            summary["cases"].append(case_result)
            continue
        case_result["runtimePassed"] = runtime_passed
        if runtime_passed:
            summary["runtimePassed"] += 1

        reparse, elapsed = run([
            args.binary,
            "--rootDir", str(generated_source.resolve()),
            "--singleFileParse",
            "--output", str(roundtrip_uast.resolve()),
            "-j1",
        ])
        summary["timingSeconds"]["reparse"] += elapsed
        if reparse.returncode or not roundtrip_uast.exists():
            case_result.update(stage="reparse", error=reparse.stderr.strip())
            summary["cases"].append(case_result)
            continue

        original = canonicalize(json.loads(source_uast.read_text(encoding="utf-8")))
        reparsed = canonicalize(json.loads(roundtrip_uast.read_text(encoding="utf-8")))
        difference = first_difference(original, reparsed)
        canonical_passed = difference is None
        case_result["canonicalUastPassed"] = canonical_passed
        if difference:
            case_result["canonicalDifference"] = difference
        else:
            summary["canonicalUastPassed"] += 1

        case_result["fullyPassed"] = runtime_passed and canonical_passed
        if case_result["fullyPassed"]:
            summary["fullyPassed"] += 1
        summary["cases"].append(case_result)

    summary["timingSeconds"] = {
        key: round(value, 6) for key, value in summary["timingSeconds"].items()
    }
    summary_path = cases_root / "phase1-emitter-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["fullyPassed"] == summary["total"] else 1)


if __name__ == "__main__":
    main()
