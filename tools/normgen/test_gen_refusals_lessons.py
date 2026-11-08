"""Test P/03/P/04 refusal projections: freshness, judge PASS, and FAIL for imported peer body/header, word-token/cell and single-chapter metadata mutants. Reject fields/headers outside peer grammar."""
import lesson as output_lesson
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05", "06-console": "p06", "09-agent": "p09"}
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def judge(lesson, mod):
    return subprocess.run([sys.executable, str(HERE / "refusal_judge.py"), "--lesson", lesson, "--module-dir", str(mod)],
                          capture_output=True, text=True, env=ENV)


class Refusals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="refusals-lessons-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gen(self, lesson, out, table=None):
        table = table or ROOT / "Platform" / lesson / "forms/refusals.tsv"
        return subprocess.run([sys.executable, str(HERE / "gen_refusals.py"), "--lesson", lesson, str(table), str(out)],
                              capture_output=True, text=True)

    def test_fresh_and_judged(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for lesson, slug in LESSONS.items():
            out = self.tmp / f"fresh-{slug}"
            done = self.gen(lesson, out)
            self.assertEqual(done.returncode, 0, done.stderr)
            kept = output_lesson.output_root() / slug / "go/refusals/refusals.go"
            self.assertEqual(kept.read_bytes(), (out / "go/refusals/refusals.go").read_bytes(), f"{kept} is stale")
            done = judge(lesson, output_lesson.output_root() / slug / "go")
            self.assertEqual(done.returncode, 0, done.stdout[-1500:])

    def test_mutants(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        src = (output_lesson.output_root() / 'p03/go/refusals/refusals.go').read_text(encoding="utf-8")
        p04 = (output_lesson.output_root() / 'p04/go/refusals/refusals.go').read_text(encoding="utf-8")
        p05 = (output_lesson.output_root() / 'p05/go/refusals/refusals.go').read_text(encoding="utf-8")
        p06 = (output_lesson.output_root() / 'p06/go/refusals/refusals.go').read_text(encoding="utf-8")
        muts = {
            ("03-worker", "fields"): src.replace('Fields: []string{"error"}', "Fields: nil", 1),
            ("03-worker", "headers"): src.replace('{"Retry-After", "1"}', '{"Retry-After", "2"}', 1),
            ("03-worker", "named"): src.replace('Named: []string{"wrong_kind", "wrong_audience"}',
                                                'Named: []string{"wrong_kind"}', 1),
            ("03-worker", "word-cell"): src.replace('WordCell: "— (log)"', 'WordCell: "-"', 1),
            ("03-worker", "word"): src.replace('Word: "NameOnAnotherBox"', 'Word: ""', 1),
            ("04-controller", "chapter"): p04.replace('Chapter: "4", Row: 3,', 'Chapter: "4.1", Row: 3,', 1),
            ("05-resource", "response"): p05.replace('Response: "ResourceDenied"', 'Response: "ResourceError"', 1),
            ("05-resource", "http-status"): p05.replace('Status: 206,', 'Status: 200,', 1),
            ("06-console", "word-phrase"): p06.replace('Word: "no such book shown"', 'Word: ""', 1),
            ("06-console", "response-peer"): p06.replace('Response: "DomainRefusal"', 'Response: "Fault"', 1),
        }
        for (lesson, name), text in muts.items():
            with self.subTest(mutant=name):
                base = {"03-worker": src, "04-controller": p04, "05-resource": p05, "06-console": p06}[lesson]
                self.assertNotEqual(text, base, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(output_lesson.output_root() / LESSONS[lesson] / "go", mod)
                (mod / "refusals/refusals.go").write_text(text, encoding="utf-8")
                done = judge(lesson, mod)
                self.assertEqual(done.returncode, 1, f"{name} survives: {done.stdout[-500:]}")

    def test_refusals(self):
        text = (ROOT / "Platform/03-worker/forms/refusals.tsv").read_text(encoding="utf-8")
        bad = {"fields-at-call": text.replace("\tslot_foreign_box\tcall\t-\t-\t-\t", "\tslot_foreign_box\tcall\t-\t-\terror\t", 1),
               "headers-at-call": text.replace("\tslot_guard\tcall\t-\t-\t-\t-\t", "\tslot_guard\tcall\t-\t-\t-\tRetry-After: 1\t", 1),
               "kind": text.replace("\tslot_guard\tcall\t-\t-\t", "\tslot_guard\tcall\t-\tbad\t", 1)}
        for name, t in bad.items():
            with self.subTest(form=name):
                self.assertNotEqual(t, text, f"{name}: the change does not apply")
                p = self.tmp / f"{name}.tsv"
                p.write_text(t, encoding="utf-8")
                done = self.gen("03-worker", self.tmp / f"out-{name}", p)
                self.assertNotEqual(done.returncode, 0, f"{name}: accepted")

    def test_p09_stored_outcome_has_no_http_body(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        source = ROOT / "Platform/09-agent/forms/refusals.tsv"
        rows = list(csv.DictReader([s for s in source.read_text(encoding="utf-8").split("\n")
                                    if s and not s.startswith("#")], delimiter="\t"))
        row = next(r for r in rows if r["name"] == "agent_edit_conflict")
        self.assertEqual((row["surface"], row["code"], row["response_schema"]), ("call", "412", "-"))
        src = (output_lesson.output_root() / 'p09/go/refusals/refusals.go').read_text(encoding="utf-8")
        declaration = next(line for line in src.split("\n") if line.startswith("var AgentEditConflict = "))
        self.assertIn('Surface: "call", Exit: -1, AnyNonZero: false, Status: 412,', declaration)
        self.assertIn('Response: ""', declaration)
        schema = next(r["response_schema"] for r in rows if r["response_schema"] != "-")
        for field, value in [("fields", "error"), ("headers", "Retry-After: 1"),
                             ("response_schema", schema), ("surface", "cli"), ("surface", "start")]:
            with self.subTest(field=field):
                changed = [dict(r) for r in rows]
                next(r for r in changed if r["name"] == row["name"])[field] = value
                path = self.tmp / f"p09-call-{field}.tsv"
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                    writer.writeheader()
                    writer.writerows(changed)
                done = self.gen("09-agent", self.tmp / ("bad-p09-" + field), path)
                self.assertNotEqual(done.returncode, 0, done.stderr)

    def test_p09_call_code_boundaries(self):
        source = ROOT / "Platform/09-agent/forms/refusals.tsv"
        rows = list(csv.DictReader([s for s in source.read_text(encoding="utf-8").split("\n")
                                    if s and not s.startswith("#")], delimiter="\t"))
        row = next(r for r in rows if r["name"] == "agent_edit_conflict")
        valid = [100, 199, 200, 299, 300, 399, 400, 499, 500, 599]
        path, out = self.tmp / "p09-code-bounds.tsv", self.tmp / "p09-code-bounds"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(dict(row, name="edge_" + str(n), code=str(n)) for n in valid)
        done = self.gen("09-agent", out, path)
        self.assertEqual(done.returncode, 0, done.stderr)
        generated = (out / "go/refusals/refusals.go").read_text(encoding="utf-8")
        for n in valid:
            declaration = next(line for line in generated.split("\n") if line.startswith(f"var Edge{n} = "))
            self.assertIn(f"Status: {n},", declaration)
        for code in ["0", "99", "600", "999", "0100", "+100", "100.0"]:
            with self.subTest(code=code):
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                    writer.writeheader()
                    writer.writerow(dict(row, code=code))
                done = self.gen("09-agent", out, path)
                self.assertNotEqual(done.returncode, 0, done.stderr)



class OptionalP06Fields(unittest.TestCase):
    """Independent actual source/OpenAPI roles; rendering only creates the subject."""
    def setUp(self):
        import yaml
        from types import SimpleNamespace
        from unittest.mock import patch
        # Import only the pinned producer as subject; expected values still come from raw Source.
        import importlib.util
        producer = Path(os.environ['NORMGEN_PRODUCER_ROOT']) / 'tools/normgen/gen_refusals.py'
        spec = importlib.util.spec_from_file_location('pinned_refusal_subject', producer)
        subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(subject)
        self.yaml, self.gen = yaml, subject
        build_env = patch.dict(ENV, GOFLAGS=ENV.get('GOFLAGS', '') + ' -buildvcs=false')
        build_env.start()
        self.addCleanup(build_env.stop)
        self.tmp = tempfile.TemporaryDirectory(prefix='p06-refusal-fields-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.form = self.home / 'refusals.tsv'
        # Canonical owner/base plus Source dependency closure. Never fall back in the producer.
        shutil.copytree(ROOT / 'Platform', self.home / 'Platform')
        self.api = self.home / 'Platform/06-console/spec/06-console.api.openapi.yaml'
        source = ROOT / 'Platform/06-console/forms/refusals.tsv'
        self.rows = list(csv.DictReader((line for line in source.read_text().split('\n')
                                        if line and not line.startswith('#')), delimiter='\t'))
        self.names = list(self.rows[0])
        self.name = 'c67_027_503_1'
        selected = [row for row in self.rows if row['name'] == self.name]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['fields'], 'detail,error,supervision?')
        self.api_text = (ROOT / 'Platform/06-console/spec/06-console.api.openapi.yaml').read_text()
        self.doc = yaml.safe_load(self.api_text)
        self.assertEqual(set(self.doc['components']['schemas']['VerifyUnavailable']['required']), {'detail', 'error'})
        self.write()
        change = patch.object(self.gen, 'L', SimpleNamespace(key='06-console', code='P/06',
                               openapi=self.api, go_module='refusalprobe'))
        change.start()
        self.addCleanup(change.stop)

    def write(self):
        with self.form.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=self.names, delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(self.rows)
        # Preserve the published YAML subset; do not reserialize unrelated schemas.
        start = self.api_text.index('    VerifyUnavailable:\n')
        end = self.api_text.index('    ManifestSource:\n', start)
        section = self.api_text[start:end]
        required = self.doc['components']['schemas']['VerifyUnavailable']['required']
        before = '      required:\n      - detail\n      - error\n'
        self.assertEqual(section.count(before), 1)
        after = '      required: ' + self.yaml.safe_dump(required, default_flow_style=True).strip() + '\n'
        self.api.write_text(self.api_text[:start] + section.replace(before, after) + self.api_text[end:])

    def selected(self):
        return next(row for row in self.rows if row['name'] == self.name)

    def wanted(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('owned_optional_role_oracle', HERE / 'refusal_judge.py')
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        row = self.selected()
        schema = oracle.SourceSchemas(self.api).schema(row['response_schema'])
        if row['fields'] == '-':
            return [], []  # No direct projection; full schema/reference closure was still checked above.
        fields = row['fields'].split(',')
        names, optional = [v.rstrip('?') for v in fields], [v[:-1] for v in fields if v.endswith('?')]
        self.assertLessEqual(set(names), set(schema['properties']))
        self.assertLessEqual(set(schema['required']), set(names) - set(optional))
        self.assertFalse(set(optional) & set(schema['required']))
        return names, optional

    def compile_readback(self, source):
        home = self.home / 'compiled'
        (home / 'refusals').mkdir(parents=True, exist_ok=True)
        (home / 'go.mod').write_text('module refusalprobe\n\ngo 1.22\n')
        (home / 'refusals/refusals.go').write_text(source)
        (home / 'main.go').write_text('''package main
import("encoding/json";"os";"refusalprobe/refusals")
func main(){json.NewEncoder(os.Stdout).Encode(map[string]any{"rows":refusals.All,"selected":refusals.ByName("c67_027_503_1")})}
''')
        done = subprocess.run(['go', 'build', '-o', str(home / 'probe'), '.'], cwd=home,
                              env=ENV, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, 'checking compile error, not a kill: ' + done.stderr)
        done = subprocess.run([str(home / 'probe')], cwd=home, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, 'checking execution error, not a kill: ' + done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual([row['Name'] for row in result['rows']], [row['name'] for row in self.rows])
        self.assertEqual(len({row['Name'] for row in result['rows']}), len(self.rows))
        self.assertEqual(result['selected']['Name'], self.name)
        self.assertEqual(result['selected']['Response'], 'VerifyUnavailable')
        return result['selected']

    def test_actual_and_coherent_required_optional_roles_compile(self):
        for supervision_optional in (True, False):
            self.selected()['fields'] = 'detail,error,supervision' + ('?' if supervision_optional else '')
            required = self.doc['components']['schemas']['VerifyUnavailable']['required']
            if not supervision_optional:
                required.append('supervision')
            self.write()
            fields, optional = self.wanted()
            got = self.compile_readback(self.gen.render(self.form)['refusals.go'])
            self.assertEqual(got['Fields'], fields)
            self.assertEqual(got.get('OptionalFields') or [], optional)

    def test_required_only_projection_is_valid_and_keeps_full_openapi(self):
        # Platform/06-console/forms/README.md:35 projects required direct
        # properties; optional and conditional fields stay in the full OpenAPI.
        schema_before = json.dumps(self.doc['components']['schemas']['VerifyUnavailable'], sort_keys=True)
        self.selected()['fields'] = 'detail,error'
        self.write()
        fields, optional = self.wanted()
        got = self.compile_readback(self.gen.render(self.form)['refusals.go'])
        self.assertEqual(got['Fields'], ['detail', 'error'])
        self.assertEqual(got.get('OptionalFields') or [], [])
        self.assertEqual((fields, optional), (['detail', 'error'], []))
        self.assertEqual(self.selected()['response_schema'], 'VerifyUnavailable')
        self.assertEqual(json.dumps(self.doc['components']['schemas']['VerifyUnavailable'], sort_keys=True), schema_before)
        supervision = self.doc['components']['schemas']['VerifyUnavailable']['properties']['supervision']
        self.assertEqual(supervision['required'], ['unreadable'])
        self.assertIs(supervision['properties']['unreadable']['const'], True)

    def test_role_mismatches_malformed_duplicates_and_surfaces_refuse(self):
        original = self.selected()['fields']
        for fields in ('detail?,error,supervision?', 'error,supervision?', 'detail,supervision?',
                       'detail,error,supervision??', 'detail,error,?', 'detail,error,sup?ervision',
                       'detail,error,supervision?,supervision', 'detail,error,supervision,supervision?',
                       'detail,error,unknown?', 'detail,,error,supervision?'):
            self.selected()['fields'] = fields
            self.write()
            with self.subTest(fields=fields), self.assertRaises(self.gen.GenError):
                self.gen.render(self.form)
        self.selected()['fields'] = original
        for surface in ('call', 'cli', 'start', 'process', 'peer'):
            self.selected()['surface'] = surface
            self.write()
            with self.subTest(surface=surface), self.assertRaises(self.gen.GenError):
                self.gen.render(self.form)
        self.selected()['surface'] = 'http'
        self.selected()['response_schema'] = '-'
        self.write()
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def test_compiled_field_role_mutants_are_semantic_disagreements(self):
        fields, optional = self.wanted()
        original = self.gen.render(self.form)['refusals.go']
        line = next(line for line in original.split('\n') if 'Name: "c67_027_503_1"' in line)
        for old, new in [('OptionalFields: []string{"supervision"}', 'OptionalFields: nil'),
                         ('OptionalFields: []string{"supervision"}', 'OptionalFields: []string{"detail"}'),
                         ('Fields: []string{"detail", "error", "supervision"}', 'Fields: []string{"detail", "error"}')]:
            self.assertEqual(line.count(old), 1)
            changed = original.replace(line, line.replace(old, new), 1)
            self.assertNotEqual(changed, original)
            got = self.compile_readback(changed)
            self.assertNotEqual((got['Fields'], got.get('OptionalFields') or []), (fields, optional))

    def test_form_required_schema_optional_is_valid(self):
        self.selected()['fields'] = 'detail,error,supervision'
        self.write()
        fields, optional = self.wanted()
        got = self.compile_readback(self.gen.render(self.form)['refusals.go'])
        self.assertEqual(got['Fields'], fields)
        self.assertEqual(got.get('OptionalFields') or [], optional)

    def test_dash_keeps_composed_schema_and_validates_missing_targets(self):
        self.selected()['fields'] = '-'
        self.write()
        original = self.api.read_text()
        marker = '    VerifyUnavailable:\n'
        start = original.index(marker)
        end = original.index('    ManifestSource:\n', start)
        # Full-resource composition remains valid without inventing direct fields.
        composed = marker + '      allOf:\n      - $ref: "#/components/schemas/Unavailable"\n'
        self.api.write_text(original[:start] + composed + original[end:])
        self.assertEqual(self.wanted(), ([], []))
        got = self.compile_readback(self.gen.render(self.form)['refusals.go'])
        self.assertEqual(got['Fields'] or [], [])
        self.api.write_text(original[:start] + composed.replace('/Unavailable', '/MissingTarget') + original[end:])
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def test_external_ref_follows_each_resource_base(self):
        self.selected()['fields'] = 'detail,error,supervision?'
        self.write()
        original = self.api.read_text()
        start = original.index('    VerifyUnavailable:\n')
        end = original.index('    ManifestSource:\n', start)
        data = self.home / 'Platform/common/data'
        (data / 'judge-role.schema.json').write_text(json.dumps({'$ref':'judge-target.schema.json#/$defs/Answer'}))
        target = data / 'judge-target.schema.json'
        target.write_text(json.dumps({'$defs': {'Answer': self.doc['components']['schemas']['VerifyUnavailable']}}))
        alias = '    VerifyUnavailable:\n      $ref: "../../common/data/judge-role.schema.json"\n'
        self.api.write_text(original[:start] + alias + original[end:])
        fields, optional = self.wanted()
        got = self.compile_readback(self.gen.render(self.form)['refusals.go'])
        self.assertEqual((got['Fields'], got.get('OptionalFields') or []), (fields, optional))
        target.unlink()
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def test_dash_external_ref_still_checks_full_target(self):
        self.selected()['fields'] = '-'
        self.write()
        original = self.api.read_text()
        start = original.index('    VerifyUnavailable:\n')
        end = original.index('    ManifestSource:\n', start)
        alias = '    VerifyUnavailable:\n      $ref: "../../common/data/judge-absent.schema.json"\n'
        self.api.write_text(original[:start] + alias + original[end:])
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def test_new_norm_role_negative_controls(self):
        original = self.selected()['fields']
        for fields in ('detail?,error,supervision?', 'error,supervision?', 'detail,supervision?',
                       'detail,error,supervision??', 'detail,error,?', 'detail,error,sup?ervision',
                       'detail,error,supervision?,supervision', 'detail,error,supervision,supervision?',
                       'detail,error,unknown?', 'detail,,error,supervision?'):
            self.selected()['fields'] = fields
            self.write()
            with self.subTest(fields=fields), self.assertRaises(self.gen.GenError):
                self.gen.render(self.form)
        self.selected()['fields'] = original
        for surface in ('call', 'cli', 'start', 'process', 'peer'):
            self.selected()['surface'] = surface
            self.write()
            with self.subTest(surface=surface), self.assertRaises(self.gen.GenError):
                self.gen.render(self.form)
        self.selected()['surface'] = 'http'
        self.selected()['response_schema'] = '-'
        self.write()
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def test_independent_source_roles_and_external_perhop_base(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('owned_independent_refusal_oracle', HERE / 'refusal_judge.py')
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        from types import SimpleNamespace
        from unittest.mock import patch
        def read():
            with patch.object(oracle, 'L', SimpleNamespace(openapi=self.api)):
                return oracle.read_plain_source(self.form)
        actual = read()
        self.assertEqual(len(actual), len(self.rows))
        # A form-required schema-optional property is valid for the independent oracle too.
        self.selected()['fields'] = 'detail,error,supervision'
        self.write()
        self.assertEqual(next(r for r in read() if r['name'] == self.name)['_optional'], [])
        for bad in ('detail?,error,supervision?', 'error,supervision?', 'detail,error,unknown?'):
            self.selected()['fields'] = bad
            self.write()
            with self.subTest(fields=bad), self.assertRaises(oracle.CheckingError):
                read()
        self.selected()['fields'] = 'detail,error,supervision?'
        self.write()
        original = self.api.read_text()
        start = original.index('    VerifyUnavailable:\n')
        end = original.index('    ManifestSource:\n', start)
        data = self.home / 'Platform/common/data'
        (data / 'judge-role.schema.json').write_text(json.dumps({'$ref':'judge-target.schema.json#/$defs/Answer'}))
        target = data / 'judge-target.schema.json'
        target.write_text(json.dumps({'$defs': {'Answer': self.doc['components']['schemas']['VerifyUnavailable']}}))
        alias = '    VerifyUnavailable:\n      $ref: "../../common/data/judge-role.schema.json"\n'
        self.api.write_text(original[:start] + alias + original[end:])
        self.assertEqual(len(read()), len(self.rows))
        # No direct projection still validates both reference hops and the actual target.
        self.selected()['fields'] = '-'
        with self.form.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=self.names, delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(self.rows)
        self.assertEqual(len(read()), len(self.rows))
        target.write_text(json.dumps({'$defs': {'Wrong': {}}}))
        with self.assertRaises(oracle.CheckingError):
            read()
        target.unlink()
        with self.assertRaises(oracle.CheckingError):
            read()

    def test_independent_ref_owner_and_target_position_guards(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('owned_refusal_owner_oracle', HERE / 'refusal_judge.py')
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        reader = oracle.SourceSchemas(self.api)
        base = self.api.resolve()
        # Positive target first; forbidden targets never become semantic disagreement.
        node, _, _ = reader.target('#/components/schemas/VerifyUnavailable', base)
        self.assertEqual(node['required'], ['detail', 'error'])
        for ref in ('#/components/schemas/VerifyUnavailable/required',
                    '../../../../outside.schema.json',
                    '../../09-agent/spec/09-agent.api.openapi.yaml#/components/schemas/AgentRefusal',
                    '06-console.api.openapi.yaml#/components/schemas/VerifyUnavailable'):
            with self.subTest(ref=ref), self.assertRaises(oracle.CheckingError):
                reader.target(ref, base)
        data = self.home / 'Platform/common/data'
        hop = data / 'judge-owner.schema.json'
        hop.write_text(json.dumps({'$ref': '../../06-console/spec/06-console.api.openapi.yaml#/components/schemas/VerifyUnavailable'}))
        with self.assertRaises(oracle.CheckingError):
            reader.closure(reader.load(hop), hop.resolve())

    def test_dash_rejects_malformed_full_schema_independently(self):
        import importlib.util
        from types import SimpleNamespace
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('owned_fullschema_oracle', HERE / 'refusal_judge.py')
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        self.selected()['fields'] = '-'
        self.write()
        with patch.object(oracle, 'L', SimpleNamespace(openapi=self.api)):
            self.assertEqual(len(oracle.read_plain_source(self.form)), len(self.rows))
            original = self.api.read_text()
            start = original.index('    VerifyUnavailable:\n')
            end = original.index('    ManifestSource:\n', start)
            section = original[start:end]
            self.assertEqual(section.count('required: [detail, error]'), 1)
            self.api.write_text(original[:start] + section.replace('required: [detail, error]', 'required: detail') + original[end:])
            with self.assertRaises(oracle.CheckingError):
                oracle.read_plain_source(self.form)
        with self.assertRaises(self.gen.GenError):
            self.gen.render(self.form)

    def _oracle_boundary_begin(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('owned_boundary_oracle', HERE / 'refusal_judge.py')
        self._boundary_m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self._boundary_m)
        self._boundary_versions = {self.api: [self.api.read_bytes()]}
        self._boundary_normal = self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable')
        self.assertEqual(self._boundary_normal['required'], ['detail', 'error'])

    def _oracle_boundary_file(self, path, value):
        path = Path(path)
        history = self._boundary_versions.setdefault(path, [path.read_bytes() if path.is_file() else None])
        if value is None:
            path.unlink()
            history.append(None)
        else:
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            path.write_bytes(raw)
            history.append(raw)
        return path

    def _oracle_boundary_set(self, schema):
        start = self.api_text.index('    VerifyUnavailable:\n')
        end = self.api_text.index('    ManifestSource:\n', start)
        self._oracle_boundary_file(self.api, (self.api_text[:start] + '    VerifyUnavailable: ' +
                                  json.dumps(schema, ensure_ascii=False) + '\n' + self.api_text[end:]).encode())

    def _oracle_boundary_observe(self, name, action, error=False, wanted=None):
        import datetime
        import hashlib
        home = Path(os.environ['ORACLE_BOUNDARY_EVIDENCE']) / os.environ.get('BOUNDARY_ATTEMPT', 'before') / self._testMethodName / name
        home.mkdir(parents=True)
        identities = {}
        for i, (path, versions) in enumerate(self._boundary_versions.items()):
            identities[str(path.relative_to(self.home))] = []
            for n, raw in enumerate(versions):
                entry = {'exists': raw is not None}
                if raw is not None:
                    filename = f'input-{i}-version-{n}'
                    (home / filename).write_bytes(raw)
                    entry.update(file=filename, sha256=hashlib.sha256(raw).hexdigest())
                identities[str(path.relative_to(self.home))].append(entry)
        record = {'test': self.id(), 'name': name, 'expected_CheckingError': error,
                  'start': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': identities,
                  'Source_pin': '03df76f29457d46ffa8a89d9e1f66ab9b9383b29', 'semantic_kills': 0}
        record['fixture_home'] = str(self.home)
        record['main_resource'] = str(self.api)
        record['action_default_arguments'] = [repr(value) for value in (action.__defaults__ or ())]
        record['admitted_raw_identities_before_reuse'] = {}
        for cell in action.__closure__ or ():
            value = cell.cell_contents
            if isinstance(value, self._boundary_m.SourceSchemas):
                record['admitted_raw_identities_before_reuse'].update(
                    {str(path): identity for path, identity in value.raw_identities.items()})
        (home / 'before.json').write_text(json.dumps(record, indent=2) + '\n')
        try:
            try:
                value = action()
            except Exception as exc:
                record['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
                if not error:
                    raise
                self.assertIsInstance(exc, self._boundary_m.CheckingError)
            else:
                record['returned'] = repr(value)
                self.assertFalse(error, 'oracle accepted a forbidden, invalid, or changed resource')
                if wanted is not None:
                    self.assertEqual(value, wanted)
            record['status'] = 'PASS'
        except BaseException as exc:
            record['status'] = 'CHECK_FAILURE'
            record['failure'] = repr(exc)
            raise
        finally:
            record['end'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (home / 'result.json').write_text(json.dumps(record, indent=2) + '\n')

    def test_oracle_boundary_enclosing_schema(self):
        self._oracle_boundary_begin()
        path = self.home / 'Platform/common/data/boundary-outer.schema.json'
        cases = [('outer-required-string', {'required': 'Leaf', 'properties': {'Leaf': {'type': 'string'}}}),
                 ('unselected-missing-ref', {'properties': {'Leaf': {'type': 'string'}, 'Other': {'$ref': '#/$defs/Missing'}}}),
                 ('unselected-forbidden-ref', {'properties': {'Leaf': {'type': 'string'}, 'Other': {'$ref': '../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/ResourceError'}}})]
        for name, outer in cases:
            with self.subTest(name=name):
                self._oracle_boundary_file(path, {'$defs': {'Outer': outer}})
                self._oracle_boundary_set({'$ref': '../../common/data/boundary-outer.schema.json#/$defs/Outer/properties/Leaf'})
                self._oracle_boundary_observe(name, lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=True)

    def test_oracle_boundary_openapi_enclosing_schema(self):
        self._oracle_boundary_begin()
        path = self.home / 'Platform/05-resource/spec/05-resource.api.openapi.yaml'
        import yaml
        document = yaml.safe_load(path.read_text())
        document['components']['schemas']['Outer'] = {'required': 'Leaf', 'properties': {'Leaf': True}}
        self._oracle_boundary_file(path, json.dumps(document, ensure_ascii=True).encode())
        self._oracle_boundary_set({'$ref': '../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/Outer/properties/Leaf'})
        self._oracle_boundary_observe('openapi-outer-required-string', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=True)

    def test_oracle_boundary_uri_matching_files(self):
        self._oracle_boundary_begin()
        from urllib.parse import quote
        data = self.home / 'Platform/common/data'
        plain = self._oracle_boundary_file(data / 'absolute.schema.json', True)
        references = [('absolute-existing', str(plain)), ('encoded-absolute-existing', quote(str(plain), safe=''))]
        for name, file, ref in [('bad-percent-path', 'bad%ZZ.schema.json', 'bad%ZZ.schema.json'),
                                ('bad-utf8-path', '\ufffd.schema.json', '%FF.schema.json'),
                                ('encoded-backslash-path', 'back' + chr(92) + 'slash.schema.json', 'back%5Cslash.schema.json')]:
            self._oracle_boundary_file(data / file, True)
            references.append((name, '../../common/data/' + ref))
        self._oracle_boundary_file(data / 'fragment.schema.json', {'$defs': {'bad%ZZ': True, '\ufffd': True}})
        references += [('bad-percent-pointer', '../../common/data/fragment.schema.json#/$defs/bad%ZZ'),
                       ('bad-utf8-pointer', '../../common/data/fragment.schema.json#/$defs/%FF')]
        for name, ref in references:
            with self.subTest(name=name):
                reader = self._boundary_m.SourceSchemas(self.api)
                self._oracle_boundary_observe(name, lambda ref=ref: reader.target(ref, self.api), error=True)
        self._oracle_boundary_file(data / '\u03bb.schema.json', {'$defs': {'\u540d/leaf~': {'type': 'string'}}})
        ref = '../../common/data/' + quote('\u03bb.schema.json') + '#/$defs/' + quote('\u540d~1leaf~0')
        self._oracle_boundary_file(data / 'unicode-hop.schema.json', {'$ref': ref.rsplit('/', 1)[0].split('/data/', 1)[1] + '/' + ref.rsplit('/', 1)[1]})
        self._oracle_boundary_set({'$ref': '../../common/data/unicode-hop.schema.json'})
        self._oracle_boundary_observe('valid-encoded-unicode-perhop', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), wanted={'type': 'string'})

    def test_oracle_boundary_admitted_cache_identity(self):
        self._oracle_boundary_begin()
        original = self.api.read_bytes()
        external = self.home / 'Platform/common/data/cache.schema.json'
        for name in ('main-change', 'main-remove', 'external-change', 'external-remove', 'admitted-external-remove-main-query'):
            with self.subTest(name=name):
                self._oracle_boundary_file(self.api, original)
                self._oracle_boundary_file(external, {'type': 'string'})
                reader = self._boundary_m.SourceSchemas(self.api)
                reader.schema('VerifyUnavailable')
                reader.target('../../common/data/cache.schema.json', self.api)
                import hashlib
                self.assertIn(self.api, reader.raw_identities)
                self.assertEqual(reader.raw_identities[external]['sha256'], hashlib.sha256(external.read_bytes()).hexdigest())
                if name.startswith('main-'):
                    self._oracle_boundary_file(self.api, None if name.endswith('remove') else b'{}')
                    action = lambda: reader.schema('VerifyUnavailable')
                else:
                    self._oracle_boundary_file(external, {'type': 'number'} if name=='external-change' else None)
                    action = (lambda: reader.schema('VerifyUnavailable')) if name.startswith('admitted-') else (lambda: reader.target('../../common/data/cache.schema.json', self.api))
                try:
                    self._oracle_boundary_observe(name, action, error=True)
                finally:
                    self._oracle_boundary_file(self.api, original)

    def test_oracle_boundary_yaml_json_values(self):
        self._oracle_boundary_begin()
        start = self.api_text.index('    VerifyUnavailable:\n')
        end = self.api_text.index('    ManifestSource:\n', start)
        section = '    VerifyUnavailable:\n      default: on\n      examples: [2026-11-08]\n      properties:\n        on: {type: string}\n'
        self._oracle_boundary_file(self.api, (self.api_text[:start] + section + self.api_text[end:]).encode())
        with self.subTest(name='yaml12-on-date'):
            self._oracle_boundary_observe('yaml12-on-date', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'),
                                          wanted={'default': 'on', 'examples': ['2026-11-08'], 'properties': {'on': {'type': 'string'}}})
        for name, value in [('yaml-nonfinite', '      default: .nan\n'), ('yaml-binary', '      default: !!binary YQ==\n')]:
            with self.subTest(name=name):
                self._oracle_boundary_file(self.api, (self.api_text[:start] + '    VerifyUnavailable:\n' + value + self.api_text[end:]).encode())
                self._oracle_boundary_observe(name, lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=True)
        path = self.home / 'Platform/common/data/nonfinite.schema.json'
        self._oracle_boundary_file(path, b'{"default":1e999}')
        self._oracle_boundary_set({'$ref': '../../common/data/nonfinite.schema.json'})
        self._oracle_boundary_observe('json-overflow', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=True)

    def test_oracle_boundary_chain_separation(self):
        self._oracle_boundary_begin()
        data = self.home / 'Platform/common/data'
        a = {'$defs': {'scalar': {'type': 'string'}}, 'properties': {'other': {'$ref': 'b.schema.json#/$defs/scalar'}}}
        b = {'$defs': {'scalar': {'type': 'number'}}, 'properties': {'other': {'$ref': 'a.schema.json#/$defs/scalar'}}}
        self._oracle_boundary_file(data / 'a.schema.json', a)
        self._oracle_boundary_file(data / 'b.schema.json', b)
        self._oracle_boundary_set({'$ref': '../../common/data/a.schema.json'})
        self._oracle_boundary_observe('legal-disjoint-cross-refs', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), wanted=a)
        self._oracle_boundary_file(data / 'a.schema.json', {'$defs': {'scalar': True}, 'properties': {'other': {'$ref': 'b.schema.json#/$defs/return'}}})
        self._oracle_boundary_file(data / 'b.schema.json', {'$defs': {'return': {'$ref': 'a.schema.json#/$defs/scalar'}}})
        self._oracle_boundary_observe('finite-return-different-pointer', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), wanted={'$defs': {'scalar': True}, 'properties': {'other': {'$ref': 'b.schema.json#/$defs/return'}}})
        local = {'type': 'object', 'properties': {'next': {'$ref': '#'}}}
        self._oracle_boundary_file(data / 'a.schema.json', local)
        self._oracle_boundary_observe('local-recursion', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), wanted=local)
        self._oracle_boundary_set({'default': {'$ref': '../../missing.schema.json'}, 'examples': [{'$ref': 'https://example.invalid/a'}]})
        self._oracle_boundary_observe('opaque-annotation-ref-data', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'),
                                      wanted={'default': {'$ref': '../../missing.schema.json'}, 'examples': [{'$ref': 'https://example.invalid/a'}]})

    def test_oracle_boundary_uri_io_type_errors(self):
        self._oracle_boundary_begin()
        bad = self.home / 'Platform/common/data/invalid-utf8.schema.json'
        self._oracle_boundary_file(bad, b'\xff')
        reader = self._boundary_m.SourceSchemas(self.api)
        cases = [('nontext-ref-guarded', lambda: reader.target(None, self.api)),
                 ('malformed-uri', lambda: reader.target('http://[', self.api)),
                 ('invalid-utf8-resource', lambda: reader.target('../../common/data/invalid-utf8.schema.json', self.api)),
                 ('nonpath-base', lambda: reader.target('#/components/schemas/VerifyUnavailable', None)),
                 ('nonpath-load', lambda: reader.load(None))]
        for name, action in cases:
            with self.subTest(name=name):
                self._oracle_boundary_observe(name, action, error=True)

    def test_oracle_boundary_unselected_null_schema(self):
        self._oracle_boundary_begin()
        import yaml
        path = self.home / 'Platform/05-resource/spec/05-resource.api.openapi.yaml'
        document = yaml.safe_load(path.read_text())
        document['components']['schemas']['BoundaryUnused'] = None
        document['components']['schemas']['BoundaryLeaf'] = True
        self._oracle_boundary_file(path, json.dumps(document, ensure_ascii=True).encode())
        self._oracle_boundary_set({'$ref': '../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/BoundaryLeaf'})
        self._oracle_boundary_observe('unselected-null-schema', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=True)

    def _canonical_cycle_observe(self, name, a, b, selected, error=False, wanted=None):
        data = self.home / 'Platform/common/data'
        self._oracle_boundary_file(data / 'cycle-a.schema.json', a)
        if b is not None:
            self._oracle_boundary_file(data / 'cycle-b.schema.json', b)
        self._oracle_boundary_set({'$ref': '../../common/data/cycle-a.schema.json#/$defs/' + selected})
        self._oracle_boundary_observe(name, lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=error, wanted=wanted)

    def test_canonical_cycle_normal_source_positive(self):
        self._oracle_boundary_begin()
        self._oracle_boundary_observe('canonical-Source03df-positive', lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), wanted=self._boundary_normal)

    def test_canonical_cycle_finite_pointer_return(self):
        self._oracle_boundary_begin()
        a = {'$defs': {'Start': {'$ref': 'cycle-b.schema.json#/$defs/Alias'}, 'Leaf': {'type': 'string'}}}
        b = {'$defs': {'Alias': {'$ref': 'cycle-a.schema.json#/$defs/Leaf'}}}
        self._canonical_cycle_observe('A-Start-B-Alias-A-Leaf-finite', a, b, 'Start', wanted={'type': 'string'})

    def test_canonical_cycle_true_closed_pair(self):
        self._oracle_boundary_begin()
        a = {'$defs': {'Start': {'$ref': 'cycle-b.schema.json#/$defs/Alias'}, 'Leaf': True}}
        b = {'$defs': {'Alias': {'$ref': 'cycle-a.schema.json#/$defs/Start'}}}
        for selected in ('Start', 'Leaf'):
            with self.subTest(selected=selected):
                self._canonical_cycle_observe('closed-A-Start-B-Alias-A-Start-selected-' + selected, a, b, selected, error=True)

    def test_canonical_cycle_local_recursion(self):
        self._oracle_boundary_begin()
        recursive = {'type': 'object', 'properties': {'next': {'$ref': '#/$defs/Recursive'}}}
        self._canonical_cycle_observe('same-file-recursion', {'$defs': {'Recursive': recursive}}, None, 'Recursive', wanted=recursive)

    def test_canonical_cycle_foreign_arrival_local_recursion(self):
        self._oracle_boundary_begin()
        recursive = {'type': 'object', 'properties': {'next': {'$ref': '#/$defs/Recursive'}}}
        a = {'$defs': {'Start': {'$ref': 'cycle-b.schema.json#/$defs/Recursive'}}}
        self._canonical_cycle_observe('foreign-prefix-local-closed-segment', a, {'$defs': {'Recursive': recursive}}, 'Start', wanted=recursive)

    def test_canonical_cycle_uri_owner_type_provenance_guards(self):
        self._oracle_boundary_begin()
        from urllib.parse import quote
        data = self.home / 'Platform/common/data'
        target = self._oracle_boundary_file(data / 'matching.schema.json', True)
        reader = self._boundary_m.SourceSchemas(self.api)
        for name, ref in [('encoded-absolute-matching-file', quote(str(target), safe='')), ('nontext-reference', None)]:
            with self.subTest(name=name):
                self._oracle_boundary_observe(name, lambda ref=ref: reader.target(ref, self.api), error=True)
        a = {'$defs': {'Start': {'$ref': 'cycle-b.schema.json#/$defs/Alias'}}}
        b = {'$defs': {'Alias': {'$ref': '../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/ResourceError'}}}
        self._canonical_cycle_observe('per-declaration-common-owner-guard', a, b, 'Start', error=True)
        self._oracle_boundary_set(self._boundary_normal)
        reader = self._boundary_m.SourceSchemas(self.api)
        original = self.api.read_bytes()
        self._oracle_boundary_file(self.api, b'{}')
        try:
            self._oracle_boundary_observe('admitted-Source-identity-guard', lambda: reader.schema('VerifyUnavailable'), error=True)
        finally:
            self._oracle_boundary_file(self.api, original)

    def test_canonical_cycle_enclosing_openapi_meta(self):
        self._oracle_boundary_begin()
        import copy
        path = self.home / 'Platform/05-resource/spec/05-resource.api.openapi.yaml'
        original = self._boundary_m.SourceSchemas(path).doc
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                doc = copy.deepcopy(original)
                doc['components']['schemas']['Outer'] = {'type': 'object', 'required': 'Leaf' if invalid else ['Leaf'], 'properties': {'Leaf': {'type': 'string'}}}
                self._oracle_boundary_file(path, json.dumps(doc, ensure_ascii=True).encode())
                self._oracle_boundary_set({'$ref': '../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/Outer/properties/Leaf'})
                self._oracle_boundary_observe('enclosing-Outer-Leaf-' + ('invalid-required' if invalid else 'valid'), lambda: self._boundary_m.SourceSchemas(self.api).schema('VerifyUnavailable'), error=invalid, wanted=None if invalid else {'type': 'string'})

if __name__ == "__main__":
    unittest.main()
