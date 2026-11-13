"""Published P/06 API: canonical composition, complete positive control, exact raw transport and KIT provenance."""
import lesson as output_lesson
import base64
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import test_gen_vectors_lessons as lessons
import wire
import wire_api_p06
import wire_fakes

GOENV = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')


def positive_control(g):
    """Existing lesson controls plus the four already known common APIs; families remains the real reader."""
    text, fns = lessons.fake_go(g)
    runs, _ = wire.expand(ROOT, '06-console')
    known = {(f'common/{name}', table, 'vectors')
             for name, table in g.common_vectors.composition('06-console', ROOT, known_only=True)}
    for name, fn in [('crl', 'CRL'), ('revoked', 'Revoked'), ('store-client', 'StoreClient'), ('log-mask', 'LogMask')]:
        values = {}
        for run in runs:
            if run.binding.package != 'common/' + name or run.binding.key not in known:
                continue
            if name == 'log-mask':
                cells = dict(run.cells, fields=run.files['fields.yaml'].decode())
                key = 'cases.tsv||' + '\x00'.join(sorted(f'{k}={v}' for k, v in cells.items()))
            else:
                key = run.cells['file' if name == 'revoked' else 'input']
            value = wire_fakes.native_value(run)
            if key in values:
                assert values[key] == value, (name, key)
            values[key] = value
        entries = ','.join(g.gstr(k) + ':val(' + g.gstr(json.dumps(v, ensure_ascii=False)) + ')' for k, v in values.items())
        text += '\nvar commonControl' + fn + ' = map[string]any{' + entries + '}\n'
        if name == 'log-mask':
            text += ('func LogMask(raw string,fields []byte)(string,error) { return commonControlLogMask['
                     'key("cases.tsv","",map[string]string{"raw":raw,"fields":string(fields)})].(string),nil }\n')
        elif name == 'store-client':
            text += 'func StoreClient(input []byte)(string,error) { return commonControlStoreClient[string(input)].(string),nil }\n'
        else:
            text += f'func {fn}(input []byte)(any,error) {{ return commonControl{fn}[string(input)],nil }}\n'
        fns.append(fn)
    return text, fns


@unittest.skipUnless(shutil.which('go'), 'go is not in PATH')
class CanonicalP06(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        import lesson
        cls.saved_lesson, cls.saved_env = lesson.CURRENT, os.environ.get('NORMGEN_LESSON')
        cls.addClassCleanup(cls.restore_lesson)
        cls.g = lessons.gv('06-console')
        cls.tmp = tempfile.TemporaryDirectory(prefix='p06-canonical-api-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.mod = Path(cls.tmp.name) / 'go'
        shutil.copytree(output_lesson.output_root() / 'p06/go', cls.mod)
        fake, fns = positive_control(cls.g)
        known = cls.g.common_vectors.DECLS
        for fn in fns:
            name = next((d['adapter'] for d in known.values() if d['go'] == fn), fn.lower() + '.go')
            path = cls.mod / 'vectoradapter' / name
            if path.is_file():
                path.unlink()
        cls.fake = cls.mod / 'vectoradapter/positive_control.go'
        cls.fake.write_text(fake)
        cls.runs, cls.excluded = wire.expand(ROOT, '06-console')

    @classmethod
    def restore_lesson(cls):
        import lesson
        lesson.CURRENT = cls.saved_lesson
        if cls.saved_env is None:
            os.environ.pop('NORMGEN_LESSON', None)
        else:
            os.environ['NORMGEN_LESSON'] = cls.saved_env
        if hasattr(cls, 'g'):
            importlib.reload(cls.g)

    def test_active_api_and_fresh_output(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        g = self.g
        self.assertTrue(all(len(row) == 5 and all(isinstance(x, str) for x in row) for row in wire_api_p06.API_P06))
        decls, known = g.plan(ROOT)
        active = {r.binding.key for r in self.runs}
        covered = {tuple(d[k] for k in ('package', 'table', 'surface')) for d in decls}
        covered |= {(f'common/{name}', table, 'vectors') for name, table in known}
        self.assertEqual(covered, active)
        self.assertEqual(len(active), 67)
        self.assertEqual(len(self.runs), 3224)
        self.assertTrue(all(d['_form'] and d['_runs'] for d in decls))
        self.assertFalse(any(d['surface'] == 'stand:group-of' for d in decls))
        files, inv = g.build(ROOT)
        self.assertEqual(sum(status == 'translated' for _, status in inv), 3224)
        for rel, data in files.items():
            self.assertEqual((output_lesson.output_root() / 'p06' / rel).read_bytes(), data, rel)
        self.assertIn('func GroupOf(input []byte) Answer', files['go/vectoradapter/groupof.go'].decode())
        self.assertIn('func FreshAgeStand(input []byte) Answer', files['go/vectoradapter/freshagestand.go'].decode())

    def test_p06_does_not_consult_draft_recipes(self):
        with patch.dict(self.g.WIRE, {}, clear=True):
            files, _ = self.g.build(ROOT)
            self.assertIn('go/wirecheck/check.go', files)
            self.assertIn('P/06 uses the published canonical wire form', self.g.lesson_kit_md())

    def test_all_3224_native_calls(self):
        done = subprocess.run(['go', 'test', '-count=1', '-json', './vectortests/'], cwd=self.mod,
                              env=GOENV, capture_output=True, text=True)
        results = {}
        for line in done.stdout.splitlines():
            if not line.startswith('{'):
                continue
            event = json.loads(line)
            if event.get('Test') and event.get('Action') in ('pass', 'fail'):
                self.assertNotIn(event['Test'], results, 'duplicate terminal native test')
                results[event['Test']] = event['Action']
        self.assertEqual(len(results), 3224, done.stderr + done.stdout[-2000:])
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout[-4000:])
        self.assertEqual(set(results.values()), {'pass'})

    def test_actual_groupof_api_preserves_raw_and_execution_errors(self):
        original = self.fake.read_text()
        replacement = ('func GroupOf(input []byte) Answer {\n'
                       ' if string(input)=="panic" { panic("P06 transport probe") };\n'
                       ' return Answer{Code:2,Value:string(input)}\n}')
        modified, count = re.subn(r'func GroupOf\(input \[\]byte\) Answer \{.*?\n\}', replacement,
                                  original, flags=re.S)
        self.assertEqual(count, 1)
        try:
            self.fake.write_text(modified)
            binary = self.mod / 'vectors'
            done = subprocess.run(['go', 'build', '-o', str(binary), './cmd/vectors'], cwd=self.mod,
                                  env=GOENV, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            path = self.mod / 'probe.json'
            for raw in (' [1.00e+02,9007199254740993,-0] ', '"\u0434\u0430\u043d\u043d\u044b\u0435"', 'panic'):
                frame = dict(format=1, package='common/group-of', table='cases.tsv', case='probe',
                             variant='', cells={'raw': raw}, files={})
                path.write_text(json.dumps(frame, ensure_ascii=False))
                done = subprocess.run([str(binary), str(path)], capture_output=True, text=True)
                if raw == 'panic':
                    self.assertNotEqual(done.returncode, 0)
                    continue
                self.assertEqual(done.returncode, 0, done.stderr)
                answer = json.loads(done.stdout)
                self.assertEqual(answer['exit_code'], 2)
                self.assertEqual(json.loads(base64.b64decode(answer['stdout_b64'])), raw)
            done = subprocess.run([str(binary), 'stand', 'group-of', str(path)], capture_output=True, text=True)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn('not a stand key', done.stderr)
        finally:
            self.fake.write_text(original)

    def test_contract_selection_keeps_stand_siblings_separate(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        import test_contracts
        mod = output_lesson.output_root() / 'p06/go'
        for package, cells_fn, stand_fn in [('common/fault', 'Fault', 'FaultStand'),
                                            ('common/fresh-age', 'FreshAge', 'FreshAgeStand'),
                                            ('common/door-token', 'DoorTokenIssue', 'DoorTokenIssueStand')]:
            cells = test_contracts.tests_calling(mod, cells_fn)
            stands = test_contracts.tests_calling(mod, stand_fn)
            self.assertTrue(cells)
            self.assertTrue(stands)
            self.assertFalse(set(cells) & set(stands))
            self.assertEqual(len(cells), sum(r.binding.package == package and r.binding.surface == 'vectors' for r in self.runs))
            self.assertEqual(len(stands), sum(r.binding.package == package and r.binding.surface.startswith('stand:') for r in self.runs))

    def test_provenance_uses_canonical_api_and_full_runtime(self):
        passport = self.g.provenance()
        self.assertIn('Platform/common/vectors/wire.tsv', {f['path'] for f in passport['form']})
        files = {f['path'] for f in passport['handwritten']}
        self.assertIn('tools/normgen/wire_api_p06.py', files)
        self.assertIn('tools/normgen/wirert/full/go/check.go', files)
        self.assertNotIn('tools/normgen/wire_draft.py', files)
        self.assertEqual(passport['judge']['path'], 'tools/normgen/test_wire_api_p06.py')


if __name__ == '__main__':
    unittest.main()
