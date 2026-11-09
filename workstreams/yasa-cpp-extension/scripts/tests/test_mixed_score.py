"""Black-box evidence corruption tests; no analyzer is needed for scorer tests."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'mixed_regression.py'
spec = importlib.util.spec_from_file_location('mixed_regression', SCRIPT)
m = importlib.util.module_from_spec(spec)
if SCRIPT.exists():
    spec.loader.exec_module(m)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ident(value):
    return sha(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class MixedScore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mixed score ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'run'
        self.root.mkdir()
        self.profile = 'mixed-acceptance-v1'
        self.gold = {'version': 1, 'profileId': self.profile,
                     'frozenBeforeNewMode': True, 'cases': []}
        self.meta = {'schema': 1, 'profileId': self.profile, 'cases': [],
                     'errors': [], 'tools': {}, 'usage': {}}
        (self.root / 'config').mkdir()
        (self.root / 'config/rules.json').write_text('{}')
        self.meta['ruleConfig'] = 'config/rules.json'
        self.meta['ruleConfigSha256'] = sha(b'{}')
        for i in range(27):
            outcome = 'finding' if i < 13 else 'clean' if i < 26 else 'failure'
            name = f'case-{i}' if i < 26 else 'missing_generated_header'
            files = {'main.c': b'int main(void) { return 0; }\n// another valid source line\n',
                     'sink.cpp': b'// source\n// sink\n'}
            if outcome == 'failure':
                files['generated.h'] = b'// generated\n'
            gold = {'goldName': name, 'directory': name, 'outcome': outcome,
                    'programs': [{'domainId': 'app', 'sources': ['main.c', 'sink.cpp']}],
                    'sourceFile': 'main.c', 'sourceLine': 1, 'sinkFile': 'sink.cpp',
                    'sinkLine': 2, 'sinkRule': 'system', 'traceFiles': ['main.c', 'sink.cpp'],
                    'findingDomainId': 'app', 'sha256': {k: sha(v) for k, v in files.items()}}
            self.gold['cases'].append(gold)
            base = f'cases/{name}'
            stage = self.root / base / 'stage'
            stage.mkdir(parents=True)
            for f, data in files.items():
                original = self.root / base / 'inputs' / f
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(data)
                (stage / f).write_bytes(data)
            selected, records, builds = [], [], []
            for n, f in enumerate(['main.c', 'sink.cpp']):
                obj = self.root / base / 'build' / f'{n}.o'
                obj.parent.mkdir(exist_ok=True)
                obj.write_bytes(b'object')
                argv = ['/usr/bin/clang++' if f.endswith('.cpp') else '/usr/bin/clang',
                        '-std=c++17' if f.endswith('.cpp') else '-std=c17',
                        '-c', str(stage / f), '-o', str(obj)]
                entry = ident([str(stage), str(stage / f), argv])
                selected.append({'entryId': entry, 'unitId': ident([self.profile, 'app', entry]),
                                 'domainId': 'app', 'sourceFile': str(stage / f)})
                records.append({'directory': str(stage), 'file': str(stage / f), 'arguments': argv})
                builds.append(self.command(base, f'compile-{n}', argv, str(stage),
                                           output=f'{base}/build/{n}.o', domainId='app', sourceFile=f))
            exe = self.root / base / 'build/program'
            exe.write_bytes(b'linked')
            builds.append(self.command(base, 'link', ['/usr/bin/clang++',
                *[str(self.root / b['output']) for b in builds], '-o', str(exe)],
                str(stage), output=f'{base}/build/program', domainId='app'))
            write(self.root / base / 'compile_commands.json', records)
            write(self.root / base / 'build-profile.json', {'version': 1,
                'profileId': self.profile, 'units': [{'entryId': u['entryId'], 'domainId': 'app'} for u in selected]})
            sabotage = None
            if outcome == 'failure':
                (stage / 'generated.h').unlink()
                sabotage = {'file': 'generated.h', 'action': 'remove_staged_copy_after_link',
                            'sha256': gold['sha256']['generated.h']}
            row = {'goldName': name, 'sourceRoot': str(stage), 'stage': f'{base}/stage',
                   'inputs': f'{base}/inputs', 'sourceSha256': dict(gold['sha256']), 'database': f'{base}/compile_commands.json',
                   'profile': f'{base}/build-profile.json', 'report': f'{base}/report',
                   'selectedUnits': selected, 'build': builds, 'sabotage': sabotage, 'errors': []}
            row['databaseSha256'] = sha((self.root / row['database']).read_bytes())
            row['profileSha256'] = sha((self.root / row['profile']).read_bytes())
            argv = ['node', '--import', 'tsx', 'src/main.ts', '--language', 'c-cpp',
                    '--sourcePath', str(stage), '--compileCommands', str(self.root / row['database']),
                    '--buildProfile', str(self.root / row['profile']), '--report', str(self.root / row['report']),
                    '--ruleConfigFile', str(self.root / self.meta['ruleConfig'])]
            row['scan'] = self.command(base, 'scan', argv, '/recorded/engine')
            if outcome == 'failure':
                row['scan']['exitCode'] = 2
            units = [{**u, 'status': 'analyzed', 'diagnostics': []} for u in selected]
            if outcome == 'failure':
                units[0]['status'] = 'partial'
                units[1]['status'] = 'preprocess_failed'
                units[1]['diagnostics'] = [{'message': 'generated.h not found'}]
            runtime = {'version': 1, 'language': 'c-cpp', 'profileId': self.profile,
                'sourcePath': str(stage), 'status': 'failed' if outcome == 'failure' else 'complete',
                'inputs': {'compileCommands': row['databaseSha256'], 'buildProfile': row['profileSha256'],
                           'ruleConfig': self.meta['ruleConfigSha256']}, 'units': units, 'diagnostics': [],
                'domains': [{'domainId': 'app', 'units': [u['unitId'] for u in selected],
                             'status': 'partial' if outcome == 'failure' else 'complete'}]}
            write(self.root / row['report'] / 'analysis-manifest.json', runtime)
            results = [self.finding(row)] if outcome == 'finding' else []
            write(self.root / row['report'] / 'report.sarif', {'version': '2.1.0', 'runs': [{'results': results}]})
            write(self.root / row['report'] / 'scan_summary.json', {'language': 'c-cpp',
                  'status': runtime['status'], 'fileCount': 2, 'analyzedUnits': 0 if outcome == 'failure' else 2,
                  'findingCount': len(results), 'entryPointCount': 1})
            self.meta['cases'].append(row)
        write(self.root / 'gold.json', self.gold)
        self.meta['goldSha256'] = sha((self.root / 'gold.json').read_bytes())
        self.seal()

    def command(self, base, name, argv, cwd, **extra):
        stdout, stderr = f'{base}/logs/{name}.stdout', f'{base}/logs/{name}.stderr'
        for p in (stdout, stderr):
            path = self.root / p
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'')
        return dict(argv=argv, cwd=cwd, exitCode=0, signal=None, timeout=False,
                    error=None, stdout=stdout, stderr=stderr, **extra)

    def finding(self, row):
        def loc(f, line):
            return {'physicalLocation': {'artifactLocation': {'uri': (Path(row['sourceRoot']) / f).as_uri()},
                                         'region': {'startLine': line}}}
        return {'sinkInfo': {'sinkRule': 'system'}, 'locations': [loc('sink.cpp', 2)],
                'properties': {'cFamily': {'profileId': self.profile, 'domainId': 'app',
                    'unitIds': [u['unitId'] for u in row['selectedUnits']]}},
                'codeFlows': [{'threadFlows': [{'locations': [{'location': loc('main.c', 1)},
                                                            {'location': loc('sink.cpp', 2)}]}]}]}

    def seal(self):
        self.meta['evidence'] = {p.relative_to(self.root).as_posix(): sha(p.read_bytes())
            for p in self.root.rglob('*') if p.is_file() and p.name not in ('run.json', 'run.sha256')}
        write(self.root / 'run.json', self.meta)
        (self.root / 'run.sha256').write_text(sha((self.root / 'run.json').read_bytes()))

    def score(self):
        self.assertTrue(hasattr(m, 'score_run'), 'mixed scorer must expose score_run')
        return m.score_run(self.root)

    def reject(self, case=None):
        result = self.score()
        self.assertFalse(result['formalPassed'])
        self.assertEqual(result['denominator'], {'positive': 13, 'negative': 13, 'failure': 1})
        self.assertTrue(result['integrityErrors'])
        if case is not None:
            self.assertTrue(result['cases'][case]['errors'])
        return result

    def change(self, row, filename, edit):
        path = self.root / row['report'] / filename
        data = json.loads(path.read_text())
        edit(data)
        write(path, data)
        self.seal()  # Semantic checks must catch even internally rehashed invalid evidence.

    def test_complete_run_and_zero_negative(self):
        result = self.score()
        self.assertTrue(result['formalPassed'], result)
        self.assertEqual(result['totals'], {'TP': 13, 'FN': 0, 'TN': 13, 'FP': 0})
        self.assertEqual(result['failureConformance'], {'expected': 1, 'passed': 1, 'failed': 0})

    def test_completed_zero_positive_is_fn(self):
        row = self.meta['cases'][0]
        self.change(row, 'report.sarif', lambda d: d['runs'][0].update(results=[]))
        self.change(row, 'scan_summary.json', lambda d: d.update(findingCount=0))
        result = self.score()
        self.assertFalse(result['formalPassed'])
        self.assertFalse(result['integrityErrors'])
        self.assertEqual(result['totals']['FN'], 1)

    def test_failed_positive_remains_in_denominator(self):
        self.meta['cases'][0]['scan']['exitCode'] = 2
        self.seal()
        result = self.reject(0)
        self.assertEqual(result['totals']['FN'], 1)
        self.assertEqual(result['failedNormalCases'], 1)

    def test_failed_negative_is_never_tn(self):
        self.meta['cases'][13]['scan']['timeout'] = True
        self.seal()
        result = self.reject(13)
        self.assertEqual(result['totals']['TN'], 12)
        self.assertEqual(result['failedNegativeCases'], 1)

    def test_missing_unit(self):
        self.change(self.meta['cases'][0], 'analysis-manifest.json', lambda d: d['units'].pop())
        self.reject(0)

    def test_profile_mismatch(self):
        self.change(self.meta['cases'][0], 'analysis-manifest.json', lambda d: d.update(profileId='other'))
        self.reject(0)

    def test_finding_profile_domain_unit_and_foreign_root(self):
        row = self.meta['cases'][0]
        path = self.root / row['report'] / 'report.sarif'
        original = path.read_bytes()
        for field, value in [('profileId', 'other'), ('domainId', 'other'), ('unitIds', ['other'])]:
            with self.subTest(field=field):
                path.write_bytes(original)
                self.change(row, 'report.sarif', lambda d: d['runs'][0]['results'][0]['properties']['cFamily'].update({field: value}))
                self.reject(0)
        path.write_bytes(original)
        self.change(row, 'report.sarif', lambda d: d['runs'][0]['results'][0]['locations'][0]['physicalLocation']['artifactLocation'].update(uri=Path(self.meta['cases'][1]['sourceRoot'], 'sink.cpp').as_uri()))
        self.reject(0)

    def test_mutation_and_missing_evidence(self):
        row = self.meta['cases'][0]
        paths = [self.root / row['stage'] / 'main.c', self.root / row['profile'],
                 self.root / 'gold.json', self.root / row['scan']['stdout'],
                 self.root / row['report'] / 'report.sarif']
        for path in paths:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.reject()
                path.write_bytes(original)
                path.unlink()
                self.reject()
                path.write_bytes(original)

    def test_rehashed_source_and_profile_mutation(self):
        row = self.meta['cases'][0]
        (self.root / row['stage'] / 'main.c').write_text('mutated\n')
        self.seal()
        self.reject(0)

    def test_summary_disagrees_with_sarif(self):
        self.change(self.meta['cases'][0], 'scan_summary.json', lambda d: d.update(findingCount=0))
        self.reject(0)

    def test_source_exact_line(self):
        row = self.meta['cases'][0]
        self.change(row, 'report.sarif', lambda d: d['runs'][0]['results'][0]['codeFlows'][0]['threadFlows'][0]['locations'][0]['location']['physicalLocation']['region'].update(startLine=2))
        result = self.score()
        self.assertEqual(result['totals']['FN'], 1)
        self.assertFalse(result['formalPassed'])
        self.assertFalse(result['integrityErrors'])

    def test_split_threads_do_not_match(self):
        row = self.meta['cases'][0]
        def split(d):
            threads = d['runs'][0]['results'][0]['codeFlows'][0]['threadFlows']
            steps = threads[0]['locations']
            threads[:] = [{'locations': steps[:1]}, {'locations': steps[1:]}]
        self.change(row, 'report.sarif', split)
        result = self.score()
        self.assertEqual(result['totals']['FN'], 1)
        self.assertFalse(result['formalPassed'])

    def test_wrong_sink_line_does_not_match(self):
        self.change(self.meta['cases'][0], 'report.sarif', lambda d: d['runs'][0]['results'][0]['locations'][0]['physicalLocation']['region'].update(startLine=1))
        self.assertEqual(self.score()['totals']['FN'], 1)

    def test_failure_requires_preprocess_failed_and_nonzero(self):
        self.meta['cases'][-1]['scan']['exitCode'] = 0
        self.seal()
        self.assertEqual(self.reject(26)['failureConformance']['passed'], 0)

    def test_archive_uses_recorded_root_even_if_original_disappears(self):
        archive = self.root.parent / 'archive'
        self.root.rename(archive)
        self.root = archive
        result = self.score()
        self.assertTrue(result['formalPassed'], result)

    def test_missing_run_and_invalid_gold_keep_denominators(self):
        (self.root / 'run.json').unlink()
        self.reject()
        write(self.root / 'gold.json', {'cases': []})
        result = self.reject()
        self.assertEqual(result['totals']['FN'], 13)
        self.assertEqual(result['failedNegativeCases'], 13)

    def test_corrupt_gold_case_never_crashes_score(self):
        self.gold['cases'][0] = {'outcome': 'finding'}
        write(self.root / 'gold.json', self.gold)
        result = self.reject()
        self.assertEqual(result['totals']['FN'], 13)

    def test_rehashed_profile_mutation(self):
        row = self.meta['cases'][0]
        profile = json.loads((self.root / row['profile']).read_text())
        profile['units'][0]['domainId'] = 'other'
        write(self.root / row['profile'], profile)
        row['profileSha256'] = sha((self.root / row['profile']).read_bytes())
        self.seal()
        self.reject(0)

    def test_plain_absolute_and_relative_uris(self):
        row = self.meta['cases'][0]
        def uris(d):
            result = d['runs'][0]['results'][0]
            result['locations'][0]['physicalLocation']['artifactLocation']['uri'] = str(Path(row['sourceRoot']) / 'sink.cpp')
            result['codeFlows'][0]['threadFlows'][0]['locations'][0]['location']['physicalLocation']['artifactLocation']['uri'] = 'main.c'
        self.change(row, 'report.sarif', uris)
        self.assertTrue(self.score()['formalPassed'])

    def test_no_filename_hit_can_cover_other_case(self):
        row = self.meta['cases'][1]
        other = self.finding(self.meta['cases'][0])
        self.change(row, 'report.sarif', lambda d: d['runs'][0].update(results=[other]))
        self.reject(1)

    def test_failure_requires_exact_terminal(self):
        self.change(self.meta['cases'][-1], 'analysis-manifest.json',
                    lambda d: d['units'][1].update(status='parse_failed'))
        self.assertEqual(self.reject(26)['failureConformance']['passed'], 0)

    def test_negatives_with_results_are_false_positives(self):
        row = self.meta['cases'][13]
        self.change(row, 'report.sarif', lambda d: d['runs'][0].update(results=[self.finding(row)]))
        self.change(row, 'scan_summary.json', lambda d: d.update(findingCount=1))
        result = self.score()
        self.assertFalse(result['formalPassed'])
        self.assertEqual(result['totals']['FP'], 1)
        self.assertFalse(result['integrityErrors'])

    def test_unmapped_even_in_nonmatching_finding(self):
        row = self.meta['cases'][0]
        def unmapped(d):
            result = d['runs'][0]['results'][0]
            result['sinkInfo']['sinkRule'] = 'other'
            result['locations'][0]['physicalLocation']['artifactLocation']['uri'] = '/somewhere/sink.cpp'
        self.change(row, 'report.sarif', unmapped)
        self.reject(0)

    def test_extra_report_evidence(self):
        row = self.meta['cases'][0]
        (self.root / row['report'] / 'stale.log').write_text('stale')
        self.reject(0)

    def test_missing_preprocess_failure_not_true_negative(self):
        self.change(self.meta['cases'][-1], 'analysis-manifest.json',
                    lambda d: d['units'][1].update(diagnostics=[]))
        result = self.reject(26)
        self.assertEqual(result['totals']['TN'], 13)
        self.assertEqual(result['failureConformance']['failed'], 1)

    def test_runner_verifies_entire_gold_before_any_copy(self):
        corpus = self.root.parent / 'corpus'
        corpus.mkdir()
        write(corpus / 'gold.json', self.gold)
        for row, case in zip(self.meta['cases'], self.gold['cases']):
            shutil.copytree(self.root / row['inputs'], corpus / case['directory'])
        (corpus / self.gold['cases'][-1]['directory'] / 'sink.cpp').write_text('mutated')
        target = self.root.parent / 'new-run'
        with self.assertRaisesRegex(ValueError, 'source hash/file set mismatch'):
            m.run_regression(Path('/no-engine'), corpus / 'gold.json', target)
        self.assertFalse(target.exists())

    def test_unit_source_domain_cannot_borrow_other_program(self):
        row = self.meta['cases'][0]
        # Add a second link domain with a same-named-looking sink source.
        # A SARIF context selecting app cannot claim a TU belonging to other-app.
        self.gold['cases'][0]['programs'].append({'domainId': 'other-app', 'sources': ['other.cpp']})
        self.gold['cases'][0]['sha256']['other.cpp'] = sha(b'// source\n// sink\n')
        for field in ('inputs', 'stage'):
            (self.root / row[field] / 'other.cpp').write_bytes(b'// source\n// sink\n')
        # Exercise location ownership directly, independently of the archive builder.
        finding = self.finding(row)
        finding['locations'][0]['physicalLocation']['artifactLocation']['uri'] = str(Path(row['sourceRoot']) / 'other.cpp')
        self.assertTrue(hasattr(m, 'validate_finding_locations'))
        with self.assertRaisesRegex(ValueError, 'domain'):
            m.validate_finding_locations(finding, row, self.gold['cases'][0],
                                        self.root / row['inputs'], 'app')

    def test_unknown_case_evidence_cannot_be_ignored(self):
        extra = self.root / 'cases/unknown/logs/scan.stdout'
        extra.parent.mkdir(parents=True)
        extra.write_text('stale')
        self.reject()

    def test_malformed_metadata_cannot_crash_score(self):
        self.meta['cases'][0]['sourceRoot'] = []
        self.seal()
        self.reject()

    def test_score_cli_refuses_overwrite(self):
        target = self.root.parent / 'score.json'
        target.write_text('keep')
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), 'score', '--run', str(self.root), '--json', str(target)], capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(target.read_text(), 'keep')

    def test_runner_refuses_nonempty_out_and_verifies_all_before_staging(self):
        target = self.root.parent / 'nonempty'
        target.mkdir()
        (target / 'keep').write_text('keep')
        with self.assertRaises((ValueError, OSError)):
            m.run_regression(Path('/no-engine'), self.root / 'gold.json', target)
        self.assertEqual([p.name for p in target.iterdir()], ['keep'])


if __name__ == '__main__':
    unittest.main()
