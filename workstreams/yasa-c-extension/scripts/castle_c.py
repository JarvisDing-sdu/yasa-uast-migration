#!/usr/bin/env python3
"""Run YASA's C checker on the CASTLE benchmark and score it per file.

Every CASTLE file declares `vulnerable: true|false` and its `cwe` in a header
comment. A vulnerable file with at least one finding is a TP, without one a FN;
a safe file with a finding is a FP, without one a TN. CWEs that taint analysis
targets (command injection, format string, path traversal, SQL injection) are
summarised separately from the memory-safety CWEs it does not model.

Usage:
  castle_c.py --castle CASTLE-Source --engine ENGINE_DIR --rules RULES.json --out OUT_DIR [--json result.json]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict

TAINT_CWES = {'78', '134', '22', '89'}


def label(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        head = fh.read(2000)
    vulnerable = re.search(r'vulnerable:\s*(true|false)', head)
    cwe = re.search(r'cwe:\s*(\d+)', head)
    return (vulnerable.group(1) == 'true') if vulnerable else None, cwe.group(1) if cwe else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--castle', required=True)
    parser.add_argument('--engine', required=True)
    parser.add_argument('--rules', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--json')
    parser.add_argument('--cwes', help='comma-separated CWE numbers to run (default: all)')
    args = parser.parse_args()
    only = set(args.cwes.split(',')) if args.cwes else None

    src = os.path.join(args.out, 'src')
    report = os.path.join(args.out, 'report')
    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(src)
    labels = {}
    dataset = os.path.join(args.castle, 'dataset')
    for cwe_dir in sorted(os.listdir(dataset)):
        if only and cwe_dir not in only:
            continue
        for f in sorted(os.listdir(os.path.join(dataset, cwe_dir))):
            if f.endswith('.c'):
                path = os.path.join(dataset, cwe_dir, f)
                labels[f] = label(path)
                # One directory per file: CASTLE files are independent programs that all define main().
                os.makedirs(os.path.join(src, f[:-2]))
                shutil.copy(path, os.path.join(src, f[:-2], f))

    # Each file is an independent program (they all define main() and reuse helper
    # names), so each one is analysed in its own engine run.
    started = time.time()
    hits = defaultdict(list)
    failures = 0
    for f in sorted(labels):
        program = os.path.join(src, f[:-2])
        out = os.path.join(report, f[:-2])
        proc = subprocess.run(
            ['npx', 'tsx', 'src/main.ts', '--sourcePath', program, '--language', 'c',
             '--ruleConfigFile', os.path.abspath(args.rules), '--checkerPackIds', 'taint-flow-c-default',
             '--report', out],
            cwd=args.engine, capture_output=True, text=True)
        if proc.returncode != 0:
            failures += 1
        sarif = os.path.join(out, 'report.sarif')
        if not os.path.exists(sarif):
            continue
        for run in json.load(open(sarif)).get('runs', []):
            for result in run.get('results', []):
                loc = result['locations'][0]['physicalLocation']
                attr = re.search(r'SINK Attribute:\s*(\w+)', json.dumps(result))
                hits[f].append({'line': loc['region'].get('startLine'), 'attribute': attr.group(1) if attr else None})
    elapsed = time.time() - started

    per_cwe = defaultdict(lambda: {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0})
    rows = []
    for f, (vulnerable, cwe) in sorted(labels.items()):
        found = bool(hits.get(f))
        outcome = ('TP' if found else 'FN') if vulnerable else ('FP' if found else 'TN')
        per_cwe[cwe][outcome] += 1
        rows.append({'file': f, 'cwe': cwe, 'vulnerable': vulnerable, 'outcome': outcome, 'findings': hits.get(f, [])})

    def summary(cwes):
        total = {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0}
        for cwe in cwes:
            for k in total:
                total[k] += per_cwe[cwe][k]
        return total

    def line(name, c):
        pos, neg = c['TP'] + c['FN'], c['TN'] + c['FP']
        return f"{name:22} {c['TP']:>4} {c['FN']:>4} {c['TN']:>4} {c['FP']:>4}   TPR {c['TP'] / pos if pos else 0:6.1%}  FPR {c['FP'] / neg if neg else 0:6.1%}"

    print(f'CASTLE: {len(labels)} files, engine failures {failures}, {elapsed:.1f}s')
    print(f"{'':22} {'TP':>4} {'FN':>4} {'TN':>4} {'FP':>4}")
    taint = summary(TAINT_CWES)
    other = summary(set(per_cwe) - TAINT_CWES)
    print(line('taint CWEs (78/134/22/89)', taint))
    print(line('other CWEs', other))
    for cwe in sorted(per_cwe, key=int):
        print(line(f'CWE-{cwe}', per_cwe[cwe]))
    print('\ntaint-CWE misclassifications:')
    for row in rows:
        if row['cwe'] in TAINT_CWES and row['outcome'] in ('FN', 'FP'):
            print(f"  {row['outcome']} {row['file']} {row['findings']}")
    if args.json:
        json.dump({'taint': taint, 'other': other, 'per_cwe': per_cwe, 'files': rows}, open(args.json, 'w'), indent=2)


if __name__ == '__main__':
    main()
