"""Independent TSV oracle and compiled-output mutants of P/08 core version metadata; P/01 core stays unchanged."""
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
sys.path.insert(0, str(HERE))
import gen_versioned_doors as g

GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
ROWS = [
    ["POST", "/domain/members", "domain/member-rows/<part>", "doc.rev", "true", "optional", "0"],
    ["DELETE", "/domain/members/{name}", "domain/member-rows/<part>", "doc.rev", "true", "optional", "-"],
    ["POST", "/domain/users", "-", "revision", "true", "ignored", "-"],
    ["PUT", "/domain/users/{name}", "domain/users/<name>", "revision", "true", "optional", "-"],
    ["DELETE", "/domain/users/{name}", "domain/users/<name>", "revision", "false", "optional", "-"],
    ["POST", "/domain/batch", "writes[]", "revision", "false", "ignored", "0"],
    ["PUT", "/domain/topology", "domain/topology", "doc.rev", "true", "base-rev", "0"],
    ["PUT", "/domain/placement/{sub}/{ref}", "domain/placement/<sub>/<ref>", "rev", "true", "optional", "0"],
    ["DELETE", "/domain/placement/{sub}/{ref}", "domain/placement/<sub>/<ref>", "rev", "false", "optional", "-"],
]
NORMS = "P/08.0-R005,P/08.0-R006"
COLUMNS = ["method", "path", "row", "revision", "etag", "if_match", "absent_revision", "norm"]
FORM = Path("Platform/08-domain/forms/versioned-doors.tsv")
API = Path("Platform/08-domain/spec/08-domain.api.openapi.yaml")


def fixture(root, rows=ROWS):
    import yaml
    form, api = root / FORM, root / API
    form.parent.mkdir(parents=True, exist_ok=True)
    api.parent.mkdir(parents=True, exist_ok=True)
    form.write_text("\t".join(COLUMNS) + "\n" + "\n".join("\t".join(r + [NORMS]) for r in rows) + "\n")
    paths = {}
    for n, row in enumerate(rows):
        method, path, _, _, etag, mode, _ = row
        import re
        params = [{"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
                  for name in re.findall(r"{([^}]+)}", path)]
        if mode != "ignored":
            params.append({"name": "If-Match", "in": "header", "required": False, "schema": {"type": "string"}})
        response = {"description": "success"}
        if etag == "true":
            response["headers"] = {"ETag": {"schema": {"type": "string"}}}
        paths.setdefault(path, {})[method.lower()] = {
            "operationId": f"Operation{n}", "parameters": params, "responses": {"200": response}}
    api.write_text(yaml.safe_dump({"openapi": "3.1.0", "paths": paths}, sort_keys=False))
    (api.parent / "08.0-domain.norms.md").write_text(
        "<!-- req: P/08.0-R005 -->\nVersions.\n<!-- req: P/08.0-R006 -->\nConditions.\n")
    return form


def oracle(form):
    """Read cells independently of the generator; compare every published field of the Go metadata."""
    rows = csv.DictReader((s for s in Path(form).read_text().splitlines() if s and not s.startswith("#")), delimiter="\t")
    out = []
    for r in rows:
        special = {"-": "none", "writes[]": "writes"}
        out.append(dict(Method=r["method"], Path=r["path"], RowKind=special.get(r["row"], "selected"),
                        RowTemplate="" if r["row"] in special else r["row"], Revision=r["revision"],
                        ETag=r["etag"] == "true", IfMatch=r["if_match"], AbsentRevisionZero=r["absent_revision"] == "0",
                        Norms=r["norm"].split(",")))
    return out


def probe(text, mod):
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "go.mod").write_text("module versionjudge\n\ngo 1.22\n")
    (mod / "coreadapter").mkdir(exist_ok=True)
    (mod / "coreadapter/versioned_doors.go").write_text(text)
    (mod / "main.go").write_text('''package main
import ("encoding/json"; "os"; "versionjudge/coreadapter")
func main() { json.NewEncoder(os.Stdout).Encode(coreadapter.VersionedDoors()) }
''')
    return subprocess.run(["go", "run", "."], cwd=mod, capture_output=True, text=True, env=GOENV)


class VersionedDoors(unittest.TestCase):
    def setUp(self):
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        self.tmp = tempfile.TemporaryDirectory(prefix="versioned-doors-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.form = fixture(self.root)

    def text(self):
        return g.render(self.root, "08-domain")["coreadapter/versioned_doors.go"]

    def test_compiled_oracle(self):
        done = probe(self.text(), Path(self.tmp.name) / "go")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), oracle(self.form))

    def test_lookup_and_independent_values(self):
        mod = Path(self.tmp.name) / "go"
        done = probe(self.text(), mod)
        self.assertEqual(done.returncode, 0, done.stderr)
        (mod / "coreadapter/metadata_test.go").write_text('''package coreadapter
import "testing"
func TestMetadata(t *testing.T) {
    created,ok:=VersionedDoorFor("POST","/domain/users")
    if !ok || created.RowKind!=NoVersionRow || created.RowTemplate!="" || !created.ETag || created.IfMatch!=IgnoredIfMatch { t.Fatalf("create: %#v",created) }
    member,ok:=VersionedDoorFor("DELETE","/domain/members/{name}")
    if !ok || !member.ETag || member.RowTemplate!="domain/member-rows/<part>" { t.Fatalf("member exception: %#v",member) }
    batch,ok:=VersionedDoorFor("POST","/domain/batch")
    if !ok || batch.RowKind!=BatchVersionRows || batch.RowTemplate!="" || batch.ETag || !batch.AbsentRevisionZero { t.Fatalf("batch: %#v",batch) }
    if _,ok:=VersionedDoorFor("PUT","/domain/users/alice"); ok { t.Fatal("request URL treated as a selected template") }
    if _,ok:=VersionedDoorFor("GET","/domain/users/{name}"); ok { t.Fatal("foreign method") }
    all:=VersionedDoors(); all[0].Norms[0]="edited"; all[0].RowTemplate="edited"
    found,_:=VersionedDoorFor("POST","/domain/members")
    if found.Norms[0]!="P/08.0-R005" || found.RowTemplate!="domain/member-rows/<part>" { t.Fatal("mutable metadata") }
    found.Norms[0]="edited again"
    if VersionedDoors()[0].Norms[0]!="P/08.0-R005" { t.Fatal("lookup shares mutable norms") }
}
''')
        done = subprocess.run(["go", "test", "-count=1", "./coreadapter/"], cwd=mod,
                              capture_output=True, text=True, env=GOENV)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_output_mutants(self):
        original = self.text()
        want = oracle(self.form)
        def change(method, path, old, new):
            lines = original.splitlines(keepends=True)
            for i, line in enumerate(lines):
                if f'Method: "{method}", Path: "{path}"' in line:
                    self.assertIn(old, line)
                    lines[i] = line.replace(old, new, 1)
                    return "".join(lines)
            self.fail(f"no generated row {method} {path}")
        first = next(s for s in original.splitlines(keepends=True) if 'Method: "POST", Path: "/domain/members"' in s)
        mutations = {
            "missing operation": original.replace(first, "", 1),
            "foreign row": change("PUT", "/domain/users/{name}", 'RowTemplate: "domain/users/<name>"', 'RowTemplate: "domain/foreign/<name>"'),
            "foreign revision": change("POST", "/domain/members", "Revision: DocumentRevision", "Revision: RowRevision"),
            "delete ETag": change("DELETE", "/domain/users/{name}", "ETag: false", "ETag: true"),
            "batch ETag": change("POST", "/domain/batch", "ETag: false", "ETag: true"),
            "member-delete ETag": change("DELETE", "/domain/members/{name}", "ETag: true", "ETag: false"),
            "ignored If-Match": change("POST", "/domain/batch", "IfMatch: IgnoredIfMatch", "IfMatch: OptionalIfMatch"),
            "base-rev": change("PUT", "/domain/topology", "IfMatch: BaseRevisionIfMatch", "IfMatch: OptionalIfMatch"),
            "missing absent revision 0": change("PUT", "/domain/topology", "AbsentRevisionZero: true", "AbsentRevisionZero: false"),
        }
        for name, text in mutations.items():
            with self.subTest(mutant=name):
                done = probe(text, Path(self.tmp.name) / "go")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotEqual(json.loads(done.stdout), want, "mutant survived")

    def test_form_refusals(self):
        original = self.form.read_text()
        lines = original.splitlines()
        mutations = {"header": original.replace("absent_revision\t", "source\tabsent_revision\t", 1),
                     "duplicate": original + lines[1] + "\n", "missing": "\n".join(lines[:-1]) + "\n"}
        for col, value in [("revision", "doc.counter"), ("etag", "yes"), ("if_match", "mandatory"),
                           ("absent_revision", "1"), ("norm", "P/08.0-R999"), ("row", "domain/members/<unknown>")]:
            row = lines[1].split("\t")
            row[COLUMNS.index(col)] = value
            mutations[col] = "\n".join([lines[0], "\t".join(row)] + lines[2:]) + "\n"
        mutations["base-rev norm"] = original.replace("base-rev\t0\t" + NORMS, "base-rev\t0\tP/08.0-R005")
        for name, text in mutations.items():
            with self.subTest(form=name):
                self.form.write_text(text)
                with self.assertRaises(g.GenError):
                    self.text()
        self.form.write_text(original)

    def test_closed_new_modes_and_compiled_independent_oracle(self):
        extra = ["PUT", "/domain/memberof/{member}/{sub}/{rows}/{id}", "domain/memberof/<member>/<sub>/<rows>/<id>", "-", "false", "optional-index", "-"]
        rows = [list(r) for r in ROWS] + [extra]
        self.form = fixture(self.root, rows)
        done = probe(self.text(), Path(self.tmp.name) / "go")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), oracle(self.form))
        rows[5][3], rows[5][6] = "-", "-"  # Batch has no API If-Match and explicitly needs metadata.
        fixture(self.root, rows)
        done = probe(self.text(), Path(self.tmp.name) / "go")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), oracle(self.form))

    def test_new_mode_invalid_combinations_are_refused(self):
        base = ["PUT", "/domain/memberof/{member}/{sub}/{rows}/{id}", "domain/memberof/<member>/<sub>/<rows>/<id>", "-", "false", "optional-index", "-"]
        for field, value in (("absent_revision", "0"), ("etag", "true"), ("if_match", "optional"),
                             ("if_match", "base-rev")):
            rows = [list(r) for r in ROWS] + [list(base)]
            rows[-1][COLUMNS.index(field)] = value
            fixture(self.root, rows)  # API stays coherent where applicable; logical combination is still invalid.
            with self.subTest(field=field, value=value), self.assertRaises(g.GenError):
                self.text()
        fixture(self.root, [list(r) for r in ROWS] + [list(base)])
        original = self.form.read_text()
        self.assertEqual(original.count("optional-index"), 1)
        self.form.write_text(original.replace("optional-index", "ignored"))
        with self.assertRaises(g.GenError):
            self.text()  # Existing If-Match forbids ignored.
        no_header = [list(r) for r in ROWS] + [list(base)]
        no_header[-1][5] = "ignored"
        fixture(self.root, no_header)
        self.form.write_text(self.form.read_text().replace("ignored\t-\t" + NORMS, "optional-index\t-\t" + NORMS))
        with self.assertRaises(g.GenError):
            self.text()  # optional-index requires the API header.

    def test_refusal_leaves_output(self):
        out = Path(self.tmp.name) / "out"
        g.generate(out, self.root, "08-domain")
        before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.form.write_text(self.form.read_text().replace("optional", "foreign-mode", 1))
        with self.assertRaises(g.GenError):
            g.generate(out, self.root, "08-domain")
        self.assertEqual(before, {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()})

    def test_no_other_lesson(self):
        with self.assertRaisesRegex(g.GenError, "only for lesson 08-domain"):
            g.render(self.root, "02-installer")

    def test_no_empty_source(self):
        (self.root / API).write_text("openapi: 3.1.0\npaths: {}\n")
        self.form.write_text("\t".join(COLUMNS) + "\n")
        with self.assertRaisesRegex(g.GenError, "no versioned operations"):
            self.text()


class PublishedP08(unittest.TestCase):
    def test_compiled_current_all24_fields_without_renderer_expected(self):
        source = HERE.parents[1] / FORM
        self.assertTrue(source.is_file(), "the published form is required")
        wanted = oracle(source)
        self.assertEqual(len(wanted), 24)
        self.assertEqual(len({(r['Method'], r['Path']) for r in wanted}), 24)
        selected = next(r for r in wanted if r['Method'] == 'PUT' and r['Path'] == '/domain/memberof/{member}/{sub}/{rows}/{id}')
        self.assertEqual((selected['Revision'], selected['ETag'], selected['IfMatch'], selected['AbsentRevisionZero']),
                         ('-', False, 'optional-index', False))
        with tempfile.TemporaryDirectory(prefix='published-versioned-metadata-') as tmp:
            text = g.render(HERE.parents[1], '08-domain')['coreadapter/versioned_doors.go']
            done = probe(text, Path(tmp))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout), wanted)

    def test_current_new_mode_compiled_mutants_have_observable_metadata_disagreements(self):
        source = HERE.parents[1] / FORM
        wanted = oracle(source)
        text = g.render(HERE.parents[1], '08-domain')['coreadapter/versioned_doors.go']
        row = next(line for line in text.split('\n') if 'Path: "/domain/memberof/{member}/{sub}/{rows}/{id}"' in line)
        mutants = [('Revision: NoRevision', 'Revision: RowRevision'),
                   ('IfMatch: OptionalIndexIfMatch', 'IfMatch: OptionalIfMatch'),
                   ('ETag: false', 'ETag: true'),
                   ('AbsentRevisionZero: false', 'AbsentRevisionZero: true')]
        with tempfile.TemporaryDirectory(prefix='published-versioned-mutants-') as tmp:
            baseline = probe(text, Path(tmp))
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            self.assertEqual(json.loads(baseline.stdout), wanted)
            for old, new in mutants:
                with self.subTest(old=old):
                    self.assertEqual(row.count(old), 1)
                    changed = text.replace(row, row.replace(old, new, 1), 1)
                    self.assertNotEqual(changed, text)
                    done = probe(changed, Path(tmp))
                    self.assertEqual(done.returncode, 0, 'checking compile/run error, not a kill: ' + done.stderr)
                    actual = json.loads(done.stdout)
                    self.assertEqual(len(actual), len(wanted))
                    self.assertNotEqual(actual, wanted)

    def test_fresh_and_kit(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        if not shutil.which("go"):
            self.skipTest("go is not in PATH")
        env = dict(os.environ, NORMGEN_LESSON="08-domain")
        kept = output_lesson.output_root() / 'p08/core/coreadapter/versioned_doors.go'
        self.assertTrue(kept.is_file(), "run gen_versioned_doors.py --lesson 08-domain")
        with tempfile.TemporaryDirectory(prefix="versioned-kit-") as tmp:
            out = Path(tmp) / "out"
            done = subprocess.run([sys.executable, str(HERE / "gen_versioned_doors.py"), str(out)], env=env,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(kept.read_bytes(), (out / "core/coreadapter/versioned_doors.go").read_bytes())
            dst = Path(tmp) / "kit"
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--part", "door", "--part", "core"],
                                  env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            manifest = json.loads((dst / "kit.manifest.json").read_text())
            self.assertEqual(manifest["parts"], ["core", "door"])
            f = next(f for f in manifest["files"] if f["path"].endswith("/coreadapter/versioned_doors.go"))
            self.assertFalse(f.get("editable"))
            closed = dst / f["path"]
            expected = closed.read_bytes()
            own = closed.parent / "own.go"
            own.write_text("package coreadapter\nconst OwnMarker = true\n")
            closed.write_text("package coreadapter\nconst Stale = true\n")
            done = subprocess.run([sys.executable, str(HERE / "kit/build_kit.py"), str(dst), "--part", "door", "--part", "core"],
                                  env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(closed.read_bytes(), expected)
            self.assertTrue(own.is_file(), "the core implementation must survive metadata regeneration")
            mod = dst / "08-domain"
            (mod / "go.mod").write_text(f"module {manifest['module']}\n\ngo 1.22\n")
            done = subprocess.run(["go", "vet", "./..."], cwd=mod, capture_output=True, text=True, env=GOENV)
            self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
