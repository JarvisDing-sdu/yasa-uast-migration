#!/usr/bin/env python3
"""Run old/new Python UAST -> emitter -> new-parser round-trip on a corpus.

The command is intentionally corpus-agnostic. It records every unsupported
syntax/UAST node instead of hiding it, which makes it suitable for b-item
large-project evidence.
"""

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any


LOCATION_KEYS = {"loc", "sourcefile"}
UNSUPPORTED_NODE = re.compile(r"Unsupported Python UAST node ([^ ]+)")


def canonicalize(value: Any) -> Any:
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        result = {
            key: canonicalize(item)
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
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = first_difference(left_item, right_item, f"{path}[{index}]")
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


def classify_error(text: str) -> str:
    matched = UNSUPPORTED_NODE.search(text)
    return f"unsupported:{matched.group(1)}" if matched else "other"


def parse_new(node: str, cli: str, source: Path, output: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    return run([node, cli, "--input", str(source), "--output", str(output)])


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--old-binary", required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument(
        "--new-parser-cli",
        default=str(root / "workstreams/yasa-python-migration/scripts/parse_new_python_uast.js"),
    )
    parser.add_argument(
        "--emitter-cli",
        default=str(root / "uast/emitter-Python/src/cli.js"),
    )
    parser.add_argument("--max-files", type=int)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    ignored_parts = {".git", "node_modules", ".venv", "__pycache__"}
    files = sorted(
        path for path in source_dir.rglob("*.py")
        if not any(part in ignored_parts for part in path.relative_to(source_dir).parts)
    )
    if args.max_files is not None:
        files = files[:args.max_files]

    summary: dict[str, Any] = {
        "sourceDir": str(source_dir),
        "total": len(files),
        "oldParsed": 0,
        "newParsed": 0,
        "semanticOldNewUastEqual": 0,
        "oldEmitted": 0,
        "newEmitted": 0,
        "oldRoundtripPassed": 0,
        "newRoundtripPassed": 0,
        "fullyPassed": 0,
        "failureKinds": {},
        "timingSeconds": {"oldParse": 0.0, "newParse": 0.0, "oldEmit": 0.0, "newEmit": 0.0, "oldReparse": 0.0, "newReparse": 0.0},
        "files": [],
    }
    failure_kinds: Counter[str] = Counter()

    for source in files:
        relative = source.relative_to(source_dir)
        case_dir = artifact_dir / relative.parent / relative.stem
        case_dir.mkdir(parents=True, exist_ok=True)
        old_uast = case_dir / "uast.old.json"
        new_uast = case_dir / "uast.new.json"
        old_source = case_dir / "source.old.py"
        new_source = case_dir / "source.new.py"
        old_report = case_dir / "emitter.old.report.json"
        new_report = case_dir / "emitter.new.report.json"
        old_reparsed = case_dir / "uast.old.roundtrip.new-parser.json"
        new_reparsed = case_dir / "uast.new.roundtrip.new-parser.json"
        row: dict[str, Any] = {"file": str(relative)}

        result, elapsed = run([
            args.old_binary, "--rootDir", str(source), "--singleFileParse", "--output", str(old_uast), "-j1",
        ])
        summary["timingSeconds"]["oldParse"] += elapsed
        if result.returncode or not old_uast.exists():
            text = error_text(result)
            row.update(stage="old-parse", error=text)
            failure_kinds[f"old-parse:{classify_error(text)}"] += 1
            summary["files"].append(row)
            continue
        summary["oldParsed"] += 1

        result, elapsed = parse_new(args.node, args.new_parser_cli, source, new_uast)
        summary["timingSeconds"]["newParse"] += elapsed
        if result.returncode or not new_uast.exists():
            text = error_text(result)
            row.update(stage="new-parse", error=text)
            failure_kinds[f"new-parse:{classify_error(text)}"] += 1
            summary["files"].append(row)
            continue
        summary["newParsed"] += 1

        old_payload = json.loads(old_uast.read_text(encoding="utf-8"))
        new_payload = json.loads(new_uast.read_text(encoding="utf-8"))
        difference = first_difference(canonicalize(old_payload), canonicalize(new_payload))
        row["semanticOldNewUastEqual"] = difference is None
        if difference is None:
            summary["semanticOldNewUastEqual"] += 1
        else:
            row["semanticOldNewDifference"] = difference

        for side, uast, generated, report, timing_key in [
            ("old", old_uast, old_source, old_report, "oldEmit"),
            ("new", new_uast, new_source, new_report, "newEmit"),
        ]:
            result, elapsed = run([
                args.node, args.emitter_cli,
                "--input", str(uast), "--output", str(generated), "--report", str(report),
            ])
            summary["timingSeconds"][timing_key] += elapsed
            if result.returncode:
                text = error_text(result)
                row.update(stage=f"{side}-emit", error=text)
                failure_kinds[f"{side}-emit:{classify_error(text)}"] += 1
                break
            summary[f"{side}Emitted"] += 1
        else:
            for side, generated, original, reparsed, timing_key in [
                ("old", old_source, old_uast, old_reparsed, "oldReparse"),
                ("new", new_source, new_uast, new_reparsed, "newReparse"),
            ]:
                result, elapsed = parse_new(args.node, args.new_parser_cli, generated, reparsed)
                summary["timingSeconds"][timing_key] += elapsed
                if result.returncode or not reparsed.exists():
                    text = error_text(result)
                    row.update(stage=f"{side}-reparse", error=text)
                    failure_kinds[f"{side}-reparse:{classify_error(text)}"] += 1
                    break
                difference = first_difference(
                    canonicalize(json.loads(original.read_text(encoding="utf-8"))),
                    canonicalize(json.loads(reparsed.read_text(encoding="utf-8"))),
                )
                row[f"{side}RoundtripPassed"] = difference is None
                if difference is None:
                    summary[f"{side}RoundtripPassed"] += 1
                else:
                    row[f"{side}RoundtripDifference"] = difference
            else:
                row["fullyPassed"] = all([
                    row.get("semanticOldNewUastEqual"),
                    row.get("oldRoundtripPassed"),
                    row.get("newRoundtripPassed"),
                ])
                if row["fullyPassed"]:
                    summary["fullyPassed"] += 1
        summary["files"].append(row)

    summary["failureKinds"] = dict(sorted(failure_kinds.items()))
    summary["timingSeconds"] = {key: round(value, 6) for key, value in summary["timingSeconds"].items()}
    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
