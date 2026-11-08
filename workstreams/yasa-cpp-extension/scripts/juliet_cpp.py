#!/usr/bin/env python3
"""Run YASA's C++ checker on NIST Juliet C++ test cases and score TP/FN/TN/FP.

Same scoring as workstreams/yasa-c-extension/scripts/juliet_c.py (per test case:
bad flow TP/FN, good flows FP/TN), adapted to C++ test cases:

- files are `<base>_<flow><part>?.cpp`, the case header `<base>_<flow>.h`, and for
  flows 81-84 `<base>_<flow>_bad.cpp` / `_goodG2B.cpp` / `_goodB2G.cpp`;
- functions may be out-of-line members (`X_bad::action`), attributed by the
  same `flow_kind` rule as C (name contains `good` -> good, `bad` -> bad).

Usage:
  juliet_cpp.py run   --juliet DIR --cwe CWE78_OS_Command_Injection --variant char \
                      --engine ENGINE_DIR --rules RULES.json --out OUT_DIR [--batch 400] [--flows 01,33]
  juliet_cpp.py score --juliet DIR --cwe ... --variant char --out OUT_DIR [--flows ...] [--json result.json]
  juliet_cpp.py --self-test
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'yasa-c-extension', 'scripts'))
import juliet_c as base  # noqa: E402

# C++ test-case files: `<base>_<flow><part>?.cpp`, flows 81-84 `<base>_<flow>_bad|_goodG2B|_goodB2G.cpp`,
# and the case's own class header `<base>_<flow>.h`.
base.CASE_RE = re.compile(r'^(?P<base>.+?)_(?P<flow>\d{2})(?P<part>[a-e]|_bad|_goodG2B|_goodB2G)?\.(?:cpp|h)$')
# Function names may be qualified (`X_bad::action`).
base.FUNC_RE = re.compile(
    r'^(?:static\s+)?(?:[A-Za-z_][\w\s\*:<>,&]*?\s[\*&]*)?(?P<name>[A-Za-z_][\w]*(?:::[A-Za-z_~]\w*)*)\s*\([^;{]*\)\s*(?:const\s*)?$')

_case_files_c = base.case_files
FLOWS = None


def case_files(juliet, cwe, variant, limit=None):
    """Test cases of a CWE, restricted to FLOWS when set."""
    groups = _case_files_c(juliet, cwe, variant)
    if FLOWS:
        groups = {case: files for case, files in groups.items() if case.rsplit('_', 1)[1] in FLOWS}
    items = list(groups.items())
    return dict(items[:limit] if limit else items)


base.case_files = case_files


def run(args):
    groups = case_files(args.juliet, args.cwe, args.variant, args.limit)
    support = os.path.join(args.juliet, 'testcasesupport')
    os.makedirs(args.out, exist_ok=True)
    names = list(groups)
    batches = [names[i:i + args.batch] for i in range(0, len(names), args.batch)]
    meta = {'cwe': args.cwe, 'variant': args.variant, 'flows': args.flows, 'cases': len(names), 'batches': []}
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
            ['npx', 'tsx', 'src/main.ts', '--sourcePath', src, '--language', 'cpp',
             '--ruleConfigFile', os.path.abspath(args.rules), '--checkerPackIds', 'taint-flow-cpp-default',
             '--report', report],
            cwd=args.engine, capture_output=True, text=True)
        elapsed = time.time() - started
        with open(os.path.join(args.out, f'engine-{index:03d}.log'), 'w') as fh:
            fh.write(proc.stdout + proc.stderr)
        meta['batches'].append({'index': index, 'cases': len(batch), 'seconds': round(elapsed, 1), 'exit': proc.returncode})
        print(f'batch {index + 1}/{len(batches)}: {len(batch)} cases, {elapsed:.1f}s, exit {proc.returncode}', flush=True)
    with open(os.path.join(args.out, 'run.json'), 'w') as fh:
        json.dump(meta, fh, indent=2)


SELF_TEST_FILES = {
    'X__char_env_system_01.cpp': [
        '#include "std_testcase.h"', 'namespace X__char_env_system_01', '{',
        'void bad()', '{', '    SINK;', '}',
        'static void goodG2B()', '{', '    SAFE;', '}',
        '}',
    ],
    'X__char_env_system_82.h': ['class X__char_env_system_82_bad { void action(char *); };'],
    'X__char_env_system_82a.cpp': ['namespace X__char_env_system_82', '{', 'void bad()', '{', '    CALL;', '}', '}'],
    'X__char_env_system_82_bad.cpp': [
        'namespace X__char_env_system_82', '{',
        'void X__char_env_system_82_bad::action(char * data)', '{', '    SINK;', '}', '}',
    ],
    'X__char_env_system_82_goodG2B.cpp': [
        'namespace X__char_env_system_82', '{',
        'void X__char_env_system_82_goodG2B::action(char * data)', '{', '    SINK;', '}', '}',
    ],
}


def self_test():
    """Scoring of a plain case and of a class-member (flow 82) case on a constructed SARIF."""
    with tempfile.TemporaryDirectory() as tmp:
        cwe_dir = os.path.join(tmp, 'juliet', 'testcases', 'X', 's01')
        out = os.path.join(tmp, 'out')
        os.makedirs(cwe_dir)
        os.makedirs(os.path.join(out, 'src-000'))
        os.makedirs(os.path.join(out, 'report-000'))
        for name, lines in SELF_TEST_FILES.items():
            for d in (cwe_dir, os.path.join(out, 'src-000')):
                with open(os.path.join(d, name), 'w') as fh:
                    fh.write('\n'.join(lines) + '\n')
        hits = [('X__char_env_system_01.cpp', 6), ('X__char_env_system_82_bad.cpp', 5),
                ('X__char_env_system_82_goodG2B.cpp', 5)]
        sarif = {'runs': [{'results': [{'locations': [{'physicalLocation': {
            'artifactLocation': {'uri': f'file://{out}/src-000/{f}'}, 'region': {'startLine': line}}}]}
            for f, line in hits]}]}
        with open(os.path.join(out, 'report-000', 'report.sarif'), 'w') as fh:
            json.dump(sarif, fh)

        groups = base.case_files(os.path.join(tmp, 'juliet'), 'X', 'char')
        assert sorted(groups) == ['X__char_env_system_01', 'X__char_env_system_82'], sorted(groups)
        assert len(groups['X__char_env_system_82']) == 4, groups['X__char_env_system_82']
        result = os.path.join(tmp, 'result.json')
        args = argparse.Namespace(juliet=os.path.join(tmp, 'juliet'), cwe='X', variant='char', out=out,
                                  json=result, limit=None)
        base.score(args)
        scored = json.load(open(result))
        cases = {row['case']: (row['bad'], row['good']) for row in scored['cases']}
        assert cases == {'X__char_env_system_01': ('TP', 'TN'), 'X__char_env_system_82': ('TP', 'FP')}, cases
        assert scored['unmapped'] == 0, scored['unmapped']
    print('self-test: ok')


def main():
    if sys.argv[1:] == ['--self-test']:
        self_test()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run', 'score'])
    parser.add_argument('--juliet', required=True)
    parser.add_argument('--cwe', required=True)
    parser.add_argument('--variant', default='char')
    parser.add_argument('--engine')
    parser.add_argument('--rules')
    parser.add_argument('--out', required=True)
    parser.add_argument('--batch', type=int, default=400)
    parser.add_argument('--flows', help='comma-separated flow numbers, e.g. 01,33 (default: all)')
    parser.add_argument('--json')
    parser.add_argument('--limit', type=int, help='only the first N test cases (sorted by name)')
    args = parser.parse_args()
    global FLOWS
    FLOWS = set(args.flows.split(',')) if args.flows else None
    if args.command == 'run':
        if not args.engine or not args.rules:
            sys.exit('run needs --engine and --rules')
        run(args)
    else:
        base.score(args)


if __name__ == '__main__':
    main()
