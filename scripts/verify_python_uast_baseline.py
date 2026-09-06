#!/usr/bin/env python3
"""Compare official Python UAST source and binary parser output for one file."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items() if key != "sourcefile"}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def count_nodes(value):
    if isinstance(value, dict):
        return (1 if "type" in value else 0) + sum(count_nodes(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_nodes(item) for item in value)
    return 0


def digest(value):
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-parser-root", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    source_parser_root = Path(args.source_parser_root).resolve()
    source = Path(args.source).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(source_parser_root))
    from uast.builder import parse_single_file

    source_json_path = out_dir / "source-parser.json"
    binary_json_path = out_dir / "binary-parser.json"
    ok, error = parse_single_file(str(source), str(source_json_path), verbose=True)
    if not ok:
        raise SystemExit(f"source parser failed: {error}")

    subprocess.run(
        [args.binary, "--rootDir", str(source), "--singleFileParse", "--output", str(binary_json_path)],
        check=True,
    )

    source_ast = normalize(json.loads(source_json_path.read_text()))
    binary_ast = normalize(json.loads(binary_json_path.read_text()))
    summary = {
        "source": str(source),
        "source_parser_nodes": count_nodes(source_ast),
        "binary_parser_nodes": count_nodes(binary_ast),
        "source_parser_sha256": digest(source_ast),
        "binary_parser_sha256": digest(binary_ast),
        "structurally_equal": source_ast == binary_ast,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["structurally_equal"] else 1)


if __name__ == "__main__":
    main()
