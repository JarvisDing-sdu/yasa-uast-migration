#!/usr/bin/env python3
"""Run YASA's C checker on NIST Juliet C test cases and score TP/FN/TN/FP.

Juliet test cases contain a `bad` flow and one or more `good` flows in
functions named accordingly (`*_bad`, `badSink`, `goodG2B`, `goodB2GSink`...).
Scoring is per test case, the usual Juliet convention:

  bad  flow: TP when a finding's sink lies in a bad function, else FN
  good flow: FP when a finding's sink lies in a good function, else TN

Usage:
  juliet_c.py run   --juliet DIR --cwe CWE78_OS_Command_Injection --variant char \
                    --engine ENGINE_DIR --rules RULES.json --out OUT_DIR [--batch 400]
  juliet_c.py score --juliet DIR --cwe ... --variant char --out OUT_DIR [--json result.json]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict

CASE_RE = re.compile(r'^(?P<base>.+?)_(?P<flow>\d{2})(?P<part>[a-e]?)\.c$')
FUNC_RE = re.compile(r'^(?:static\s+)?(?:[A-Za-z_][\w\s\*]*?\s\**)?(?P<name>[A-Za-z_]\w*)\s*\([^;{]*\)\s*$')


def case_files(juliet, cwe, variant, limit=None):
    """C files of a CWE grouped by test case id (`<base>_<flow>`)."""
    root = os.path.join(juliet, 'testcases', cwe)
    groups = defaultdict(list)
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            m = CASE_RE.match(f)
            if not m:
                continue
            if variant and f'__{variant}_' not in f:
                continue
            groups[f"{m.group('base')}_{m.group('flow')}"].append(os.path.join(dirpath, f))
    items = sorted(groups.items())
    return dict(items[:limit] if limit else items)


def function_ranges(path):
    """(start, end, name) of top-level functions; Juliet keeps `{`/`}` at column 0."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().split('\n')
    ranges = []
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if m and i + 1 < len(lines) and lines[i + 1].startswith('{'):
            start = i + 1
            j = i + 2
            while j < len(lines) and not lines[j].startswith('}'):
                j += 1
            ranges.append((start, j + 1, m.group('name')))
            i = j
        i += 1
    return ranges


def flow_kind(name):
    lowered = name.lower()
    if 'good' in lowered:
        return 'good'
    if 'bad' in lowered:
        return 'bad'
    return None


def run(args):
    groups = case_files(args.juliet, args.cwe, args.variant, args.limit)
    support = os.path.join(args.juliet, 'testcasesupport')
    os.makedirs(args.out, exist_ok=True)
    names = list(groups)
    batches = [names[i:i + args.batch] for i in range(0, len(names), args.batch)]
    meta = {'cwe': args.cwe, 'variant': args.variant, 'cases': len(names), 'batches': []}
    for index, batch in enumerate(batches):
        src = os.path.join(args.out, f'src-{index:03d}')
        report = os.path.join(args.out, f'report-{index:03d}')
        shutil.rmtree(src, ignore_errors=True)
        shutil.rmtree(report, ignore_errors=True)
        os.makedirs(src)
        for header in ('std_testcase.h', 'std_testcase_io.h'):
            if os.path.exists(os.path.join(support, header)):
                shutil.copy(os.path.join(support, header), src)
        for case in batch:
            for f in groups[case]:
                shutil.copy(f, src)
        started = time.time()
        proc = subprocess.run(
            ['npx', 'tsx', 'src/main.ts', '--sourcePath', src, '--language', 'c',
             '--ruleConfigFile', os.path.abspath(args.rules), '--checkerPackIds', 'taint-flow-c-default',
             '--report', report],
            cwd=args.engine, capture_output=True, text=True)
        elapsed = time.time() - started
        with open(os.path.join(args.out, f'engine-{index:03d}.log'), 'w') as fh:
            fh.write(proc.stdout + proc.stderr)
        meta['batches'].append({'index': index, 'cases': len(batch), 'seconds': round(elapsed, 1), 'exit': proc.returncode})
        print(f'batch {index + 1}/{len(batches)}: {len(batch)} cases, {elapsed:.1f}s, exit {proc.returncode}', flush=True)
    with open(os.path.join(args.out, 'run.json'), 'w') as fh:
        json.dump(meta, fh, indent=2)


def score(args):
    groups = case_files(args.juliet, args.cwe, args.variant, args.limit)
    file_to_case = {}
    for case, files in groups.items():
        for f in files:
            file_to_case[os.path.basename(f)] = case
    ranges_cache = {}
    hits = defaultdict(set)  # case -> {'bad', 'good'}
    unmapped = 0
    for entry in sorted(os.listdir(args.out)):
        if not entry.startswith('report-'):
            continue
        sarif = os.path.join(args.out, entry, 'report.sarif')
        if not os.path.exists(sarif):
            continue
        src = os.path.join(args.out, entry.replace('report-', 'src-'))
        for run_ in json.load(open(sarif)).get('runs', []):
            for result in run_.get('results', []):
                loc = result['locations'][0]['physicalLocation']
                name = os.path.basename(loc['artifactLocation']['uri'])
                line = loc['region']['startLine']
                case = file_to_case.get(name)
                path = os.path.join(src, name)
                if case is None or not os.path.exists(path):
                    unmapped += 1
                    continue
                if path not in ranges_cache:
                    ranges_cache[path] = function_ranges(path)
                func = next((n for s, e, n in ranges_cache[path] if s <= line <= e), None)
                kind = flow_kind(func) if func else None
                if kind:
                    hits[case].add(kind)
                else:
                    unmapped += 1

    totals = {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0}
    by_dim = {'source': defaultdict(lambda: dict.fromkeys(totals, 0)),
              'sink': defaultdict(lambda: dict.fromkeys(totals, 0)),
              'flow': defaultdict(lambda: dict.fromkeys(totals, 0))}
    rows = []
    for case in groups:
        parts = case.split('__', 1)[1].rsplit('_', 1)  # "<variant>_<source>_<sink>", "<flow>"
        flow = parts[1]
        body = parts[0][len(args.variant) + 1:] if args.variant and parts[0].startswith(args.variant + '_') else parts[0]
        tokens = [args.variant or ''] + body.split('_')
        bad = 'TP' if 'bad' in hits[case] else 'FN'
        good = 'FP' if 'good' in hits[case] else 'TN'
        totals[bad] += 1
        totals[good] += 1
        rows.append({'case': case, 'bad': bad, 'good': good})
        # Windows-only sinks are spelled `w32_<api>` / `w32spawnl`; keep the prefix with the sink.
        split = len(tokens) - 2 if len(tokens) > 2 and tokens[-2] == 'w32' else len(tokens) - 1
        source = '_'.join(tokens[1:split]) or tokens[0]
        sink = '_'.join(tokens[split:])
        for dim, key in (('source', source), ('sink', sink), ('flow', flow)):
            by_dim[dim][key][bad] += 1
            by_dim[dim][key][good] += 1

    def line(label, c):
        pos, neg = c['TP'] + c['FN'], c['TN'] + c['FP']
        tpr = c['TP'] / pos if pos else 0
        fpr = c['FP'] / neg if neg else 0
        return f"{label:28} {c['TP']:>5} {c['FN']:>5} {c['TN']:>5} {c['FP']:>5}   TPR {tpr:6.1%}  FPR {fpr:6.1%}"

    print(f"{args.cwe} ({args.variant or 'all'}): {len(groups)} test cases; unmapped findings: {unmapped}")
    print(f"{'':28} {'TP':>5} {'FN':>5} {'TN':>5} {'FP':>5}")
    print(line('TOTAL', totals))
    for dim in ('source', 'sink'):
        print(f'-- by {dim}')
        for key, c in sorted(by_dim[dim].items()):
            print(line(key, c))
    print('-- by flow variant (FN or FP only)')
    for key, c in sorted(by_dim['flow'].items()):
        if c['FN'] or c['FP']:
            print(line(key, c))
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump({'cwe': args.cwe, 'variant': args.variant, 'totals': totals, 'unmapped': unmapped,
                       'by': {k: dict(v) for k, v in by_dim.items()}, 'cases': rows}, fh, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run', 'score'])
    parser.add_argument('--juliet', required=True)
    parser.add_argument('--cwe', required=True)
    parser.add_argument('--variant', default='char')
    parser.add_argument('--engine')
    parser.add_argument('--rules')
    parser.add_argument('--out', required=True)
    parser.add_argument('--batch', type=int, default=400)
    parser.add_argument('--json')
    parser.add_argument('--limit', type=int, help='only the first N test cases (sorted by name)')
    args = parser.parse_args()
    if args.command == 'run':
        if not args.engine or not args.rules:
            sys.exit('run needs --engine and --rules')
        run(args)
    else:
        score(args)


if __name__ == '__main__':
    main()
