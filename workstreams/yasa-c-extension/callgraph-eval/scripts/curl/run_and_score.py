#!/usr/bin/env python3
"""Run the callback-fix Engine on the frozen curl benchmark and score it with the unchanged protocol.

Same node bundle, argv, source, configuration and heap as the earlier yasa-fixed run
(curl-large/run_analyzer.py); only the Engine checkout differs. Export and scoring reuse
curl-large/export_predictions.py and curl-large/score.py as libraries, reading gold and the
curated indirect subset in place. Nothing under curl-large/ is written.

Usage: run_and_score.py [run|score|all]
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
CURL = WORK / 'curl-large'
ENGINE = WORK / 'callback-fix/engine'
BUNDLE = WORK / 'tools/codegraph-v1.6.2/codegraph-darwin-arm64'
TOOL = 'yasa-callback'
OUT = HERE / 'results' / TOOL
HEAP_MB = 8192


def run():
    config = json.loads((CURL / 'yasa-run-config.json').read_text())
    cmd = [str(BUNDLE / 'node'), f'--max-old-space-size={HEAP_MB}', '--import', 'tsx', 'src/main.ts',
           '--sourcePath', str(CURL / 'input'), '--language', 'c',
           '--cTarget', config['target'], '--cUnknownMacros', config['unknownMacros'],
           '--cDefine', ','.join(k + '=' + v for k, v in config['defines'].items()),
           '--cUndefine', ','.join(config['undefines']),
           '--cIncludeDir', ','.join(config['includeDirs']),
           '--checkerIds', 'callgraph', '--dumpAllCG',
           '--ruleConfigFile', 'resource/example-rule-config/rule_config_c.json',
           '--report', str(OUT / 'report')]
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ENGINE, capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(['git', 'diff', 'HEAD'], cwd=ENGINE, capture_output=True).stdout
    record = dict(tool=TOOL, argv=cmd, cwd=str(ENGINE), engine_base_commit=head,
                  engine_uncommitted_diff_sha256=hashlib.sha256(diff).hexdigest(),
                  node_old_space_mb=HEAP_MB,
                  started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  note='Callback-fix candidate (uncommitted). Same inputs as results/yasa-fixed; no controlled speed ratio is claimed.')
    (OUT / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
    env = os.environ.copy()
    start = time.monotonic()
    with (OUT / 'stdout.log').open('wb') as log:
        code = subprocess.Popen(cmd, cwd=ENGINE, env=env, stdout=log, stderr=subprocess.STDOUT).wait()
    record.update(status='exited', exit_code=code, elapsed_seconds=time.monotonic() - start,
                  completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (OUT / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    return code


def score():
    sys.path.insert(0, str(CURL))
    import export_predictions
    import score as scoring
    export_predictions.BASE = HERE  # export_yasa reads BASE/results/<tool>/report
    normalized = export_predictions.export_yasa(TOOL)
    (OUT / 'normalized.json').write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + '\n')
    gold_path = CURL / 'reference/gold.json'
    curated_path = CURL / 'indirect-audit/indirect-gold.json'
    frame = scoring.build_frame(json.loads(gold_path.read_text()))
    result, mismatches = scoring.score_tool(normalized, frame, json.loads(curated_path.read_text()))
    result.update(scoring_protocol_sha256=scoring.PROTOCOL_SHA256,
                  gold_sha256=hashlib.sha256(gold_path.read_bytes()).hexdigest(),
                  curated_gold_sha256=hashlib.sha256(curated_path.read_bytes()).hexdigest(),
                  normalized_sha256=hashlib.sha256((OUT / 'normalized.json').read_bytes()).hexdigest())
    (OUT / 'score.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'mismatches.json').write_text(json.dumps(mismatches, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in result if k not in ('records',)}, ensure_ascii=False)[:4000])


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    code = run() if step in ('run', 'all') else 0
    if step in ('score', 'all') and code == 0:
        score()
    raise SystemExit(code)
