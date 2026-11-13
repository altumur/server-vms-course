"""Complete packages, owner union and form refusals through the full generation chain on spec103 pin7b96ff9f."""
import lesson as output_lesson
import copy
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import vector_consumers as C
import consumer_vectors
import wire

PIN = '7b96ff9f84e8090e11922131bc77799f0a0b54e1'
GOENV = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')


def generator(key):
    import lesson
    lesson.CURRENT = lesson.get(key)
    os.environ['NORMGEN_LESSON'] = key
    import gen_vectors
    return importlib.reload(gen_vectors)


class Registry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='consumer-registry-')
        self.root = Path(self.tmp.name)
        (self.root/'Platform').mkdir()
        shutil.copy2(ROOT/'Platform/lessons.tsv', self.root/'Platform/lessons.tsv')
        for package, table in [('common/demo', 'cases.tsv'), ('01-store/jcs', 'canonical_json.tsv'),
                               ('06-console/rid', 'rid.tsv'), ('03-worker/unassigned', 'cases.tsv')]:
            owner, name = package.split('/')
            p = self.root/'Platform'/owner/'vectors'/name/table
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('case\nonly\n')
        self.rows = [('01-store/jcs', 'canonical_json.tsv', '02-installer', 'norm'),
                     ('common/demo', 'cases.tsv', '03-worker', 'norm')]
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        p = self.root/C.FORM
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\t'.join(C.COLUMNS)+'\n'+'\n'.join('\t'.join(r) for r in self.rows)+'\n')

    def test_union_and_no_common_implicit_owner(self):
        rows = C.read(self.root)
        self.assertEqual(rows['01-store/jcs', 'canonical_json.tsv'], {'01-store','02-installer'})
        self.assertEqual(rows['common/demo', 'cases.tsv'], {'03-worker'})
        self.assertEqual(rows['06-console/rid', 'rid.tsv'], {'06-console'})
        self.assertIn(('03-worker/unassigned', 'cases.tsv'), C.for_lesson(self.root, '03-worker'))
        self.rows = []
        self.write()
        self.assertNotIn(('common/demo', 'cases.tsv'), C.read(self.root))
        self.assertIn(('01-store/jcs', 'canonical_json.tsv'), C.read(self.root))

    def test_form_errors_even_on_another_consumer(self):
        original = list(self.rows)
        bad = [(*original[0][:3], 'different norm'), ('jcs','canonical_json.tsv','02-installer','norm'),
               ('11-foreign/jcs','canonical_json.tsv','02-installer','norm'),
               ('01-store/missing','canonical_json.tsv','02-installer','norm'),
               ('01-store/jcs','missing.tsv','02-installer','norm'),
               ('01-store/jcs','../canonical_json.tsv','02-installer','norm'),
               ('01-store/jcs','canonical_json.tsv','99-unknown','norm')]
        for row in bad:
            with self.subTest(row=row):
                self.rows = original + [row]
                self.write()
                with self.assertRaises(C.ConsumerError): C.for_lesson(self.root, '03-worker')
                with self.assertRaises(wire.WireError): wire.consumers(self.root)

    def test_header_and_cell_count(self):
        p = self.root/C.FORM
        for text in ('package\ttable\tlesson\n', '\t'.join(C.COLUMNS)+'\nonly\ttwo\n'):
            p.write_text(text)
            with self.assertRaises(C.ConsumerError): C.read(self.root)

    def test_json_selector_is_strict(self):
        cel = wire.Cel()
        self.assertTrue(cel('"rid" in json(row["expect"])', {'expect':'{"rid":"a"}'}, '03-worker', 'fixture'))
        for text in ('{"rid":1,"rid":2}', 'NaN', '{} garbage', '\ufeff{}'):
            with self.subTest(text=text), self.assertRaises(wire.WireError):
                cel('"rid" in json(row["expect"])', {'expect':text}, '03-worker', 'fixture')

    def test_ignore_pointer_grammar(self):
        wire.check_ignore(['/a~1b', '/list/0'], 'fixture')
        for paths in ([], [''], ['relative'], ['/bad~2'], ['/a','/a'], ['/a','/a/b']):
            with self.subTest(paths=paths), self.assertRaises(wire.WireError): wire.check_ignore(paths, 'fixture')


class LocalAPIGates(unittest.TestCase):
    """A local Go API is enabled by its gate, independently of lesson identity."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='consumer-local-gates-')
        self.root = Path(self.tmp.name)
        (self.root / 'Platform').mkdir()
        shutil.copy2(ROOT / 'Platform/lessons.tsv', self.root / 'Platform/lessons.tsv')
        path = self.root / C.FORM
        path.parent.mkdir(parents=True)
        path.write_text('\t'.join(C.COLUMNS) + '\n')
        self.owner, self.package = '03-worker', 'fetched'
        self.source_wire = next(line for line in (ROOT / wire.FORM).read_text().splitlines()
                                if line.startswith('03-worker/fetched\tcases.tsv\tvectors\t'))

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, owner='03-worker', name='fetched'):
        self.owner, self.package = owner, name
        directory = self.root / 'Platform' / owner / 'vectors' / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'cases.tsv').write_text('case\tinput\texpect\tnote\nlocal\tfixture\t["b","a"]\tindependent fixture\n')
        (directory / 'README.md').write_text('# Vector wire\n')
        fields = self.source_wire.split('\t')
        fields[0], fields[-1] = owner + '/' + name, owner + '/vectors/' + name + '/README.md#vector-wire'
        (self.root / wire.FORM).write_text('\t'.join(wire.COLUMNS) + '\n' + '\t'.join(fields) + '\n')
        self.stages = self.root / 'Platform' / owner / 'forms/stages.kit.tsv'
        self.stages.parent.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(L=SimpleNamespace(key=owner, rel='Platform/' + owner),
                               lesson_consumers=lambda root: C.for_lesson(root, owner))

    def test_real_unqualified_and_qualified_gates_select_the_wire(self):
        g = self.fixture()
        for cell in ('vectors:fetched', 'code:*;vectors:03-worker/fetched'):
            self.stages.write_text('stage\tgate\nnative\t' + cell + '\n')
            with self.subTest(cell=cell):
                decls = consumer_vectors.declarations(self.root, g)
                self.assertEqual([(d['package'], d['table'], d['fn']) for d in decls],
                                 [('03-worker/fetched', 'cases.tsv', 'Fetched')])
                self.assertEqual(len(decls[0]['_runs']), 1)
                self.assertEqual(decls[0]['compare'], 'set')

    def test_comments_other_cells_and_substrings_never_activate(self):
        g = self.fixture()
        # No wire binding exists here: accidental activation must fail this test,
        # rather than returning an unnoticed extra declaration.
        (self.root / wire.FORM).write_text('\t'.join(wire.COLUMNS) + '\n')
        for text in ('# vectors:fetched\nstage\tgate\nnative\tcode:*\n',
                     'stage\tgate\tnote\nvectors:fetched\tbuild\tvectors:fetched\n',
                     'stage\tgate\nnative\tvectors:fetched-extra\n'):
            self.stages.write_text(text)
            with self.subTest(text=text):
                self.assertEqual(consumer_vectors.declarations(self.root, g), [])
        self.stages.unlink()        # Historical sources may predate the gate/form.
        self.assertEqual(consumer_vectors.declarations(self.root, g), [])

    def test_selected_api_requires_real_binding_and_owned_table(self):
        g = self.fixture()
        self.stages.write_text('stage\tgate\nnative\tvectors:fetched\n')
        (self.root / wire.FORM).write_text('\t'.join(wire.COLUMNS) + '\n')
        with self.assertRaisesRegex(wire.WireError, 'no vector binding'):
            consumer_vectors.declarations(self.root, g)
        (self.root / 'Platform/03-worker/vectors/fetched/cases.tsv').unlink()
        with self.assertRaisesRegex(wire.WireError, 'no assigned tables'):
            consumer_vectors.declarations(self.root, g)

    def test_gate_parser_rejects_malformed_cells(self):
        g = self.fixture()
        for cell in ('vectors:fetched;', 'code:*; vectors:fetched', 'vectors:fetched;vectors:fetched'):
            self.stages.write_text('stage\tgate\nnative\t' + cell + '\n')
            with self.subTest(cell=cell), self.assertRaises(wire.WireError):
                consumer_vectors.declarations(self.root, g)

    def test_local_api_selection_is_generic_for_another_lesson(self):
        g = self.fixture('04-controller', 'local-probe')
        with patch.dict(consumer_vectors.API, {'04-controller/local-probe': ('LocalProbe', 'cells')}):
            for cell in ('vectors:local-probe', 'vectors:04-controller/local-probe'):
                self.stages.write_text('stage\tgate\nnative\t' + cell + '\n')
                with self.subTest(cell=cell):
                    decls = consumer_vectors.declarations(self.root, g)
                    self.assertEqual([(d['package'], d['fn']) for d in decls], [('04-controller/local-probe', 'LocalProbe')])


class NewPin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        found = subprocess.run(['git','cat-file','-e',PIN+':Platform/common/vectors/consumers.tsv'], cwd=ROOT,
                               capture_output=True)
        if found.returncode:
            raise unittest.SkipTest('spec103 consumer pin '+PIN+' is not available')
        cls.tmp = tempfile.TemporaryDirectory(prefix='consumer-pin-')
        cls.root = Path(cls.tmp.name)/'specs'
        cls.root.mkdir()
        data = subprocess.check_output(['git','archive',PIN,'Platform','Source/tests/testdata'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(data)) as t: t.extractall(cls.root, filter='data')
        # Explicit historical fixture adaptation, not a current producer fallback.
        # The archived donor remains unchanged; these two exact bytes are copied
        # to the canonical paths expected by the current reader.
        import hashlib
        donors = {"testsub": "7e6118cea2d639e11e894208d5f5be1d82cd1ec385cac0231fe7449305e5430a",
                  "testsub2": "813a807f3472bdc64e279c94c12bfe3b00ebaaa8ebda0c996d2a50161043e6eb"}
        for name, digest in donors.items():
            donor = cls.root / "Source/tests/testdata" / f"{name}.subsystem.yaml"
            original = donor.read_bytes()
            assert hashlib.sha256(original).hexdigest() == digest, (PIN, donor)
            target = cls.root / "Platform/common/data/testsub" / donor.name
            assert not target.exists(), target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
            assert target.read_bytes() == donor.read_bytes() == original
        fixture=json.loads((HERE/'testdata/consumer-owners-8af61893a.json').read_text())
        assert fixture['source_commit']=='8af61893a7458054d8c79701f78b3b284e8573a8'
        cls.base={(r['package'],r['table']):set(r['lessons']) for r in fixture['tables']}
        cls.new = C.read(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        import lesson
        self.previous_lesson = lesson.CURRENT
        self.previous_env = os.environ.get("NORMGEN_LESSON")

    def tearDown(self):
        import lesson
        lesson.CURRENT = self.previous_lesson
        if self.previous_env is None:
            os.environ.pop("NORMGEN_LESSON", None)
        else:
            os.environ["NORMGEN_LESSON"] = self.previous_env
        import gen_vectors
        importlib.reload(gen_vectors)

    def test_exact_assignments_owner_and_legacy_common_projection(self):
        delta = {(p,t,o) for (p,t),owners in self.new.items() for o in owners}
        delta -= {(p,t,o) for (p,t),owners in self.base.items() for o in owners}
        expected = {('01-store/jcs','canonical_json.tsv',o) for o in
                    ('02-installer','03-worker','06-console','08-domain','09-agent')}
        expected |= {('06-console/'+p,t,'03-worker') for p,t in
                     [('rid','rid.tsv'),('rid','template.tsv'),('request-digest','digest.tsv'),
                      ('requests-body','requests_body.tsv')]}
        self.assertEqual(delta, expected)
        import common_vectors
        for owner in ('01-store','02-installer','03-worker','06-console','08-domain','09-agent'):
            self.assertEqual(common_vectors.composition(owner, self.root, known_only=True),
                             common_vectors.composition(owner, ROOT, known_only=True))

    def test_p01_refuses_an_unimplemented_foreign_assignment(self):
        from unittest.mock import patch
        import gen_tests
        with patch.object(C, "for_lesson", return_value={("06-console/request-digest", "digest.tsv")}):
            with self.assertRaisesRegex(gen_tests.GenError, "no gen_tests adapter"):
                gen_tests.render(ROOT)

    def test_p02_jcs_reaches_command_and_tests(self):
        g = generator('02-installer')
        files, inv = g.build(self.root)
        self.assertIn('go/vectoradapter/jcs.go', files)
        self.assertIn(b'case "01-store/jcs canonical_json.tsv"', files['go/vectorcmd/vectorcmd.go'])
        frames = [json.loads(data) for path,data in files.items()
                  if path.startswith('vectors/01-store/jcs/') and path.endswith('.json')]
        self.assertEqual(len(frames), 17)
        self.assertTrue(all(set(f['cells']) == {'raw'} and f['files'] == {} for f in frames))
        self.assertTrue(any(p.startswith('01-store/jcs ') and status=='translated' for p,status in inv))

    def test_draft_stage_packages_require_the_declared_owner(self):
        g = generator('03-worker')
        path = self.root / 'Platform/03-worker/forms/stages.kit.tsv'
        original = path.read_bytes() if path.exists() else None
        try:
            for token in ('creates-key', 'common/slot', '01-store/jcs', '06-console/rid'):
                path.write_text('stage\tgate\nexample\tvectors:' + token + ';code:*\n')
                g.plan(self.root)
            for token in ('03-worker/jcs', '06-console/jcs', 'common/creates-key'):
                with self.subTest(token=token):
                    path.write_text('stage\tgate\nexample\tvectors:' + token + '\n')
                    with self.assertRaisesRegex(g.GenError, 'no declaration of its wire'):
                        g.plan(self.root)
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def test_wire_stage_packages_require_the_declared_owner(self):
        import wire_vectors
        path = self.root / 'Platform/02-installer/forms/stages.kit.tsv'
        original = path.read_bytes() if path.exists() else None
        try:
            for token in ('canonical', 'common/loopback', '01-store/jcs'):
                path.write_text('stage\tgate\nexample\tvectors:' + token + ';code:*\n')
                wire_vectors.declarations(self.root)
            for token in ('02-installer/jcs', '06-console/jcs', 'common/canonical'):
                with self.subTest(token=token):
                    path.write_text('stage\tgate\nexample\tvectors:' + token + '\n')
                    with self.assertRaisesRegex(wire.WireError, 'undeclared stages.kit.tsv package'):
                        wire_vectors.declarations(self.root)
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def historical_families(self, slug):
        # This named old source has its own creation/receipt. Never copy current
        # output into a historical test and label it as a matching source.
        if not hasattr(self.__class__, '_family_sets'):
            self.__class__._family_sets = {}
        sets = self.__class__._family_sets
        if slug not in sets:
            output = Path(tempfile.mkdtemp(prefix='historical-families-' + slug + '-', dir=self.tmp.name))
            # Imports and lesson selection stay in the creator process. Vectors
            # supply the historical module closure; families alone have no go.mod.
            creator = """import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[3])/'tools/normgen'))
sys.path.insert(0,str(Path(sys.argv[3])/'tools/normgen/kit'))
import lesson,build_kit
build_kit.prepare(('families','vectors'),profiles=(sys.argv[1],),
                  source_root=Path(sys.argv[2]),code_root=Path(sys.argv[3]),
                  output_root=Path(sys.argv[4]),context={'kind':'historical','source_pin':sys.argv[5]})
print(os.environ[lesson.OUTPUT_RECEIPT_ENV])
"""
            done = subprocess.run([sys.executable, '-B', '-c', creator, slug, str(self.root), str(ROOT),
                                   str(output), PIN], capture_output=True, text=True,
                                  env=dict(GOENV, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(done.returncode, 0, 'historical creator failed: ' + done.stderr)
            held = done.stdout.removesuffix('\n')
            self.assertEqual(len(held), 64, 'creator must return one held receipt')
            self.assertTrue(all(c in '0123456789abcdef' for c in held), 'malformed creator receipt')
            sets[slug] = (output, held)
        output, held = sets[slug]
        ready = output_lesson.ready_outputs(output_root=output, source_root=self.root, code_root=ROOT,
                                            profiles=(slug,), expected_manifest_sha256=held)
        return ready[slug] / 'go/families'

    def fake_foreign(self, g, files, mutated=None):
        mod = Path(self.tmp.name)/('mod-'+g.L.key+('-'+mutated if mutated else ''))
        mod.mkdir(exist_ok=True)
        for rel,data in files.items():
            if rel.startswith('go/'):
                p=mod/rel[3:];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        shutil.copytree(self.historical_families(g.L.slug), mod/'families', dirs_exist_ok=True)
        (mod/'go.mod').write_text(f'module {g.GO_MODULE}\n\ngo 1.22\n')
        import consumer_vectors
        ds = consumer_vectors.declarations(self.root, g) if g.L.key!='02-installer' else []
        if g.L.key=='02-installer':
            bs=wire.lesson_bindings(self.root,g.L.key)
            b=next(b for b in bs if b.package=='01-store/jcs')
            runs,_=wire.Expander(self.root).run(b,g.L.key)
            ds=[dict(fn='JCS',package=b.package,_runs=runs)]
        rows={}
        for d in ds:
            for r in d['_runs']:
                value=copy.deepcopy(r.value)
                if r.ignore==['/detail']:
                    value={'detail':'an actual native reason'}
                if mutated==d['package'].split('/')[1]:
                    value={}   # missing required native fields or the value being compared
                key=r.binding.table+'|'+'\x00'.join(sorted(k+'='+v for k,v in r.cells.items()))
                rows.setdefault(d['fn'],{})[key]=value
        head='''package vectoradapter
import("encoding/json";"sort";"strings")
func consumerKey(table string, cells map[string]string) string {
    parts:=[]string{};for k,v:=range cells {parts=append(parts,k+"="+v)};sort.Strings(parts)
    return table+"|"+strings.Join(parts,"\\x00")
}
'''
        source=[head]
        for fn, values in rows.items():
            source.append(f'var consumer{fn} = map[string]string{{'+','.join(g.gstr(k)+':'+g.gstr(json.dumps(v,ensure_ascii=False)) for k,v in values.items())+'}\n')
            source.append(f'func {fn}(table string,cells map[string]string,files map[string][]byte) Answer {{ s,ok:=consumer{fn}[consumerKey(table,cells)];if !ok {{return NotImplemented("missing fake input")}};var v any;_ = json.Unmarshal([]byte(s),&v);return Answer{{Value:v}} }}\n')
            (mod/'vectoradapter'/(fn.lower()+'.go')).unlink()
        (mod/'vectoradapter/consumer_fake.go').write_text('\n'.join(source))
        return mod, sum(len(d['_runs']) for d in ds)

    def test_new_consumers_execute_and_mutants_fail(self):
        for owner in ('02-installer','03-worker','06-console','08-domain','09-agent'):
            with self.subTest(owner=owner):
                g=generator(owner)
                files,_=g.build(self.root)
                for mutant in ((None,'jcs','rid','request-digest','requests-body') if owner=='03-worker' else (None,'jcs')):
                    mod,count=self.fake_foreign(g,files,mutant)
                    pattern='^(TestJcs_|TestRid_|TestRequestDigest_|TestRequestsBody_)' if owner=='03-worker' else '^TestJcs_'
                    done=subprocess.run(['go','test','-count=1','-json','./vectortests','-run',pattern], cwd=mod,
                                        capture_output=True,text=True,env=GOENV)
                    events=[json.loads(s) for s in done.stdout.splitlines() if s.startswith('{')]
                    results={e['Test']:e['Action'] for e in events if e.get('Test') and e['Action'] in ('pass','fail')}
                    self.assertEqual(len(results),count,done.stderr+done.stdout[-1800:])
                    self.assertEqual(done.returncode==0,mutant is None,done.stderr+done.stdout[-1800:])
                    if mutant:
                        self.assertTrue(any(a=='fail' for a in results.values()))

    def test_native_schema_runs_before_ignored_detail(self):
        g=generator('03-worker');files,_=g.build(self.root)
        mod,count=self.fake_foreign(g,files,'rid')
        import consumer_vectors
        d=next(d for d in consumer_vectors.declarations(self.root,g) if d['table']=='template.tsv')
        row=next(r for r in d['_runs'] if r.ignore==['/detail'])
        name=f"TestRid_Template_Line{row.lines[0]}"
        done=subprocess.run(['go','test','-count=1','./vectortests','-run','^'+name+'$'],cwd=mod,
                            capture_output=True,text=True,env=GOENV)
        self.assertNotEqual(done.returncode,0)
        self.assertIn('--- FAIL: '+name,done.stdout)
        self.assertIn('native schema:',done.stdout)
        self.assertIn('detail',done.stdout)


if __name__=='__main__': unittest.main()
