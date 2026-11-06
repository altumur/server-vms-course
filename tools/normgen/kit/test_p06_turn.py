"""Current-source internal C4 verification: Turn, editable adapter and complete default failure.

The old private87 export is historical context only; its execution is not inherited.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GEN = HERE.parent
HISTORICAL_EXPORT = '87ea188e1ace7e0ba91e7b5f66587cf25e709854'
sys.path.insert(0, str(GEN))
import lesson
import tsv_input
EVIDENCE = Path(os.environ['C4_EVIDENCE_DIR']) if os.environ.get('C4_EVIDENCE_DIR') else Path(tempfile.mkdtemp(prefix='c4-kit-evidence-'))
MODULE = 'p06console/06-console'
GOENV = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')


class P06TurnKit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lesson.ready_outputs(profiles=lesson.PROFILES)
        table = tsv_input.read(ROOT / 'Platform/common/vectors/turn/cases.tsv',
                               names=('case', 'input', 'expect', 'note'), root=ROOT)
        cls.expected_names = {'TestTurn_Cases_Line' + str(line) for line, row in table.rows
                              if json.loads(row['input'])['kind'] == 'operations'}
        if len(cls.expected_names) != 16:
            raise AssertionError('current operation turn corpus is not the approved16')
        cls.tmp = tempfile.TemporaryDirectory(prefix='p06-turn-kit-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.kit = Path(cls.tmp.name) / 'real'
        cls.build(cls.kit)
        cls.mod = cls.kit / '06-console'
        cls.manifest = json.loads((cls.kit / 'kit.manifest.json').read_bytes())
        # Standard verification module, outside the builder's payload inventory.
        (cls.mod / 'go.mod').write_text('module ' + MODULE + '\n\ngo 1.22\n')

    @classmethod
    def build(cls, target, contracts=True):
        command = [sys.executable, str(HERE / 'build_kit.py'), str(target), '--lesson', '06-console',
                   '--module', MODULE, '--part', 'families', '--part', 'vectors']
        if contracts:
            command += ['--part', 'contracts']
        done = subprocess.run(command, cwd=ROOT, env=GOENV, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError('current-source internal KIT build failure: ' + done.stdout + done.stderr)

    def evidence(self, name, value):
        folder = EVIDENCE
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(value, indent=2) + '\n')

    def test_01_manifest_source_provenance_and_compilation(self):
        man = self.manifest
        self.assertIsNone(man.get('export'))
        self.assertEqual(man['commit'], subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip())
        self.assertNotIn('seed', man)
        self.assertNotIn('SOURCE.txt', {p.name for p in self.kit.iterdir()})
        paths = {f['path']: f for f in man['files']}
        for path, entry in paths.items():
            self.assertEqual(hashlib.sha256((self.kit / path).read_bytes()).hexdigest(), entry['sha256'], path)
        adapter = paths['06-console/internal/vectoradapter/turn.go']
        self.assertTrue(adapter.get('editable'))
        self.assertEqual(adapter['origin'], 'handwritten')
        self.assertEqual(adapter['source'], 'tools/normgen/contracts/adapters/turn.go')
        self.assertFalse(paths['06-console/internal/contracts/turn.go'].get('editable'))
        self.assertFalse(paths['06-console/internal/wirecheck/check.go'].get('editable'))
        form = {f['path']: f['sha256'] for f in man['provenance']['vectors']['form']}
        for path in ('Platform/common/vectors/turn/cases.tsv', 'Platform/common/vectors/turn/README.md',
                     'Platform/common/contracts/turn.md', 'Platform/common/vectors/wire.tsv',
                     'Platform/common/vectors/consumers.tsv'):
            content = (ROOT / path).read_bytes()
            self.assertEqual(form[path], hashlib.sha256(content).hexdigest(), path)
        contracts = {f['path']: f['sha256'] for f in man['provenance']['contracts']['handwritten']}
        for path in ('contracts/go/turn.go', 'contracts/adapters/turn.go'):
            self.assertEqual(contracts['tools/normgen/' + path], hashlib.sha256((GEN / path).read_bytes()).hexdigest())
        checks = []
        for command in (['go', 'vet', './...'], ['go', 'build', './...'], ['go', 'test', '-run', '^$', './...']):
            done = subprocess.run(command, cwd=self.mod, env=GOENV, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            checks.append(command)
        self.evidence('kit-provenance-compile.json', {'source_context': 'current internal verification', 'historical_export_not_inherited': HISTORICAL_EXPORT, 'code': man['commit'],
                      'payload_sha': len(paths), 'checks': checks, 'turn_adapter': adapter,
                      'turn_form_pins': {k: v for k, v in form.items() if 'turn' in k}})

    def actual_tests(self, mod):
        done = subprocess.run(['go', 'test', '-count=1', '-json', '-run', '^TestTurn_Cases_', './internal/vectortests/'],
                              cwd=mod, env=GOENV, capture_output=True, text=True)
        self.assertNotIn('panic:', done.stdout + done.stderr)
        results = {}
        for line in done.stdout.splitlines():
            event = json.loads(line)
            if event.get('Test') and event.get('Action') in ('pass', 'fail', 'skip'):
                self.assertNotIn(event['Test'], results, 'duplicate terminal test')
                results[event['Test']] = event['Action']
        self.assertEqual(set(results), self.expected_names, done.stdout + done.stderr)
        self.assertIn(done.returncode, (0, 1), 'not a normal semantic Go test result')
        self.assertEqual(done.returncode == 0, all(v == 'pass' for v in results.values()))
        self.assertNotIn('skip', results.values())
        return done, results

    def test_02_real_closed_adapter_executes_all16_published_operations(self):
        done, results = self.actual_tests(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(set(results.values()), {'pass'})
        self.evidence('kit-real-turn16.json', results)

    def test_03_default_executes_fail_and_rebuild_preserves_yours(self):
        scaffold = Path(self.tmp.name) / 'scaffold'
        self.build(scaffold, contracts=False)
        mod = scaffold / '06-console'
        (mod / 'go.mod').write_text('module ' + MODULE + '\n\ngo 1.22\n')
        done, results = self.actual_tests(mod)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(set(results.values()), {'fail'})
        self.assertIn('adapter did not execute', done.stdout)
        adapter = self.mod / 'internal/vectoradapter/turn.go'
        own = adapter.read_bytes() + b'\n// C4 verification: preserve the owned adapter.\n'
        adapter.write_bytes(own)
        closed = [self.mod / 'internal/wirecheck/check.go', self.mod / 'internal/vectortests/turn_cases_test.go',
                  self.mod / 'internal/vectoradapter/vectoradapter.go']
        expected = {p: p.read_bytes() for p in closed}
        for path in closed:
            path.write_text('stale closed verification fixture\n')
        self.build(self.kit)
        self.assertEqual(adapter.read_bytes(), own)
        for path in closed:
            self.assertEqual(path.read_bytes(), expected[path], str(path))
        self.evidence('kit-default-and-rebuild.json', {'default': results, 'editable_preserved': True,
                      'closed_refreshed': [str(p.relative_to(self.mod)) for p in closed]})


if __name__ == '__main__':
    unittest.main()
