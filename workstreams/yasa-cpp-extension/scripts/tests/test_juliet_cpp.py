"""Scoring must distinguish completed scans from missing evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'juliet_cpp.py'
spec = importlib.util.spec_from_file_location('juliet_cpp', SCRIPT)
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)


class ScoreEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.out = root / 'out'
        self.src = self.out / 'src-000'
        self.report = self.out / 'report-000'
        corpus = root / 'juliet' / 'testcases' / 'X'
        for d in (self.src, self.report, corpus):
            d.mkdir(parents=True, exist_ok=True)
        self.name = 'X__char_env_system_01.cpp'
        code = 'void bad()\n{\nSINK;\n}\nvoid good()\n{\nSAFE;\n}\n'
        for d in (self.src, corpus):
            (d / self.name).write_text(code)
        self.args = argparse.Namespace(juliet=str(root / 'juliet'), cwe='X', variant='char',
            out=str(self.out), limit=None, flows=None, json=str(root / 'score.json'))
        self.meta = {'schema': 1, 'cwe': 'X', 'variant': 'char', 'flows': None,
            'case_names': [self.name[:-4]], 'cases': 1, 'batches': [{
                'index': 0, 'cases': 1, 'case_names': [self.name[:-4]], 'exit': 0,
                'files': {self.name: hashlib.sha256((self.src / self.name).read_bytes()).hexdigest()}}]}
        self.summary = {'language': 'cpp', 'fileCount': 1, 'findingCount': 0,
            'projectPath': str(self.src), 'scanEndTime': '2026-11-08T00:00:00Z'}
        self.write()

    def write(self):
        (self.out / 'run.json').write_text(json.dumps(self.meta))
        (self.report / 'scan_summary.json').write_text(json.dumps(self.summary))
        (self.out / 'engine-000.log').write_text('scan complete\n')

    def rejected(self):
        with self.assertRaises((ValueError, OSError)):
            j.score(self.args)
        self.assertFalse(Path(self.args.json).exists())

    def test_successful_zero_findings_without_sarif(self):
        j.score(self.args)
        self.assertEqual(json.loads(Path(self.args.json).read_text())['totals'],
                         {'TP': 0, 'FN': 1, 'TN': 1, 'FP': 0})

    def test_archived_run_can_be_rescored(self):
        self.meta['batches'][0]['source_path'] = str(self.src)
        self.write()
        archived = self.out.parent / 'archived'
        self.out.rename(archived)
        self.args.out = str(archived)
        j.score(self.args)
        self.assertTrue(Path(self.args.json).exists())

    def test_failed_batch(self):
        self.meta['batches'][0]['exit'] = 137
        self.write()
        self.rejected()

    def test_missing_run(self):
        # Rename instead of removing: the same behavior as an absent manifest.
        (self.out / 'run.json').rename(self.out / 'saved-run.json')
        self.rejected()

    def test_missing_summary(self):
        (self.report / 'scan_summary.json').rename(self.report / 'saved-summary.json')
        self.rejected()

    def test_missing_findings_report(self):
        self.summary['findingCount'] = 1
        self.write()
        self.rejected()

    def test_incomplete_file_coverage(self):
        self.summary['fileCount'] = 0
        self.write()
        self.rejected()

    def test_changed_source(self):
        (self.src / self.name).write_text('changed')
        self.rejected()

    def test_selection_mismatch(self):
        self.meta['case_names'] = []
        self.write()
        self.rejected()

    def test_stale_batch(self):
        (self.out / 'report-001').mkdir()
        self.rejected()

    def test_unmapped_finding(self):
        self.summary['findingCount'] = 1
        self.write()
        sarif = {'runs': [{'results': [{'locations': [{'physicalLocation': {
            'artifactLocation': {'uri': self.name}, 'region': {'startLine': 100}}}]}]}]}
        (self.report / 'report.sarif').write_text(json.dumps(sarif))
        self.rejected()

    def test_report_count_mismatch(self):
        self.summary['findingCount'] = 1
        self.write()
        (self.report / 'report.sarif').write_text('{"runs": [{"results": []}]}')
        self.rejected()

    def test_parser_failure_in_log(self):
        (self.out / 'engine-000.log').write_text('#files unable to be parsed: 1')
        self.rejected()


if __name__ == '__main__':
    unittest.main()
