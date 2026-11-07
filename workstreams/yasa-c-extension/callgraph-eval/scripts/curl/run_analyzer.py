#!/usr/bin/env python3
"""Run frozen analyzers serially and retain exact argv, output, exit and timing."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

base = Path(__file__).resolve().parent
root = base.parents[1]
tool = sys.argv[1]
engine = (base / 'fixed-engine') if tool == 'yasa-fixed' else root / 'work/official-c-integration/engine'
bundle = root / 'work/tools/codegraph-v1.6.2/codegraph-darwin-arm64'
out = base / 'results' / tool
out.mkdir(parents=True, exist_ok=True)
config = json.loads((base / 'yasa-run-config.json').read_text())
env = os.environ.copy()
env.update(CODEGRAPH_TELEMETRY='0', DO_NOT_TRACK='1', CODEGRAPH_NO_DAEMON='1')
if tool in ('yasa', 'yasa-fixed'):
    node_options = []
    if os.environ.get('YASA_HEAP_MB'):
        node_options += ['--max-old-space-size=' + str(int(os.environ['YASA_HEAP_MB']))]
    if os.environ.get('YASA_INSPECT') == '1':
        node_options += ['--inspect=127.0.0.1:0']
    cmd = [str(bundle / 'node'), *node_options, '--import', 'tsx', 'src/main.ts',
           '--sourcePath', str(base / 'input'), '--language', 'c',
           '--cTarget', config['target'], '--cUnknownMacros', config['unknownMacros'],
           '--cDefine', ','.join(k + '=' + v for k, v in config['defines'].items()),
           '--cUndefine', ','.join(config['undefines']),
           '--cIncludeDir', ','.join(config['includeDirs']),
           '--checkerIds', 'callgraph', '--dumpAllCG',
           '--ruleConfigFile', 'resource/example-rule-config/rule_config_c.json',
           '--report', str(out / 'report')]
    cwd = engine
elif tool == 'codegraph':
    cmd = [str(bundle / 'bin/codegraph'), 'init', '--yes', str(base / 'input')]
    cwd = root
else:
    raise SystemExit('Expected yasa, yasa-fixed or codegraph')
record = dict(tool=tool, argv=cmd, cwd=str(cwd),
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              timeout_seconds=None,
              timing_note='No compiler/reference workload. See concurrency-note.json for analyzer overlap; no controlled speed ratio is claimed.')
(out / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
start = time.monotonic()
with (out / 'stdout.log').open('wb') as log:
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    print(f'{tool} PID {proc.pid}; log: {out / "stdout.log"}', flush=True)
    try:
        code = proc.wait()
        record['status'] = 'exited'
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        code = proc.returncode
        record['status'] = 'timeout'
record.update(exit_code=code, elapsed_seconds=time.monotonic() - start,
              completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(out / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2), flush=True)
raise SystemExit(code if code and code > 0 else 0)
