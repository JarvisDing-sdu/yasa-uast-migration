#!/usr/bin/env python3
"""Run an Engine's full call graph on the frozen curl benchmark and score it.

Same node bundle, argv, inputs, configuration and 8 GB heap as
yasa-c-extension/callgraph-eval/scripts/curl/run_and_score.py; export and scoring
reuse the curl workspace's export_predictions.py and score.py unchanged.

Usage: curl_callgraph_score.py --engine ENGINE_DIR --curl-large DIR --bundle DIR --out DIR
Writes <out>/score.json (primary_strict, full_ast_direct_pair_recall, curated_indirect).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

TOOL = 'yasa'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', required=True)
    ap.add_argument('--curl-large', required=True)
    ap.add_argument('--bundle', required=True, help='directory holding the node binary used for the benchmark')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    curl = Path(a.curl_large).resolve()
    out = Path(a.out).resolve()
    results = out / 'results' / TOOL
    results.mkdir(parents=True, exist_ok=True)
    config = json.loads((curl / 'yasa-run-config.json').read_text())
    cmd = [str(Path(a.bundle) / 'node'), '--max-old-space-size=8192', '--import', 'tsx', 'src/main.ts',
           '--sourcePath', str(curl / 'input'), '--language', 'c',
           '--cTarget', config['target'], '--cUnknownMacros', config['unknownMacros'],
           '--cDefine', ','.join(k + '=' + v for k, v in config['defines'].items()),
           '--cUndefine', ','.join(config['undefines']),
           '--cIncludeDir', ','.join(config['includeDirs']),
           '--checkerIds', 'callgraph', '--dumpAllCG',
           '--ruleConfigFile', 'resource/example-rule-config/rule_config_c.json',
           '--report', str(results / 'report')]
    started = time.monotonic()
    with (results / 'stdout.log').open('wb') as log:
        code = subprocess.run(cmd, cwd=a.engine, stdout=log, stderr=subprocess.STDOUT).returncode
    if code:
        sys.exit(f'engine exited {code}; see {results / "stdout.log"}')
    sys.path.insert(0, str(curl))
    import export_predictions
    import score as scoring
    export_predictions.BASE = out  # export_yasa reads BASE/results/<tool>/report
    normalized = export_predictions.export_yasa(TOOL)
    gold_path = curl / 'reference/gold.json'
    curated_path = curl / 'indirect-audit/indirect-gold.json'
    frame = scoring.build_frame(json.loads(gold_path.read_text()))
    result, _ = scoring.score_tool(normalized, frame, json.loads(curated_path.read_text()))
    keep = {k: result[k] for k in ('primary_strict', 'full_ast_direct_pair_recall', 'curated_indirect')}
    keep['gold_sha256'] = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    keep['elapsed_seconds'] = round(time.monotonic() - started, 1)
    (out / 'score.json').write_text(json.dumps(keep, indent=1) + '\n')
    print(json.dumps({k: keep[k] for k in ('gold_sha256', 'elapsed_seconds')}))


if __name__ == '__main__':
    main()
