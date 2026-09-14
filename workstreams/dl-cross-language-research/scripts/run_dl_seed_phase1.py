#!/usr/bin/env python3
"""Execute generated phase-1 cases and save deterministic expected outputs."""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument(
        "--cases-dir",
        default="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed",
    )
    args = parser.parse_args()
    root = Path(args.cases_dir)
    summary = {"total": 0, "passed": 0, "failed": []}
    for source in sorted(root.glob("DL*/source.py")):
        summary["total"] += 1
        result = subprocess.run([args.python, str(source)], capture_output=True, text=True)
        case_dir = source.parent
        if result.returncode:
            summary["failed"].append({"case": case_dir.name, "stderr": result.stderr})
            continue
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            summary["failed"].append({"case": case_dir.name, "stderr": str(error)})
            continue
        (case_dir / "expected.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        summary["passed"] += 1
    (root / "phase1-run-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if not summary["failed"] else 1)


if __name__ == "__main__":
    main()
