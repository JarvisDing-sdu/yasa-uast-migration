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
import contextlib
import hashlib
import io
from pathlib import Path
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


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def run(args):
    groups = case_files(args.juliet, args.cwe, args.variant, args.limit)
    if not groups or args.batch < 1:
        raise ValueError('no selected cases or invalid batch size')
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('output directory must be empty; keep previous raw results')
    out.mkdir(parents=True, exist_ok=True)
    names = list(groups)
    batches = [names[i:i + args.batch] for i in range(0, len(names), args.batch)]
    meta = {'schema': 1, 'cwe': args.cwe, 'variant': args.variant,
            'flows': sorted(FLOWS) if FLOWS else None, 'cases': len(names),
            'case_names': names, 'rules_sha256': sha256(args.rules), 'batches': []}
    manifest = out / 'run.json'
    manifest.write_text(json.dumps(meta, indent=2))
    for index, batch in enumerate(batches):
        src = out / f'src-{index:03d}'
        report = out / f'report-{index:03d}'
        src.mkdir()
        for header in ('std_testcase.h', 'std_testcase_io.h'):
            original = Path(args.juliet) / 'testcasesupport' / header
            if original.exists():
                shutil.copy(original, src)
        for case in batch:
            for f in groups[case]:
                target = src / os.path.basename(f)
                if target.exists():
                    raise ValueError(f'duplicate source basename: {target.name}')
                shutil.copy(f, target)
        argv = ['node', '--import', 'tsx', 'src/main.ts', '--sourcePath', str(src), '--language', 'cpp',
                '--ruleConfigFile', os.path.abspath(args.rules), '--checkerPackIds', 'taint-flow-cpp-default',
                '--report', str(report)]
        record = {'index': index, 'cases': len(batch), 'case_names': batch,
                  'files': {f.name: sha256(f) for f in sorted(src.iterdir())},
                  'source_path': str(src), 'argv': argv, 'exit': None}
        meta['batches'].append(record)
        manifest.write_text(json.dumps(meta, indent=2))
        started = time.time()
        proc = subprocess.run(argv, cwd=args.engine, capture_output=True, text=True)
        (out / f'engine-{index:03d}.log').write_text(proc.stdout + proc.stderr)
        record.update(seconds=round(time.time() - started, 1), exit=proc.returncode)
        manifest.write_text(json.dumps(meta, indent=2))
        print(f'batch {index + 1}/{len(batches)}: {len(batch)} cases, {record["seconds"]:.1f}s, exit {proc.returncode}', flush=True)
        if proc.returncode:
            raise ValueError(f'batch {index} failed; raw output retained, score refused')
    validate_run(args)


def validate_run(args):
    """Verify evidence before counting an undetected bad/good flow as FN/TN.

    fileCount proves file coverage, not semantic completeness of supported C++ constructs.
    A successful zero-finding scan legitimately has no report.sarif.
    """
    out = Path(args.out).resolve()
    meta = read_json(out / 'run.json')
    groups = case_files(args.juliet, args.cwe, args.variant, args.limit)
    if (meta.get('schema') != 1 or not groups or meta.get('cwe') != args.cwe or
        meta.get('variant') != args.variant or meta.get('case_names') != list(groups) or
        meta.get('cases') != len(groups)):
        raise ValueError('run manifest does not match requested test selection')
    batches = meta.get('batches', [])
    if not batches or [b.get('index') for b in batches] != list(range(len(batches))):
        raise ValueError('missing or invalid batches')
    if [c for b in batches for c in b.get('case_names', [])] != list(groups):
        raise ValueError('batch partition does not cover selected cases')
    for prefix in ('src-', 'report-'):
        if {p.name for p in out.glob(prefix + '*')} != {f'{prefix}{i:03d}' for i in range(len(batches))}:
            raise ValueError('missing or stale batch directories')
    for batch in batches:
        index = batch['index']
        src, report = out / f'src-{index:03d}', out / f'report-{index:03d}'
        if batch.get('exit') != 0 or batch.get('cases') != len(batch['case_names']):
            raise ValueError(f'batch {index} did not complete successfully')
        expected = {Path(f).name: sha256(f) for c in batch['case_names'] for f in groups[c]}
        for header in ('std_testcase.h', 'std_testcase_io.h'):
            original = Path(args.juliet) / 'testcasesupport' / header
            if original.exists():
                expected[header] = sha256(original)
        actual = {f.name: sha256(f) for f in src.iterdir() if f.is_file()}
        if batch.get('files') != expected or actual != expected:
            raise ValueError(f'batch {index} source manifest mismatch')
        log = (out / f'engine-{index:03d}.log').read_text()
        if re.search(r'#files unable to be parsed:|(?:Error|Exception|FATAL)\b', log):
            raise ValueError(f'batch {index} engine error in log')
        summary = read_json(report / 'scan_summary.json')
        original_src = batch.get('source_path')
        argv = batch.get('argv', [])
        if not original_src and '--sourcePath' in argv:
            original_src = argv[argv.index('--sourcePath') + 1]
        # Raw output may be archived elsewhere. Verify the original scan path while
        # checking the copied inputs above by content, so an archive stays rescorable.
        original_src = Path(original_src or src).resolve()
        if (summary.get('language') != 'cpp' or summary.get('fileCount') != len(expected) or
            not summary.get('scanEndTime') or Path(summary.get('projectPath', '')).resolve() != original_src):
            raise ValueError(f'batch {index} missing scan coverage/completion evidence')
        sarif = report / 'report.sarif'
        if sarif.exists():
            data = read_json(sarif)
            if not data.get('runs'):
                raise ValueError(f'batch {index} empty SARIF runs')
            count = sum(len(r.get('results', [])) for r in data['runs'])
        else:
            count = 0
        if count != summary.get('findingCount'):
            raise ValueError(f'batch {index} SARIF missing or finding count mismatch')
    return meta


def score(args):
    validate_run(args)
    # Keep the existing C scoring labels and logic. Publish only after unmapped == 0.
    with tempfile.TemporaryDirectory() as tmp:
        checked = argparse.Namespace(**vars(args))
        checked.json = os.path.join(tmp, 'score.json')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            base.score(checked)
        result = read_json(checked.json)
        if result['unmapped']:
            raise ValueError(f'{result["unmapped"]} unmapped findings; score refused')
        if args.json:
            Path(args.json).write_text(json.dumps(result, indent=2))
        print(output.getvalue(), end='')


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
        files = {f.name: sha256(f) for f in Path(out, 'src-000').iterdir()}
        Path(out, 'run.json').write_text(json.dumps({'schema': 1, 'cwe': 'X', 'variant': 'char',
            'cases': len(groups), 'case_names': list(groups), 'batches': [{
                'index': 0, 'cases': len(groups), 'case_names': list(groups), 'files': files, 'exit': 0}]}))
        Path(out, 'engine-000.log').write_text('synthetic self-test scan complete')
        Path(out, 'report-000', 'scan_summary.json').write_text(json.dumps({
            'language': 'cpp', 'fileCount': len(files), 'findingCount': len(hits),
            'projectPath': str(Path(out, 'src-000')), 'scanEndTime': 'self-test'}))
        score(args)
        scored = read_json(result)
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
        score(args)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        sys.exit(f'evaluation refused: {exc}')
