#!/usr/bin/env python3
"""C regression for the C++ work: everything the C support must keep identical.

  run      parser-C tests, Engine test-c, sast-c, parser-C UAST snapshot,
           Juliet C (CWE78/CWE134 x char/wchar_t) and the curl call graph score;
           writes <out>/summary.json plus the raw outputs.
  compare  checks a run against a baseline run (exit 1 with a list of differences).

Paths come from the environment, with defaults for this workspace:
  YASA_ROOT (integration repo), CORPUS, JULIET, CURL_LARGE, NODE_BUNDLE.
Usage: c_regression.py run OUT [--skip juliet,curl]
       c_regression.py compare OUT BASELINE
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('YASA_ROOT', HERE.parents[2]))
WORK = ROOT.parent.parent  # .../co-d/work
CORPUS = Path(os.environ.get('CORPUS', WORK / 'cpp/corpus'))
JULIET = Path(os.environ.get('JULIET', '/Users/caosijie/Documents/Codex/2026-10-26/https-github-com-jarvisding-sdu-yasa/work/bench-sources/juliet'))
CURL_LARGE = Path(os.environ.get('CURL_LARGE', WORK / 'curl-large'))
NODE_BUNDLE = Path(os.environ.get('NODE_BUNDLE', WORK / 'tools/codegraph-v1.6.2/codegraph-darwin-arm64'))
PARSER_C = ROOT / 'uast/parser-C'
ENGINE = ROOT / 'engine'
C_EXT = ROOT / 'workstreams/yasa-c-extension'
TSX = PARSER_C / 'node_modules/.bin/tsx'
JULIET_SETS = [(cwe, v) for cwe in ('CWE78_OS_Command_Injection', 'CWE134_Uncontrolled_Format_String') for v in ('char', 'wchar_t')]


def sh(cmd, cwd, log):
    with open(log, 'w') as fh:
        return subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT).returncode


def mocha_json(cwd, files, out_file, require):
    """Run mocha with the json reporter written to a file; return {passed, failed} test titles."""
    log = str(out_file) + '.log'
    sh(['npx', 'mocha', '--require', require, *files, '--reporter', 'json', '--reporter-option', f'output={out_file}'],
       cwd, log)
    if Path(out_file).exists():
        data = json.loads(Path(out_file).read_text())
    else:
        # Older mocha ignores `output` and prints the report to stdout, after the engine's own logs.
        text = Path(log).read_text()
        data = json.loads(text[text.rindex('{\n  "stats":'):])
    return {'passed': sorted(t['fullTitle'] for t in data['passes']),
            'failed': sorted(t['fullTitle'] for t in data['failures'])}


def run(out, skip):
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    # 1. parser-C unit tests
    summary['parser_c_tests'] = mocha_json(PARSER_C, ['tests/index.ts'], out / 'parser-c-tests.json', 'tsx')
    # 2. Engine test-c (files taken from package.json so new C test files are included)
    script = json.loads((ENGINE / 'package.json').read_text())['scripts']['test-c']
    files = [w for w in script.split() if w.endswith('.ts')]
    summary['engine_test_c'] = mocha_json(ENGINE, files, out / 'engine-test-c.json', 'tsx/cjs')
    # 3. sast-c
    bench = C_EXT / 'benchmark'
    sh(['npx', 'tsx', 'src/main.ts', '--sourcePath', str(bench / 'sast-c/case'), '--language', 'c',
        '--ruleConfigFile', str(bench / 'rule_config_xast_c.json'), '--checkerPackIds', 'taint-flow-c-default',
        '--report', str(out / 'sast-c')], ENGINE, out / 'sast-c.log')
    sh([sys.executable, str(C_EXT / 'scripts/score_c_benchmark.py'), str(out / 'sast-c/report.sarif'),
        str(bench / 'sast-c/case'), '--json', str(out / 'sast-c.json')], ENGINE, out / 'sast-c-score.log')
    sast = json.loads((out / 'sast-c.json').read_text())
    summary['sast_c'] = {'total': sast['total'], 'cases': {c['case']: c['outcome'] for c in sast['cases']}}
    # 4. UAST snapshot
    sh([str(TSX), str(HERE / 'c_uast_snapshot.ts'), str(PARSER_C), str(CORPUS), str(out / 'uast-snapshot.json')],
       ROOT, out / 'uast-snapshot.log')
    summary['uast_snapshot'] = json.loads((out / 'uast-snapshot.json').read_text())
    # 5. Juliet C
    if 'juliet' not in skip:
        summary['juliet_c'] = {}
        for cwe, variant in JULIET_SETS:
            jout = out / f'juliet-{cwe}-{variant}'
            if jout.exists():
                shutil.rmtree(jout)
            common = ['--juliet', str(JULIET), '--cwe', cwe, '--variant', variant, '--out', str(jout)]
            sh([sys.executable, str(C_EXT / 'scripts/juliet_c.py'), 'run', *common, '--engine', str(ENGINE),
                '--rules', str(ENGINE / 'resource/example-rule-config/rule_config_c.json')], ROOT, str(jout) + '.run.log')
            sh([sys.executable, str(C_EXT / 'scripts/juliet_c.py'), 'score', *common, '--json', str(jout) + '.json'],
               ROOT, str(jout) + '.score.log')
            summary['juliet_c'][f'{cwe}-{variant}'] = json.loads(Path(str(jout) + '.json').read_text())
    # 6. curl call graph
    if 'curl' not in skip:
        cout = out / 'curl-callgraph'
        sh([sys.executable, str(HERE / 'curl_callgraph_score.py'), '--engine', str(ENGINE), '--curl-large', str(CURL_LARGE),
            '--bundle', str(NODE_BUNDLE), '--out', str(cout)], ROOT, out / 'curl-callgraph.log')
        score = json.loads((cout / 'score.json').read_text())
        summary['curl_callgraph'] = {k: score[k] for k in ('primary_strict', 'full_ast_direct_pair_recall', 'curated_indirect')}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    for name in ('parser_c_tests', 'engine_test_c'):
        print(f"{name}: {len(summary[name]['passed'])} passed, {len(summary[name]['failed'])} failed")
    print('sast_c:', summary['sast_c']['total'])
    print('uast_snapshot:', len(summary['uast_snapshot']), 'files')
    for k, v in summary.get('juliet_c', {}).items():
        print('juliet', k, v['totals'])
    if 'curl_callgraph' in summary:
        c = summary['curl_callgraph']
        print('curl: callsite', {k: c['primary_strict']['callsite_target'][k] for k in ('tp', 'fp', 'fn')},
              'full_ast', c['full_ast_direct_pair_recall']['found'], 'curated', c['curated_indirect']['strict_site_target']['found'])


def compare(out, base):
    new = json.loads((out / 'summary.json').read_text())
    old = json.loads((base / 'summary.json').read_text())
    diffs = []
    for name in ('parser_c_tests', 'engine_test_c'):
        if new[name]['failed']:
            diffs.append(f'{name}: failing {new[name]["failed"]}')
        missing = sorted(set(old[name]['passed']) - set(new[name]['passed']))
        if missing:
            diffs.append(f'{name}: baseline tests no longer passing {missing}')
    if new['sast_c'] != old['sast_c']:
        changed = {k: (old['sast_c']['cases'].get(k), v) for k, v in new['sast_c']['cases'].items() if old['sast_c']['cases'].get(k) != v}
        diffs.append(f'sast_c: total {old["sast_c"]["total"]} -> {new["sast_c"]["total"]}; changed {changed}')
    snap_old, snap_new = old['uast_snapshot'], new['uast_snapshot']
    changed = sorted(k for k in set(snap_old) | set(snap_new) if snap_old.get(k) != snap_new.get(k))
    if changed:
        diffs.append(f'uast_snapshot: {len(changed)} files differ, e.g. {changed[:10]}')
    for key in ('juliet_c', 'curl_callgraph'):
        if key in new and key in old and new[key] != old[key]:
            diffs.append(f'{key}: differs')
        elif (key in new) != (key in old):
            diffs.append(f'{key}: present in only one of the runs')
    if diffs:
        print('C regression: DIFFERENT'); [print(' -', d) for d in diffs]
        sys.exit(1)
    print('C regression: identical to baseline')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'run' and len(sys.argv) >= 3:
        skip = set(sys.argv[sys.argv.index('--skip') + 1].split(',')) if '--skip' in sys.argv else set()
        run(Path(sys.argv[2]).resolve(), skip)
    elif cmd == 'compare' and len(sys.argv) == 4:
        compare(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    else:
        sys.exit(__doc__)
