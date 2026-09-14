#!/usr/bin/env python3
"""Parse generated seed sources with a uast4py binary and save UAST JSON."""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument(
        "--cases-dir",
        default="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed",
    )
    args = parser.parse_args()
    root = Path(args.cases_dir)
    summary = {"total": 0, "passed": 0, "failed": []}
    for source in sorted(root.glob("DL*/source.py")):
        summary["total"] += 1
        target = source.parent / "source.uast.json"
        result = subprocess.run(
            [args.binary, "--rootDir", str(source.resolve()), "--singleFileParse", "--output", str(target.resolve()), "-j1"],
            capture_output=True,
            text=True,
        )
        if result.returncode or not target.exists():
            summary["failed"].append({"case": source.parent.name, "stderr": result.stderr})
            continue
        try:
            root_node = json.loads(target.read_text(encoding="utf-8"))
            if root_node.get("type") != "CompileUnit":
                raise ValueError("root is not CompileUnit")
        except Exception as error:
            summary["failed"].append({"case": source.parent.name, "stderr": str(error)})
            continue
        summary["passed"] += 1
    (root / "phase1-uast-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if not summary["failed"] else 1)


if __name__ == "__main__":
    main()
