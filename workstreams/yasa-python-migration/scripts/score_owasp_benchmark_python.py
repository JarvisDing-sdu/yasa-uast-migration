#!/usr/bin/env python3
"""Score a YASA SARIF scan against OWASP Benchmark Python v0.1 file labels.

This is a file-level regression scorer: a benchmark case is considered flagged
when at least one SARIF result points to its BenchmarkTestNNNNN.py file.  It
does not claim to be OWASP's CWE-aware official score because current YASA
SARIF findings do not carry OWASP CWE/category IDs.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


TEST_NAME_RE = re.compile(r"(BenchmarkTest\d{5})\.py$")


def load_expected(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [{key.strip(): value for key, value in row.items()} for row in csv.DictReader(handle, skipinitialspace=True)]
    expected = {}
    for row in rows:
        name = row["# test name"].strip()
        expected[name] = {
            "category": row["category"].strip(),
            "real": row["real vulnerability"].strip().lower() == "true",
            "cwe": row["cwe"].strip(),
        }
    return expected


def load_flagged_tests(path: Path):
    sarif = json.loads(path.read_text(encoding="utf-8"))
    results = [result for run in sarif.get("runs", []) for result in run.get("results", [])]
    flagged = set()
    unmatched = []
    for result in results:
        locations = result.get("locations", [])
        uri = ""
        if locations:
            uri = locations[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "")
        match = TEST_NAME_RE.search(uri)
        if match:
            flagged.add(match.group(1))
        else:
            unmatched.append(uri)
    return results, flagged, sorted(set(unmatched))


def case_name_from_result(result):
    locations = result.get("locations", [])
    uri = ""
    if locations:
        uri = locations[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "")
    match = TEST_NAME_RE.search(uri)
    return match.group(1) if match else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--sarif", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--include-categories",
        help="Comma-separated OWASP categories to score; default scores every category.",
    )
    parser.add_argument(
        "--scope-name",
        help="Optional human-readable name for the selected category scope.",
    )
    args = parser.parse_args()

    expected_all = load_expected(args.expected)
    included_categories = None
    if args.include_categories:
        included_categories = sorted({item.strip() for item in args.include_categories.split(",") if item.strip()})
        unknown = sorted(set(included_categories) - {item["category"] for item in expected_all.values()})
        if unknown:
            raise SystemExit(f"Unknown OWASP categories: {unknown}")
    expected = {
        name: metadata for name, metadata in expected_all.items()
        if included_categories is None or metadata["category"] in included_categories
    }
    raw_results, flagged, unmatched = load_flagged_tests(args.sarif)
    scoped_results = [result for result in raw_results if case_name_from_result(result) in expected]
    scoped_flagged = flagged & set(expected)
    totals = {"TP": 0, "FN": 0, "TN": 0, "FP": 0}
    categories = defaultdict(lambda: {"TP": 0, "FN": 0, "TN": 0, "FP": 0, "total": 0})

    for name, metadata in expected.items():
        hit = name in scoped_flagged
        outcome = "TP" if metadata["real"] and hit else "FN" if metadata["real"] else "FP" if hit else "TN"
        totals[outcome] += 1
        bucket = categories[metadata["category"]]
        bucket[outcome] += 1
        bucket["total"] += 1

    summary = {
        "scoring": "file-level: any SARIF result in BenchmarkTestNNNNN.py marks that case flagged",
        "limitation": "not OWASP's CWE-aware official score; YASA SARIF lacks OWASP CWE/category IDs",
        "scope_name": args.scope_name,
        "included_categories": included_categories,
        "expected_cases": len(expected),
        "expected_positive_cases": totals["TP"] + totals["FN"],
        "expected_negative_cases": totals["TN"] + totals["FP"],
        "raw_sarif_results": len(raw_results),
        "scoped_raw_sarif_results": len(scoped_results),
        "unique_flagged_cases": len(scoped_flagged),
        "outcomes": totals,
        "categories": dict(sorted(categories.items())),
        "flagged_cases_missing_from_expected": sorted(scoped_flagged - set(expected)),
        "sarif_locations_not_matching_benchmark_test_file": unmatched,
    }
    payload = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
