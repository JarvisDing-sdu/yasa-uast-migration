#!/usr/bin/env python3
"""Freeze inputs, run configured dumpAllAST, and audit both parser backends."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def walk(root):
    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            yield node
            pending.extend(value for key, value in node.items() if key not in ('_meta', 'loc', 'parent'))
        elif isinstance(node, list):
            pending.extend(node)


def snapshot(project):
    files = {}
    for folder in project['snapshotRoots']:
        root = Path(folder).resolve()
        for file in sorted(root.rglob('*')):
            if '.git' in file.parts or not file.is_file():
                continue
            if file.suffix.lower() in ('.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.inc', '.in'):
                files[str(file)] = sha(file)
    return {'project': project, 'databaseSha256': sha(Path(project['database'])), 'files': files}


def audit(directory, expected):
    manifest = json.loads((directory / 'manifest.json').read_text())
    roots = collections.Counter()
    unsupported = collections.Counter()
    conversion = collections.Counter()
    functions = 0
    invalid = []
    for row in manifest['results']:
        conversion.update(row.get('conversionDiagnostics', {}))
        if not row.get('output'):
            continue
        file = directory / row['output']
        try:
            ast = json.loads(file.read_text())
            roots[ast.get('type')] += 1
            if ast.get('type') != 'CompileUnit':
                invalid.append({'file': row['sourceFile'], 'error': 'unexpected root'})
            for node in walk(ast):
                functions += node.get('type') == 'FunctionDefinition'
                kind = node.get('_meta', {}).get('unhandled', {}).get('kind')
                if kind:
                    unsupported[kind] += 1
        except (ValueError, OSError) as error:
            invalid.append({'file': row['sourceFile'], 'error': str(error)})
    return {'expectedCommands': expected, 'selectedCommands': manifest['total'], 'completed': manifest['completed'],
            'coverageMatches': manifest['total'] == manifest['completed'] == expected,
            'statuses': dict(collections.Counter(row['status'] for row in manifest['results'])),
            'syntaxDiagnostics': sum(row.get('diagnostics', 0) for row in manifest['results']),
            'roots': dict(roots), 'functionDefinitionRecords': functions,
            'unhandledNodes': dict(unsupported), 'conversionDiagnostics': dict(conversion), 'invalidExports': invalid, 'manifestSha256': sha(directory / 'manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    engine = args.engine.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    frozen = [snapshot(project) for project in config['projects']]
    write(args.out / 'inputs.lock.json', frozen)
    with (args.out / 'engine.patch').open('w') as stream:
        subprocess.run(['git', 'diff', 'HEAD'], cwd=engine, stdout=stream, check=True)
    source_hashes = {str(file.relative_to(engine)): sha(file) for folder in ['src/engine/parser/c-family', 'src/interface', 'node_modules/@ant-yasa/uast-parser-c', 'node_modules/@ant-yasa/uast-parser-cpp']
                     for file in (engine / folder).rglob('*') if file.is_file() and file.suffix in ('.ts', '.js', '.wasm', '.json')}
    write(args.out / 'engine-source-sha256.json', source_hashes)
    results = []
    for project in config['projects']:
        records = json.loads(Path(project['database']).read_text())
        for backend in config['backends']:
            directory = args.out / f"{project['name']}-{backend}"
            command = ['node', '--max-old-space-size=4096', '--import', 'tsx', 'src/main.ts',
                       '--sourcePath', project['sourcePath'], '--language', project['language'], '--dumpAllAST',
                       '--cCompileCommands', project['database'], '--cAstBackend', backend, '--report', str(directory.resolve())]
            row = {'project': project['name'], 'role': project['role'], 'backend': backend, 'command': command}
            start = time.monotonic()
            with (args.out / f"{project['name']}-{backend}.log").open('w') as stream:
                try:
                    result = subprocess.run(command, cwd=engine, stdout=stream, stderr=subprocess.STDOUT, timeout=config.get('timeoutSeconds', 600))
                    row['exitCode'] = result.returncode
                except subprocess.TimeoutExpired:
                    row['exitCode'] = None
                    row['timeout'] = True
            row['seconds'] = round(time.monotonic() - start, 3)
            try:
                row.update(audit(directory, len(records)))
            except (OSError, ValueError, KeyError) as error:
                row['auditError'] = str(error)
            results.append(row)
            write(args.out / 'summary.json', results)
            print(project['name'], backend, row.get('statuses', row.get('auditError')), flush=True)
    unchanged = frozen == [snapshot(project) for project in config['projects']]
    final_hashes = {str(file.relative_to(engine)): sha(file) for folder in ['src/engine/parser/c-family', 'src/interface', 'node_modules/@ant-yasa/uast-parser-c', 'node_modules/@ant-yasa/uast-parser-cpp']
                    for file in (engine / folder).rglob('*') if file.is_file() and file.suffix in ('.ts', '.js', '.wasm', '.json')}
    code_unchanged = source_hashes == final_hashes
    write(args.out / 'input-integrity.json', {'unchangedDuringRun': unchanged, 'implementationUnchangedDuringRun': code_unchanged})
    return int(not unchanged or not code_unchanged or any(row.get('exitCode') != 0 or not row.get('coverageMatches') or row.get('invalidExports') or row.get('syntaxDiagnostics', 0) > 0 for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
