#!/usr/bin/env python3
"""Reproducible frozen mixed C/C++ acceptance runner and evidence scorer.

run --engine ENGINE --manifest fixtures/mixed/gold.json --out NEW_EMPTY_DIR
score --run ARCHIVE --json NEW_FILE

Only compile/link fixture programs; NEVER execute them. Evidence paths are archive
relative, while compiler/SARIF identities use the recorded original stage roots.
Checksums detect corruption, not malicious replacement of the entire archive.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import resource
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

TERMINAL = {'analyzed', 'partial', 'preprocess_failed', 'parse_failed',
            'analysis_failed', 'timed_out', 'unsupported'}
DENOMINATOR = {'positive': 13, 'negative': 13, 'failure': 1}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    """The public Node SHA256(JSON.stringify(array)) contract, including UTF-8."""
    return sha(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value, 'invalid archive path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == value,
            f'unsafe archive path: {value}')
    return p


def archived(root, value):
    p = root / relative(value)
    require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),
            f'archive symlink/escape: {value}')
    return p


def file_list(root):
    require(root.is_dir() and not root.is_symlink(), f'missing directory: {root}')
    files = {}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), f'symlink in evidence: {p}')
        if p.is_file():
            files[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return files


def validate_gold(gold):
    require(isinstance(gold, dict), 'gold must be an object')
    require(gold['version'] == 1 and gold['frozenBeforeNewMode'] is True, 'gold is not frozen version 1')
    require(isinstance(gold['profileId'], str) and gold['profileId'], 'gold profileId missing')
    cases = gold['cases']
    require(isinstance(cases, list) and all(isinstance(c, dict) for c in cases), 'invalid gold cases')
    require(Counter(c['outcome'] for c in cases) == Counter(finding=13, clean=13, failure=1),
            'gold must retain all 13 positives, 13 negatives and one declared failure')
    require(len({c['goldName'] for c in cases}) == 27, 'duplicate gold case')
    require(len({c['directory'] for c in cases}) == 27, 'duplicate gold directory')
    for case in cases:
        relative(case['goldName'])
        relative(case['directory'])
        require(case['programs'] and case['sha256'], 'empty case programs or hashes')
        require(len({p['domainId'] for p in case['programs']}) == len(case['programs']), 'duplicate link domain')
        for f, digest in case['sha256'].items():
            relative(f)
            require(isinstance(digest, str) and len(digest) == 64 and
                    all(c in '0123456789abcdef' for c in digest), f'invalid hash: {f}')
        for program in case['programs']:
            relative(program['domainId'])
            require(program['sources'] and len(set(program['sources'])) == len(program['sources']), 'duplicate/empty program sources')
            require(all(f in case['sha256'] for f in program['sources']), 'TU absent from source hashes')
        if case['outcome'] == 'finding':
            require(case['findingDomainId'] in {p['domainId'] for p in case['programs']}, 'unknown finding domain')
            require(all(f in case['sha256'] for f in [case['sourceFile'], case['sinkFile'], *case['traceFiles']]), 'unhashed gold location')
            require(type(case['sourceLine']) is int and case['sourceLine'] > 0 and
                    type(case['sinkLine']) is int and case['sinkLine'] > 0, 'invalid gold line')
        if case['outcome'] == 'failure':
            require(case['goldName'] == 'missing_generated_header' and 'generated.h' in case['sha256'],
                    'undeclared failure case')


def run_command(root, base, name, argv, cwd, timeout=120, **extra):
    logs = root / base / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    out, err = logs / (name + '.stdout'), logs / (name + '.stderr')
    record = dict(argv=argv, cwd=str(cwd), exitCode=None, signal=None,
                  timeout=False, error=None, stdout=out.relative_to(root).as_posix(),
                  stderr=err.relative_to(root).as_posix(), **extra)
    start = time.monotonic()
    with out.open('xb') as stdout, err.open('xb') as stderr:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record['timeout'] = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            record['exitCode'] = proc.returncode if proc.returncode >= 0 else None
            record['signal'] = -proc.returncode if proc.returncode < 0 else None
        except OSError as error:
            record['error'] = str(error)
    record['elapsedSeconds'] = round(time.monotonic() - start, 6)
    return record


def successful(command):
    return (type(command.get('exitCode')) is int and command['exitCode'] == 0 and command.get('signal') is None and
            command.get('timeout') is False and command.get('error') is None)


def seal(root, metadata):
    metadata['evidence'] = {name: digest for name, digest in file_list(root).items()
                            if name not in ('run.json', 'run.sha256')}
    write_json(root / 'run.json', metadata)
    (root / 'run.sha256').write_text(sha((root / 'run.json').read_bytes()) + '\n', encoding='utf-8')


def run_regression(engine, manifest, out, timeout=120):
    engine, manifest, out = Path(engine).resolve(), Path(manifest).resolve(), Path(out).resolve()
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())), 'output directory must be empty/new')
    require(not out.is_relative_to(manifest.parent) and not manifest.is_relative_to(out), 'output overlaps frozen fixtures')
    gold_bytes = manifest.read_bytes()
    gold = json.loads(gold_bytes)
    validate_gold(gold)
    # All input bytes must be checked before creating even the first staged copy.
    for case in gold['cases']:
        actual = file_list(manifest.parent / relative(case['directory']))
        require(actual == case['sha256'], f"frozen source hash/file set mismatch: {case['goldName']}")
    require((engine / 'src/main.ts').is_file(), 'engine must contain src/main.ts')
    rules = engine / 'resource/example-rule-config/rule_config_c_family.json'
    require(rules.is_file(), 'mixed rule configuration missing')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'gold.json').write_bytes(gold_bytes)
    (out / 'config').mkdir()
    shutil.copyfile(rules, out / 'config/rules.json')
    start = time.monotonic()
    metadata = {'schema': 1, 'profileId': gold['profileId'], 'goldSha256': sha(gold_bytes),
                'originalManifest': str(manifest), 'engine': str(engine), 'recordedRoot': str(out),
                'ruleConfig': 'config/rules.json', 'ruleConfigSha256': sha(rules.read_bytes()),
                'started': datetime.now(timezone.utc).isoformat(), 'cases': [], 'errors': [],
                'tools': {}, 'usage': {}, 'limits': {'scanTimeoutSeconds': timeout,
                'buildTimeoutSeconds': 60, 'executesFixturePrograms': False,
                'checksumsAreNotSignatures': True}}
    try:
        compilers = {'c': shutil.which('clang'), 'cpp': shutil.which('clang++'), 'node': shutil.which('node')}
        require(all(compilers.values()), 'clang, clang++ and node must be installed')
        for name, executable in compilers.items():
            metadata['tools'][name] = {'path': executable, 'sha256': sha(Path(executable).read_bytes()),
                'version': run_command(out, 'tools', name, [executable, '--version'], engine, 30)}
        # Copy and compile/link EVERY fixture before the first analyzer invocation.
        for case in gold['cases']:
            name = case['goldName']
            base = f'cases/{name}'
            inputs, stage = out / base / 'inputs', out / base / 'stage'
            shutil.copytree(manifest.parent / case['directory'], inputs)
            require(file_list(inputs) == case['sha256'], f'input changed during copy: {name}')
            shutil.copytree(inputs, stage)
            row = {'goldName': name, 'sourceRoot': str(stage), 'inputs': f'{base}/inputs',
                   'stage': f'{base}/stage', 'sourceSha256': dict(case['sha256']), 'database': f'{base}/compile_commands.json',
                   'profile': f'{base}/build-profile.json', 'report': f'{base}/report',
                   'selectedUnits': [], 'build': [], 'scan': None, 'sabotage': None, 'errors': []}
            metadata['cases'].append(row)
            records = []
            for program in case['programs']:
                build = out / base / 'build' / program['domainId']
                build.mkdir(parents=True)
                objects = []
                for index, source in enumerate(program['sources']):
                    cpp = source.endswith(('.cpp', '.cc', '.cxx', '.C'))
                    obj = build / f'{index}.o'
                    argv = [compilers['cpp' if cpp else 'c'], '-std=c++17' if cpp else '-std=c17',
                            '-c', str(stage / source), '-o', str(obj)]
                    entry = identity([str(stage), str(stage / source), argv])
                    row['selectedUnits'].append({'entryId': entry,
                        'unitId': identity([gold['profileId'], program['domainId'], entry]),
                        'domainId': program['domainId'], 'sourceFile': str(stage / source)})
                    records.append({'directory': str(stage), 'file': str(stage / source), 'arguments': argv})
                    cmd = run_command(out, base, f"compile-{program['domainId']}-{index}", argv, stage, 60,
                        domainId=program['domainId'], sourceFile=source, output=obj.relative_to(out).as_posix())
                    row['build'].append(cmd)
                    if not successful(cmd) or not obj.exists() or not obj.stat().st_size:
                        row['errors'].append(f'compile proof failed: {source}')
                    objects.append(str(obj))
                exe = build / 'fixture-program'
                cmd = run_command(out, base, f"link-{program['domainId']}",
                    [compilers['cpp'], *objects, '-o', str(exe)], stage, 60,
                    domainId=program['domainId'], output=exe.relative_to(out).as_posix())
                row['build'].append(cmd)
                if not successful(cmd) or not exe.exists() or not exe.stat().st_size:
                    row['errors'].append(f"link proof failed: {program['domainId']}")
            write_json(out / row['database'], records)
            write_json(out / row['profile'], {'version': 1, 'profileId': gold['profileId'],
                'units': [{'entryId': u['entryId'], 'domainId': u['domainId']} for u in row['selectedUnits']]})
            row['databaseSha256'] = sha((out / row['database']).read_bytes())
            row['profileSha256'] = sha((out / row['profile']).read_bytes())
            print(f"[build] {name}: {len(records)} TUs, {len(case['programs'])} link(s), errors={len(row['errors'])}", flush=True)
        for row in metadata['cases']:
            if row['goldName'] == 'missing_generated_header' and not row['errors']:
                header = out / row['stage'] / 'generated.h'
                row['sabotage'] = {'file': 'generated.h', 'action': 'remove_staged_copy_after_link',
                                   'sha256': sha(header.read_bytes())}
                header.unlink()
        for row in metadata['cases']:
            report = out / row['report']
            require(not report.exists(), 'report must be fresh')
            argv = [compilers['node'], '--import', 'tsx', 'src/main.ts', '--language', 'c-cpp',
                    '--sourcePath', row['sourceRoot'], '--compileCommands', str(out / row['database']),
                    '--buildProfile', str(out / row['profile']), '--report', str(report),
                    '--ruleConfigFile', str(out / metadata['ruleConfig'])]
            row['scan'] = run_command(out, f"cases/{row['goldName']}", 'scan', argv, engine, timeout)
            print(f"[scan] {row['goldName']}: exit={row['scan']['exitCode']} signal={row['scan']['signal']} timeout={row['scan']['timeout']}", flush=True)
    except (ValueError, OSError, KeyError, TypeError) as error:
        metadata['errors'].append(str(error))
    finally:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        metadata['usage'] = {'elapsedSeconds': round(time.monotonic() - start, 6),
            'childUserSeconds': usage.ru_utime, 'childSystemSeconds': usage.ru_stime,
            'childMaxRss': usage.ru_maxrss, 'maxRssUnit': 'bytes' if sys.platform == 'darwin' else 'KiB',
            'maxRssMeaning': 'OS child-process high-water mark; not aggregate concurrent memory'}
        metadata['finished'] = datetime.now(timezone.utc).isoformat()
        seal(out, metadata)
    return metadata


def normalize_uri(uri, source_root, gold, inputs):
    """Lexical mapping deliberately never resolves against the current filesystem."""
    require(isinstance(uri, str) and uri and '\\' not in uri, 'missing/invalid location URI')
    parsed = urlsplit(uri)
    if parsed.scheme:
        require(parsed.scheme == 'file' and parsed.netloc in ('', 'localhost') and
                not parsed.query and not parsed.fragment, f'unmapped URI: {uri}')
        path = unquote(parsed.path)
        require(path.startswith('/'), f'nonabsolute file URI: {uri}')
    else:
        require(not parsed.netloc and not parsed.query and not parsed.fragment, f'unmapped URI: {uri}')
        path = unquote(parsed.path)
    path = posixpath.normpath(path if path.startswith('/') else posixpath.join(source_root, path))
    root = posixpath.normpath(source_root)
    require(root.startswith('/') and path.startswith(root + '/'), f'location outside recorded stage root: {uri}')
    rel = path[len(root) + 1:]
    require(rel in gold['sha256'] and (inputs / rel).is_file(), f'unmapped location: {uri}')
    return rel


def locations(value):
    if isinstance(value, dict):
        if 'physicalLocation' in value:
            yield value['physicalLocation']
        for child in value.values():
            yield from locations(child)
    elif isinstance(value, list):
        for child in value:
            yield from locations(child)


def physical_location(loc, row, gold, inputs):
    artifact = loc['artifactLocation']
    require('uriBaseId' not in artifact, 'unresolved SARIF uriBaseId')
    file = normalize_uri(artifact['uri'], row['sourceRoot'], gold, inputs)
    line = loc['region']['startLine']
    lines = (inputs / file).read_text(encoding='utf-8').splitlines()
    require(type(line) is int and 0 < line <= len(lines), f'unmapped source line: {file}:{line}')
    end = loc['region'].get('endLine', line)
    require(type(end) is int and line <= end <= len(lines), f'unmapped end line: {file}:{end}')
    return file, line


def validate_finding_locations(finding, row, gold, inputs, domain):
    """Known translation units must belong to the finding's selected link domain."""
    all_tus = {f for p in gold['programs'] for f in p['sources']}
    own_tus = {f for p in gold['programs'] if p['domainId'] == domain for f in p['sources']}
    for loc in locations(finding):
        file, _ = physical_location(loc, row, gold, inputs)
        require(file not in all_tus or file in own_tus, f'location belongs to another domain: {file}')


def checked_command(root, cmd):
    require(isinstance(cmd, dict) and isinstance(cmd['argv'], list) and cmd['argv'] and
            all(isinstance(arg, str) and '\0' not in arg for arg in cmd['argv']), 'missing command argv')
    require(isinstance(cmd['cwd'], str) and cmd['cwd'].startswith('/'), 'command cwd must be absolute')
    for name in ('stdout', 'stderr'):
        require(archived(root, cmd[name]).is_file(), f'missing raw {name} log')
    require(type(cmd['timeout']) is bool and (cmd['signal'] is None or type(cmd['signal']) is int), 'missing command terminal fields')
    require('exitCode' in cmd and 'error' in cmd, 'missing command exit/error')


def expected_units(root, row, gold, profile_id):
    database = read_json(archived(root, row['database']))
    profile = read_json(archived(root, row['profile']))
    require(profile['version'] == 1 and profile['profileId'] == profile_id, 'profile identity mismatch')
    expected_pairs = [(p['domainId'], f) for p in gold['programs'] for f in p['sources']]
    require(len(database) == len(expected_pairs), 'database TU count mismatch')
    entries = {}
    for record in database:
        directory = posixpath.normpath(posixpath.join(posixpath.dirname(row['sourceRoot']), record['directory']))
        source = posixpath.normpath(posixpath.join(directory, record['file']))
        require(directory == row['sourceRoot'], 'database directory differs from recorded stage')
        normalize_uri(source, row['sourceRoot'], gold, archived(root, row['inputs']))
        entry = identity([directory, source, record['arguments']])
        require(entry not in entries, 'duplicate compile entry')
        entries[entry] = (source, record['arguments'])
    selected = []
    require(len(profile['units']) == len(expected_pairs), 'profile selected unit count mismatch')
    for p in profile['units']:
        require(p['entryId'] in entries, 'unknown profile entry')
        source, _ = entries[p['entryId']]
        selected.append({'entryId': p['entryId'], 'unitId': identity([profile_id, p['domainId'], p['entryId']]),
                         'domainId': p['domainId'], 'sourceFile': source})
    actual_pairs = [(u['domainId'], normalize_uri(u['sourceFile'], row['sourceRoot'], gold, archived(root, row['inputs']))) for u in selected]
    require(Counter(actual_pairs) == Counter(expected_pairs), 'profile gold TU/domain mismatch')
    require(len({u['unitId'] for u in selected}) == len(selected), 'duplicate selected unit')
    require(sorted(selected, key=lambda x: x['unitId']) == sorted(row['selectedUnits'], key=lambda x: x['unitId']), 'recorded selected unit identities mismatch')
    return selected, entries


def verify_case(root, row, gold, metadata):
    require(not row['errors'], f"runner errors: {row['errors']}")
    inputs, stage = archived(root, row['inputs']), archived(root, row['stage'])
    require(row['sourceSha256'] == gold['sha256'], 'recorded source hashes differ from gold')
    require(file_list(inputs) == gold['sha256'], 'frozen archived source hash/file set mismatch')
    staged_hashes = dict(gold['sha256'])
    failure = gold['outcome'] == 'failure'
    if failure:
        require(row['sabotage'] == {'file': 'generated.h', 'action': 'remove_staged_copy_after_link',
                'sha256': gold['sha256']['generated.h']}, 'missing/invalid declared sabotage')
        staged_hashes.pop('generated.h')
    else:
        require(row['sabotage'] is None, 'undeclared sabotage')
    require(file_list(stage) == staged_hashes, 'staged source hash/file set mismatch')
    for path_key, hash_key in [('database', 'databaseSha256'), ('profile', 'profileSha256')]:
        require(sha(archived(root, row[path_key]).read_bytes()) == row[hash_key], f'{path_key} hash mismatch')
    selected, entries = expected_units(root, row, gold, metadata['profileId'])
    # A compile proof for every selected TU and one link proof per actual program.
    require(len(row['build']) == len(selected) + len(gold['programs']), 'missing compile/link proof')
    compiled, linked = [], []
    for cmd in row['build']:
        checked_command(root, cmd)
        require(successful(cmd), 'failed compile/link proof')
        product = archived(root, cmd['output'])
        require(product.is_file() and product.stat().st_size > 0, 'missing compile/link product')
        if 'sourceFile' in cmd:
            source = posixpath.join(row['sourceRoot'], cmd['sourceFile'])
            unit = next((u for u in selected if u['domainId'] == cmd['domainId'] and u['sourceFile'] == source), None)
            require(unit is not None and cmd['argv'] == entries[unit['entryId']][1], 'compile argv/TU mismatch')
            compiled.append(unit['unitId'])
        else:
            require(cmd['domainId'] in {p['domainId'] for p in gold['programs']}, 'unknown link domain')
            object_paths = [b['argv'][b['argv'].index('-o') + 1] for b in row['build']
                            if b.get('domainId') == cmd['domainId'] and 'sourceFile' in b]
            require(cmd['argv'][1:-2] == object_paths and cmd['argv'][-2] == '-o', 'link objects/domain mismatch')
            linked.append(cmd['domainId'])
    require(Counter(compiled) == Counter(u['unitId'] for u in selected), 'missing/duplicate TU compile proof')
    require(Counter(linked) == Counter(p['domainId'] for p in gold['programs']), 'missing/duplicate program link proof')
    scan = row['scan']
    checked_command(root, scan)
    argv = scan['argv']
    require(argv[1:4] == ['--import', 'tsx', 'src/main.ts'], 'scan must invoke public CLI')
    for flag, value in [('--language', 'c-cpp'), ('--sourcePath', row['sourceRoot'])]:
        require(argv.count(flag) == 1 and argv[argv.index(flag) + 1] == value, f'scan argv mismatch: {flag}')
    # Compare original absolute paths lexically; archived files can live elsewhere.
    recorded_base = posixpath.dirname(row['sourceRoot'])
    for flag, suffix in [('--compileCommands', 'compile_commands.json'), ('--buildProfile', 'build-profile.json'), ('--report', 'report')]:
        require(argv.count(flag) == 1 and argv[argv.index(flag) + 1] == posixpath.join(recorded_base, suffix), f'scan argv mismatch: {flag}')
    require(scan['signal'] is None and scan['timeout'] is False and scan['error'] is None, 'scan interrupted/errored')
    report = archived(root, row['report'])
    runtime = read_json(report / 'analysis-manifest.json')
    require(runtime['language'] == 'c-cpp' and runtime['profileId'] == metadata['profileId'] and
            runtime['sourcePath'] == row['sourceRoot'], 'runtime profile/source root mismatch')
    require(runtime['inputs'] == {'compileCommands': row['databaseSha256'], 'buildProfile': row['profileSha256'],
                                 'ruleConfig': metadata['ruleConfigSha256']}, 'runtime input hashes mismatch')
    units = runtime['units']
    require(len(units) == len(selected) and len({u['unitId'] for u in units}) == len(selected), 'missing/duplicate runtime TU')
    require({u['unitId'] for u in units} == {u['unitId'] for u in selected}, 'runtime selected units differ')
    for u in units:
        expected = next(e for e in selected if e['unitId'] == u['unitId'])
        require(u['domainId'] == expected['domainId'] and u['sourceFile'] == expected['sourceFile'], 'runtime TU/domain identity mismatch')
        require(u['status'] in TERMINAL and isinstance(u['diagnostics'], list), 'nonterminal runtime unit')
        if 'profileId' in u:
            require(u['profileId'] == metadata['profileId'], 'runtime TU profile mismatch')
    domains = runtime['domains']
    require(Counter(d['domainId'] for d in domains) == Counter(p['domainId'] for p in gold['programs']), 'runtime domains mismatch')
    for domain in domains:
        require(Counter(domain['units']) == Counter(u['unitId'] for u in selected if u['domainId'] == domain['domainId']), 'domain selected units mismatch')
    require(isinstance(runtime['diagnostics'], list), 'missing runtime diagnostics')
    summary = read_json(report / 'scan_summary.json')
    require(summary['language'] == 'c-cpp' and summary['status'] == runtime['status'], 'summary status mismatch')
    require(summary['fileCount'] == len(selected) and summary['analyzedUnits'] == sum(u['status'] == 'analyzed' for u in units), 'summary TU coverage mismatch')
    sarif = read_json(report / 'report.sarif')
    require(sarif['version'] == '2.1.0' and isinstance(sarif['runs'], list) and sarif['runs'], 'missing SARIF runs')
    findings = []
    for run in sarif['runs']:
        require(isinstance(run['results'], list), 'missing SARIF results')
        findings.extend(run['results'])
    require(type(summary['findingCount']) is int and summary['findingCount'] == len(findings), 'summary findingCount/SARIF mismatch')
    if failure:
        require(type(scan['exitCode']) is int and scan['exitCode'] != 0 and runtime['status'] in ('failed', 'partial'), 'declared failure must exit nonzero')
        failed = next(u for u in units if u['sourceFile'] == posixpath.join(row['sourceRoot'], gold['sinkFile']))
        require(failed['status'] == 'preprocess_failed' and failed['diagnostics'] and
                'generated.h' in json.dumps(failed['diagnostics']), 'missing-header preprocess_failed evidence required')
    else:
        require(successful(scan) and runtime['status'] == 'complete' and all(u['status'] == 'analyzed' for u in units), 'failed normal run')
        require(all(d['status'] == 'complete' for d in domains), 'incomplete link domain')
        require(type(summary['entryPointCount']) is int and summary['entryPointCount'] > 0, 'no analyzed entrypoints')
    matched = False
    for finding in findings:
        context = finding['properties']['cFamily']
        require(context['profileId'] == metadata['profileId'], 'finding profile mismatch')
        domain_units = [u for u in selected if u['domainId'] == context['domainId']]
        require(domain_units and Counter(context['unitIds']) == Counter(u['unitId'] for u in domain_units), 'finding domain/unit mismatch')
        require(finding['locations'], 'finding missing sink')
        # Validate every published location, including related locations, not just hits.
        validate_finding_locations(finding, row, gold, inputs, context['domainId'])
        sink = physical_location(finding['locations'][0]['physicalLocation'], row, gold, inputs)
        if gold['outcome'] != 'finding' or context['domainId'] != gold['findingDomainId']:
            continue
        if finding.get('sinkInfo', {}).get('sinkRule') != gold['sinkRule'] or sink != (gold['sinkFile'], gold['sinkLine']):
            continue
        for flow in finding.get('codeFlows', []):
            for thread in flow.get('threadFlows', []):
                steps = [physical_location(s['location']['physicalLocation'], row, gold, inputs) for s in thread.get('locations', [])]
                if ((gold['sourceFile'], gold['sourceLine']) in steps and
                        set(gold['traceFiles']).issubset({f for f, _ in steps})):
                    matched = True
    return matched, len(findings)


def score_run(directory):
    """Return partial counts and integrity errors even when a formal pass is refused."""
    root = Path(directory).resolve()
    result = {'schema': 1, 'formalPassed': False, 'denominator': dict(DENOMINATOR),
              'totals': {'TP': 0, 'FN': 0, 'TN': 0, 'FP': 0}, 'failedNormalCases': 0,
              'failedNegativeCases': 0, 'failureConformance': {'expected': 1, 'passed': 0, 'failed': 1},
              'integrityErrors': [], 'cases': [], 'usage': {}, 'partial': True,
              'limits': ['Checksums detect corruption; they do not authenticate a wholly replaced archive.',
                         'Synthetic fixture acceptance does not measure real-project recall.']}
    errors = result['integrityErrors']
    scoped_errors = {}
    metadata, gold = None, None
    gold_valid = False
    try:
        metadata = read_json(root / 'run.json')
        require(isinstance(metadata, dict), 'run metadata must be an object')
        require(metadata['schema'] == 1, 'unknown run schema')
        require(sha((root / 'run.json').read_bytes()) == (root / 'run.sha256').read_text().strip(), 'run metadata hash mismatch')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f'run metadata: {error}')
    try:
        gold = read_json(root / 'gold.json')
        validate_gold(gold)
        gold_valid = True
        require(metadata is not None and sha((root / 'gold.json').read_bytes()) == metadata['goldSha256'], 'gold hash mismatch')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f'gold: {error}')
    if isinstance(metadata, dict):
        try:
            require(not metadata['errors'], f"runner errors: {metadata['errors']}")
            require(gold is not None and metadata['profileId'] == gold['profileId'], 'run/gold profile mismatch')
            rule = archived(root, metadata['ruleConfig'])
            require(sha(rule.read_bytes()) == metadata['ruleConfigSha256'], 'rule config hash mismatch')
            evidence = metadata['evidence']
            require(isinstance(evidence, dict) and evidence, 'missing evidence hash inventory')
            actual = file_list(root)
            for path, digest in evidence.items():
                relative(path)
                if actual.get(path) != digest:
                    if path.startswith('cases/') and len(PurePosixPath(path).parts) > 2:
                        name = PurePosixPath(path).parts[1]
                        scoped_errors.setdefault(name, []).append(f'evidence missing/mutated: {path}')
                    else:
                        errors.append(f'evidence missing/mutated: {path}')
            # Extra evidence under a report/stage/build is also stale input.
            for path in actual:
                if path.startswith(('cases/', 'config/', 'tools/')):
                    if path not in evidence:
                        if path.startswith('cases/') and len(PurePosixPath(path).parts) > 2:
                            scoped_errors.setdefault(PurePosixPath(path).parts[1], []).append(f'unrecorded evidence: {path}')
                        else:
                            errors.append(f'unrecorded evidence: {path}')
            result['usage'] = metadata.get('usage', {})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f'evidence: {error}')
    known_names = {c['goldName'] for c in gold['cases']} if gold_valid else set()
    for name in set(scoped_errors) - known_names:
        errors.extend(scoped_errors[name])
    global_bad = bool(errors)
    if not gold_valid:
        result['totals']['FN'] = 13
        result['failedNormalCases'] = 26
        result['failedNegativeCases'] = 13
        return result
    rows = metadata.get('cases', []) if isinstance(metadata, dict) else []
    if not isinstance(rows, list) or not all(isinstance(r, dict) and
            isinstance(r.get('goldName'), str) and isinstance(r.get('sourceRoot'), str) and
            r['sourceRoot'].startswith('/') for r in rows):
        errors.append('invalid run case records')
        rows = []
        global_bad = True
    if Counter(r.get('goldName') for r in rows) != Counter(c['goldName'] for c in gold['cases']):
        errors.append('run case selection differs from frozen gold')
        global_bad = True
    roots = [r.get('sourceRoot') for r in rows]
    if len(set(roots)) != len(roots):
        errors.append('cases share recorded stage roots')
        global_bad = True
    for case in gold['cases']:
        row_errors = list(scoped_errors.get(case['goldName'], []))
        matched, count = False, None
        row = next((r for r in rows if r.get('goldName') == case['goldName']), None)
        try:
            require(row is not None, 'case evidence missing')
            matched, count = verify_case(root, row, case, metadata)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration, IndexError) as error:
            row_errors.append(str(error) or type(error).__name__)
        if global_bad:
            row_errors.append('archive integrity validation failed')
        for error in row_errors:
            errors.append(f"{case['goldName']}: {error}")
        valid = not row_errors
        if case['outcome'] == 'failure':
            outcome = 'EXPECTED_FAILURE' if valid else 'FAILED_CONFORMANCE'
            result['failureConformance'] = {'expected': 1, 'passed': int(valid), 'failed': int(not valid)}
        elif case['outcome'] == 'finding':
            outcome = 'TP' if valid and matched else 'FN'
            result['totals'][outcome] += 1
        else:
            outcome = 'FAILED' if not valid else 'FP' if count else 'TN'
            if valid:
                result['totals'][outcome] += 1
            else:
                result['failedNegativeCases'] += 1
        if case['outcome'] != 'failure' and not valid:
            result['failedNormalCases'] += 1
        result['cases'].append({'goldName': case['goldName'], 'expected': case['outcome'],
                                'outcome': outcome, 'findingCount': count, 'errors': row_errors})
    result['formalPassed'] = (not errors and result['totals'] == {'TP': 13, 'FN': 0, 'TN': 13, 'FP': 0}
                              and result['failureConformance']['passed'] == 1)
    result['partial'] = bool(errors)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--engine', required=True, type=Path)
    run.add_argument('--manifest', required=True, type=Path)
    run.add_argument('--out', required=True, type=Path)
    run.add_argument('--timeout', type=float, default=120, help='per CLI invocation, seconds (default 120)')
    score = commands.add_parser('score')
    score.add_argument('--run', required=True, type=Path)
    score.add_argument('--json', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            require(args.timeout > 0, 'timeout must be positive')
            metadata = run_regression(args.engine, args.manifest, args.out, args.timeout)
            scored = score_run(args.out)
            print(json.dumps({k: scored[k] for k in ('formalPassed', 'denominator', 'totals', 'failedNormalCases', 'failureConformance', 'usage')}, indent=2))
            return 0 if scored['formalPassed'] and not metadata['errors'] else 2
        require(not args.json.exists(), 'score JSON must be a new file')
        scored = score_run(args.run)
        write_json(args.json, scored)
        print(json.dumps({k: scored[k] for k in ('formalPassed', 'denominator', 'totals', 'failedNormalCases', 'failureConformance', 'usage')}, indent=2))
        return 0 if scored['formalPassed'] else 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
