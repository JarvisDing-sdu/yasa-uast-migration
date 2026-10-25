#!/usr/bin/env python3
"""Score a YASA SARIF report against the xAST-style C benchmark.

A case is a `.c` file or a directory whose name ends in `_T` (must be
detected) or `_F` (must not be detected). A case counts as detected when any
finding's sink location lies inside it.

Usage: score_c_benchmark.py <report.sarif> <case-root> [--json out.json]
"""
import json
import os
import sys
from collections import defaultdict


def collect_cases(root):
    cases = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        name = os.path.basename(dirpath)
        if rel != '.' and (name.endswith('_T') or name.endswith('_F')):
            cases[rel] = name.endswith('_T')
            dirnames[:] = []
            continue
        for f in filenames:
            stem = f[:-2] if f.endswith('.c') else None
            if stem and (stem.endswith('_T') or stem.endswith('_F')):
                cases[os.path.normpath(os.path.join(rel, stem))] = stem.endswith('_T')
    return cases


def finding_case(uri, root, cases):
    path = uri.replace('file://', '')
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root)) if os.path.isabs(path) else path
    rel = os.path.normpath(rel)
    stem = rel[:-2] if rel.endswith('.c') else rel
    if stem in cases:
        return stem
    parts = rel.split(os.sep)
    for i in range(len(parts), 0, -1):
        cand = os.sep.join(parts[:i])
        if cand in cases:
            return cand
    return None


def main():
    sarif_path, root = sys.argv[1], sys.argv[2]
    cases = collect_cases(root)
    detected = set()
    report = json.load(open(sarif_path))
    for run in report.get('runs', []):
        for result in run.get('results', []):
            for loc in result.get('locations', []):
                uri = loc['physicalLocation']['artifactLocation']['uri']
                case = finding_case(uri, root, cases)
                if case:
                    detected.add(case)

    by_cat = defaultdict(lambda: {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0})
    rows = []
    for case, expected in sorted(cases.items()):
        hit = case in detected
        outcome = ('TP' if hit else 'FN') if expected else ('FP' if hit else 'TN')
        category = os.path.dirname(case)
        by_cat[category][outcome] += 1
        rows.append({'case': case, 'expected': expected, 'detected': hit, 'outcome': outcome})

    total = {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0}
    print(f"{'category':45} {'TP':>4} {'FN':>4} {'TN':>4} {'FP':>4}")
    for category, c in sorted(by_cat.items()):
        print(f"{category:45} {c['TP']:>4} {c['FN']:>4} {c['TN']:>4} {c['FP']:>4}")
        for k in total:
            total[k] += c[k]
    print(f"{'TOTAL':45} {total['TP']:>4} {total['FN']:>4} {total['TN']:>4} {total['FP']:>4}")
    pos, neg = total['TP'] + total['FN'], total['TN'] + total['FP']
    print(f"TPR (recall) = {total['TP']}/{pos} = {total['TP'] / pos:.1%}" if pos else 'no positive cases')
    print(f"FPR          = {total['FP']}/{neg} = {total['FP'] / neg:.1%}" if neg else 'no negative cases')
    print('\nmisclassified:')
    for row in rows:
        if row['outcome'] in ('FN', 'FP'):
            print(f"  {row['outcome']}  {row['case']}")
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump({'total': total, 'categories': by_cat, 'cases': rows}, open(out, 'w'), indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
