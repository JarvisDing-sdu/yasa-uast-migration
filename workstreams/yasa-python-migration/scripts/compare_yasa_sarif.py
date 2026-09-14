#!/usr/bin/env python3
"""Compare YASA SARIF findings and traces, ignoring only derived node hashes."""

import argparse
import json
from pathlib import Path
from typing import Any


IGNORED_KEYS = {"nodeHash"}


def normalize_uri(value: Any) -> Any:
    """Normalize only the legacy xAST source-root spelling in trace strings."""
    if not isinstance(value, str):
        return value
    if value.startswith("file:///case/"):
        return "file:///" + value.removeprefix("file:///case/")
    # The old binary embeds this root in entrypoint names and trace snippets,
    # not only in URI fields.
    return value.replace("/case/", "/")


def normalize(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: normalize_uri(item) if isinstance(item, str) else normalize(item)
            for key, item in sorted(value.items())
            if key not in IGNORED_KEYS
        }
    return value


def results(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [result for run in document.get("runs", []) for result in run.get("results", [])]


def identity(result: dict[str, Any]) -> tuple[Any, ...]:
    location = result.get("locations", [{}])[0].get("physicalLocation", {})
    region = location.get("region", {})
    return (
        result.get("ruleId"),
        location.get("artifactLocation", {}).get("uri"),
        region.get("startLine"),
        region.get("startColumn"),
        result.get("message", {}).get("text"),
    )


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


def canonical_result(result: dict[str, Any]) -> str:
    return json.dumps(normalize(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    old_results = results(json.loads(args.old.read_text(encoding="utf-8")))
    new_results = results(json.loads(args.new.read_text(encoding="utf-8")))
    old_ids = set(map(identity, old_results))
    new_ids = set(map(identity, new_results))
    normalized_old = sorted(map(canonical_result, old_results))
    normalized_new = sorted(map(canonical_result, new_results))
    difference = first_difference(normalized_old, normalized_new)
    summary = {
        "ignoredDerivedFields": sorted(IGNORED_KEYS),
        "normalizedEnvironmentFields": ["legacy xAST source-root: /case/ → /"],
        "oldRawFindings": len(old_results),
        "newRawFindings": len(new_results),
        "identityEqual": old_ids == new_ids,
        "normalizedResultsEqual": normalized_old == normalized_new,
        "firstNormalizedDifference": difference,
        "oldOnlyIdentities": sorted(old_ids - new_ids)[:20],
        "newOnlyIdentities": sorted(new_ids - old_ids)[:20],
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    raise SystemExit(0 if summary["normalizedResultsEqual"] else 1)


if __name__ == "__main__":
    main()
