#!/usr/bin/env python3
"""Create a display-only SARIF copy whose source URIs resolve locally.

YASA's primary locations may contain absolute paths without a ``file:`` scheme,
while trace locations may use values such as ``file:///accuracy/...`` that are
relative to the xAST case root in meaning but absolute URI paths in syntax.
SARIF Viewer therefore cannot locate them.  This utility never edits the
evidence file in place; it writes a separate viewer-oriented copy.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlparse


def local_uri(uri: str, source_root: Path) -> tuple[str, bool]:
    parsed = urlparse(uri)
    if parsed.scheme not in {"", "file"}:
        return uri, False

    raw_path = unquote(parsed.path if parsed.scheme == "file" else uri)
    direct = Path(raw_path)
    if direct.is_absolute() and direct.exists():
        return direct.resolve().as_uri(), True

    relative = raw_path.lstrip("/")
    if relative.startswith("case/"):
        relative = relative.removeprefix("case/")
    candidate = source_root / relative
    if candidate.exists():
        return candidate.resolve().as_uri(), True
    return uri, False


def rewrite(value, source_root: Path, counters: dict[str, int]) -> None:
    if isinstance(value, list):
        for item in value:
            rewrite(item, source_root, counters)
        return
    if not isinstance(value, dict):
        return

    artifact = value.get("artifactLocation")
    if isinstance(artifact, dict) and isinstance(artifact.get("uri"), str):
        counters["seen"] += 1
        original = artifact["uri"]
        normalized, resolved = local_uri(original, source_root)
        if resolved:
            artifact["uri"] = normalized
            counters["resolved"] += 1
            if normalized != original:
                counters["rewritten"] += 1
        else:
            counters["unresolved"] += 1

    for child in value.values():
        rewrite(child, source_root, counters)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise SystemExit("Refusing to overwrite the evidence SARIF; choose a separate --output")

    source_root = args.source_root.resolve()
    document = json.loads(input_path.read_text(encoding="utf-8"))
    counters = {"seen": 0, "resolved": 0, "rewritten": 0, "unresolved": 0}
    rewrite(document, source_root, counters)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"input": str(input_path), "output": str(output_path), **counters}, indent=2))
    if counters["unresolved"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
