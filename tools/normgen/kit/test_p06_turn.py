"""Private C4 KIT: real Turn, editable adapter and executed default failure."""
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
SPECS = Path('/home/pilot/coord103/candidate-p06-semantic-export')
EXPORT = '87ea188e1ace7e0ba91e7b5f66587cf25e709854'
MODULE = 'p06console/06-console'
GOENV = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')


@unittest.skipUnless((SPECS / '.git').exists(), 'private P06 C4 export is unavailable')
class P06TurnKit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        command += ['--export', EXPORT, '--specs', str(SPECS)]
        done = subprocess.run(command, cwd=ROOT, env=GOENV, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError('private KIT build failure: ' + done.stdout + done.stderr)

    def evidence(self, name, value):
        folder = Path(os.environ.get('C4_EVIDENCE_DIR', GEN / '__pycache__/c4-turn-evidence'))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(value, indent=2) + '\n')

    def test_01_manifest_source_provenance_and_compilation(self):
        man = self.manifest
        self.assertEqual(man['export'], EXPORT)
        self.assertEqual(man['commit'], subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip())
        self.assertNotIn('seed', man)
        self.assertNotIn('dirty', (self.kit / 'SOURCE.txt').read_text())
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
            content = subprocess.check_output(['git', 'show', EXPORT + ':' + path], cwd=SPECS)
            self.assertEqual(form[path], hashlib.sha256(content).hexdigest(), path)
        contracts = {f['path']: f['sha256'] for f in man['provenance']['contracts']['handwritten']}
        for path in ('contracts/go/turn.go', 'contracts/adapters/turn.go'):
            self.assertEqual(contracts['tools/normgen/' + path], hashlib.sha256((GEN / path).read_bytes()).hexdigest())
        checks = []
        for command in (['go', 'vet', './...'], ['go', 'build', './...'], ['go', 'test', '-run', '^$', './...']):
            done = subprocess.run(command, cwd=self.mod, env=GOENV, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            checks.append(command)
        self.evidence('kit-provenance-compile.json', {'export': EXPORT, 'code': man['commit'],
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
                results[event['Test']] = event['Action']
        self.assertEqual(len(results), 16, done.stdout + done.stderr)
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
