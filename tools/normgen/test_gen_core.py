"""Test editable gen_core scaffolds (ADR-0083 addendum 95, item 3). All-part kits must compile/vet; Open returns Store implementing coreadapter.Core. Get keeps the empty-store launch behavior; Write/List return503 not implemented; Rights/chapter 1.3 return503 not in this stage. Stage tests fail without panic. Verify N3/req comments, seed preservation, required door/stagetests and stale-output refusal. Linux CT103, Go 1.22 only."""
import json
import copy
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import lesson as output_lesson
import build_kit  # noqa: E402
import gen_core  # noqa: E402

MOD = "example.com/w2c/store"
PARTS = ["door", "flags", "refusals", "vectors", "stagetests", "launch", "core", "admin", "families"]

PROBE = '''package coreadapter

import (
	"strings"
	"testing"
	"time"
)

func TestCoreStub(t *testing.T) {
	c, err := Open(Config{BodyLimit: 1 << 20, RowCeiling: 1 << 19, Now: time.Now, DataDir: t.TempDir(),
		Rights: []byte(`{"roles":{"acc":{"group":"acc","read":["acc/*"],"write":["acc/*"],"delete":["acc/*"]}}}`)})
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := c.(*Store); !ok {
		t.Fatalf("Open gives %T, want *Store", c)
	}
	defer c.Close()
	cfg := Config{BodyLimit: 1 << 20}
	for _, x := range []struct{ method, target, body, want string; code int }{
		{"GET", "/v1/get?key=acc/x", "", `"index":""`, 200},
		{"GET", "/v1/list?prefix=acc/", "", "not implemented", 503},
		{"POST", "/v1/write", `{"key":"acc/x","items":[]}`, "not implemented", 503},
		{"GET", "/v1/rights", "", "not in this stage", 503},
		{"GET", "/v1/status", "", "not in this stage", 503},
	} {
		var b []byte
		if x.body != "" {
			b = []byte(x.body)
		}
		code, _, body := Handle(c, cfg, Call{Sock: "acc"}, x.method, x.target, map[string]string{}, b)
		if code != x.code || !strings.Contains(string(body), x.want) {
			t.Errorf("%s %s: %d %s, want %d …%s…", x.method, x.target, code, body, x.code, x.want)
		}
	}
}
'''


def build(dst):
    build_kit.build(dst, MOD, PARTS)
    store = Path(dst) / "01-store"
    (store / "go.mod").write_text(f"module {MOD}\n\ngo 1.22\n", encoding="utf-8")
    return store


class SectionLabels(unittest.TestCase):
    def test_n_and_legacy_section_labels(self):
        for stored in ("N3 Procedures", '\u041d3 Procedures'):
            sec = (stored, 2, [("P/01.1-R001", "the anchored text")])
            for lookup in ("N3 Procedures", '\u041d3 Procedures'):
                with self.subTest(stored=stored, lookup=lookup):
                    self.assertIs(gen_core.find([sec], lookup), sec)

    def test_qualifier_and_ambiguity_keep_existing_rules(self):
        sec = ("N3 Procedures(extra)", 2, [])
        self.assertIs(gen_core.find([sec], '\u041d3 Procedures'), sec)
        for secs, name in [([("N30 Procedures", 2, [])], '\u041d3 Procedures'),
                           ([('other \u041d3 Procedures', 2, [])], "other N3 Procedures"),
                           ([('\u041d3 Procedures', 2, []), ("N3 Procedures", 2, [])], "N3 Procedures")]:
            with self.subTest(sections=secs, name=name):
                with self.assertRaises(gen_core.GenError):
                    gen_core.find(secs, name)


def _core_source_index(path):
    """Read existing Source requirement declarations, retaining their section and full text."""
    text = Path(path).read_text(encoding="utf-8")
    rows, section, current, lines, fence = {}, "", None, [], False

    def finish():
        if current is not None:
            value = "\n".join(lines).strip()
            if current in rows or not value:
                raise AssertionError("missing/duplicate Source requirement body: " + current)
            rows[current] = (section, value)

    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        anchor = re.fullmatch(r"<!-- req: (P/[0-9]+\.[0-9]+-R[0-9]+) -->", line) if not fence else None
        heading = re.match(r"^#{2,4} (.+)$", line) if not fence else None
        if anchor or heading:
            finish(); current, lines = None, []
            if heading:
                section = re.sub('^\u041d(?=[0-9])', 'N', heading[1])
            else:
                current = anchor[1]
        elif current is not None:
            lines.append(line)
    finish()
    return rows


def _core_expected_markers(root, name):
    """Independent accepted method locations; no generator selectors or rendered report."""
    indices = {chapter: _core_source_index(Path(root) / f"Platform/01-store/spec/01.{chapter}-store.norms.md")
               for chapter in (1, 2, 3)}
    explicit = {
        "Context": ("P/01.2-R006", "P/01.2-R017", "P/01.2-R018", "P/01.2-R019", "P/01.1-R050", "P/01.1-R066"),
        "Rights": ("P/01.2-R012", "P/01.2-R014", "P/01.2-R015", "P/01.3-R016"),
        "Status": ("P/01.3-R013", "P/01.3-R015", "P/01.3-R016", "P/01.3-R017"),
        "Join": ("P/01.3-R013", "P/01.3-R016", "P/01.3-R017"),
        "Leave": ("P/01.3-R013", "P/01.3-R016", "P/01.3-R017", "P/01.3-R023"),
        "Metrics": ("P/01.3-R015", "P/01.3-R016"),
        "CopyGet": ("P/01.3-R033", "P/01.3-R034"), "CopyHead": ("P/01.3-R033",),
    }
    if name in explicit:
        anchors = explicit[name]
        for anchor in anchors:
            if anchor not in indices[int(anchor.split('.')[1][0])]:
                raise AssertionError("missing Source method binding " + anchor)
        return anchors
    selectors = {"Get": ("N3 Procedures", "read("), "List": ("list(",),
                 "Write": ("write(", "delete(", "write batch(", "Admission time", "Replay by identifier", "Persistence cost"),
                 "QueryRefused": ("N2.1 Request parsing",)}
    if name not in selectors:
        raise AssertionError("unknown method binding " + name)
    selected = []
    for prefix in selectors[name]:
        values = [(anchor, body) for anchor, (head, body) in indices[1].items() if head.startswith(prefix)]
        if not values:
            raise AssertionError("missing Source method section " + prefix)
        if name == "QueryRefused":
            start = [i for i, (_, body) in enumerate(values) if body.startswith("- **Query.**")]
            if len(start) != 1:
                raise AssertionError("missing/ambiguous Source Query clause")
            begin = start[0]
            end = next((i for i in range(begin + 1, len(values)) if values[i][1].startswith("- **")), len(values))
            values = values[begin:end]
        selected.extend(anchor for anchor, _ in values)
    if len(set(selected)) != len(selected):
        raise AssertionError("ambiguous Source method binding")
    return tuple(selected)


def _core_marker_view(text):
    # Opaque literals cannot invent a function or req marker. Keep only exact machine comments.
    def visible(match):
        token = match[0]
        if re.fullmatch(r"//[ \t]*req:[ \t]*P/[0-9]+\.[0-9]+-R[0-9]+[ \t]*", token):
            return token
        return "".join("\n" if c == "\n" else " " for c in token)
    return re.sub(r'"(?:\\.|[^"\\])*"|`[^`]*`|\x27(?:\\.|[^\x27\\])*\x27|//[^\n]*|/\*.*?\*/',
                  visible, text, flags=re.S)


def _assert_core_markers(text, name, expected):
    view = _core_marker_view(text)
    matches = list(re.finditer(r"((?:^[ \t]*(?://[^\n]*)?\n)*)^func \(s \*Store\) "
                               + re.escape(name) + r"\(", view, re.M))
    if len(matches) != 1:
        raise AssertionError("missing/duplicate actual Store method " + name)
    markers = re.findall(r"//[ \t]*req:[ \t]*(P/[0-9]+\.[0-9]+-R[0-9]+)[ \t]*$", matches[0][1], re.M)
    if len(markers) != len(set(markers)) or set(markers) != set(expected):
        raise AssertionError("missing/stale/extra Source method markers: " + name)


def _assert_requirement_marker(text, identity, source):
    if not source.strip():
        raise AssertionError("empty independent Source requirement")
    markers = re.findall(r"(?m)^\s*//[ \t]*req:[ \t]*(P/[0-9]+\.[0-9]+-R[0-9]+)[ \t]*$",
                         _core_marker_view(text))
    if markers.count(identity) != 1:
        raise AssertionError("missing or stale Source requirement marker " + identity)


class CosmeticCoreControls(unittest.TestCase):
    """Synthetic Source/declaration cases; integration setups and native code are not run."""
    def test_00_id_only_markers_bind_actual_method(self):
        _assert_core_markers('// req: P/01.1-R001\nfunc (s *Store) Get(c Ctx) apidoor.Answer {}\n',
                             'Get', ['P/01.1-R001'])
        _assert_requirement_marker('// req: P/01.1-R001\n', 'P/01.1-R001', 'independent source body')

    def test_missing_stale_duplicate_extra_and_prose_only_markers(self):
        normal = '// req: P/01.1-R001\nfunc (s *Store) Get(c Ctx) apidoor.Answer {}\n'
        for wrong in (normal.replace('P/01.1-R001', 'P/01.1-R999'), normal.replace('// req:', '// prose:'),
                      '// req: P/01.1-R001\n' + normal, '// req: P/01.1-R002\n' + normal,
                      normal.replace('R001\n', 'R001 — copied prose\n')):
            with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                _assert_core_markers(wrong, 'Get', ['P/01.1-R001'])

    def test_markers_must_bind_real_unique_function(self):
        normal = '// req: P/01.1-R001\nfunc (s *Store) Get(c Ctx) apidoor.Answer {}\n'
        for wrong in ('/*' + normal + '*/', 'var fake = `' + normal + '`', normal + normal,
                      normal.replace('Get(', 'Other(')):
            with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                _assert_core_markers(wrong, 'Get', ['P/01.1-R001'])

    def test_independent_source_sections_missing_duplicate_and_query_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root / 'Platform/01-store/spec'; directory.mkdir(parents=True)
            path = directory / '01.1-store.norms.md'
            for chapter in (2, 3):
                (directory / f'01.{chapter}-store.norms.md').write_text('## N1 Form\n')
            normal = ('## N3 Procedures\n<!-- req: P/01.1-R001 -->\nintro\n'
                      '### read(key)\n<!-- req: P/01.1-R002 -->\nread body\n'
                      '## N2 Doors\n### N2.1 Request parsing\n<!-- req: P/01.1-R003 -->\n- **Query.** data\n'
                      '<!-- req: P/01.1-R004 -->\nquery continuation\n'
                      '<!-- req: P/01.1-R005 -->\n- **Body.** data\n')
            path.write_text(normal)
            self.assertEqual(_core_expected_markers(root, 'Get'), ('P/01.1-R001', 'P/01.1-R002'))
            self.assertEqual(_core_expected_markers(root, 'QueryRefused'), ('P/01.1-R003', 'P/01.1-R004'))
            for wrong in (normal.replace('### read(key)', '### foreign'), normal + '<!-- req: P/01.1-R001 -->\nduplicate\n',
                          normal.replace('- **Query.**', 'missing')):
                path.write_text(wrong)
                with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                    _core_expected_markers(root, 'QueryRefused' if 'missing' in wrong else 'Get')

    def test_requirement_markers_do_not_accept_missing_or_stale_source(self):
        for actual, source in [('// req: P/01.1-R999\n', 'body'), ('// req: P/01.1-R001\n', ''),
                               ('var fake = `// req: P/01.1-R001\n`', 'body')]:
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                _assert_requirement_marker(actual, 'P/01.1-R001', source)


class Core(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ncore-")
        cls.store = build(cls.tmp.name)
        cls.core = "".join(p.read_text(encoding="utf-8") for p in sorted((cls.store / "internal/coreadapter").glob("*.go")))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def go(self, *args):
        return subprocess.run(["go", *args], cwd=self.store, capture_output=True, text=True)

    def test_vet(self):
        done = self.go("vet", "./...")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_stub_answers(self):
        probe = self.store / "internal/coreadapter/probe_test.go"
        probe.write_text(PROBE, encoding="utf-8")
        try:
            done = self.go("test", "-count=1", "-run", "TestCoreStub", "./internal/coreadapter/")
        finally:
            probe.unlink()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_stage_tests_run_red_without_panic(self):
        done = self.go("test", "-count=1", "./internal/stagetests/")
        out = done.stdout + done.stderr
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--- FAIL", out)
        self.assertNotIn("panic:", out)
        self.assertNotIn("build failed", out)

    def test_anchors_over_methods(self):
        for name in ("Get", "List", "Write", "QueryRefused"):
            _assert_core_markers(self.core, name, _core_expected_markers(gen_core.ROOT, name))
        for name in ("Rights", "Status", "Join", "Leave", "Metrics"):
            self.assertRegex(self.core, rf"func \(s \*Store\) {name}\([^)]*\) apidoor.Answer {{\n\treturn notInStage\(")

    def test_identity_over_context(self):
        _assert_core_markers(self.core, "Context", _core_expected_markers(gen_core.ROOT, "Context"))
        self.assertRegex(self.core, r"func \(s \*Store\) Context\(call Call, header map\[string\]string\) Ctx \{\n"
                         r"\treturn &Request\{Call: call, Header: header\}\n\}")
        kit = (Path(self.tmp.name) / "KIT.md").read_text(encoding="utf-8")
        self.assertIn("**Context — the identity of the call: what to check.**", kit)

    def test_anchors_over_stubs(self):
        for name in ("Rights", "Status", "Join", "Leave", "Metrics", "CopyGet", "CopyHead"):
            _assert_core_markers(self.core, name, _core_expected_markers(gen_core.ROOT, name))
            self.assertRegex(self.core, rf"func \(s \*Store\) {name}\([^)]*\) apidoor.Answer {{\n\treturn notInStage\(apidoor.Op{name}\)")

    def test_manifest_and_doc(self):
        m = __import__("json").loads((Path(self.tmp.name) / "kit.manifest.json").read_text(encoding="utf-8"))
        own = {f["path"] for f in m["files"] if f.get("editable")}
        self.assertIn("01-store/internal/coreadapter/core.go", own)
        self.assertIn("01-store/internal/coreadapter/open.go", own)
        self.assertIn("core", m["provenance"])
        for name in ("core", "open", *(n.lower() for n in gen_core.OPS)):
            self.assertIn(f"01-store/internal/coreadapter/{name}.go", own)
        open_go = (self.store / "internal/coreadapter/open.go").read_text(encoding="utf-8")
        self.assertIn("newStore(cfg)", open_go)
        self.assertNotIn("ErrNotImplemented", open_go)
        doc = (Path(self.tmp.name) / "KIT.md").read_text(encoding="utf-8")
        self.assertIn("## Part `core`: the core stub — what to fill", doc)


def _seed_prior_machine_identity(data):
    """Make an old untouched scaffold distinct through a real machine identity field."""
    pattern = rb"(?m)^// Source: [^\r\n]+\n// sha256: ([0-9a-f]{64})$"
    match = re.search(pattern, data)
    if match is None:
        raise AssertionError("seed fixture has no machine Source/SHA identity")
    start, end = match.span(1)
    digest = data[start:end]
    changed = (b"0" if digest[:1] != b"0" else b"1") + digest[1:]
    prior = data[:start] + changed + data[end:]
    if prior == data or hashlib.sha256(prior).digest() == hashlib.sha256(data).digest():
        raise AssertionError("seed identity fixture must change actual file hash")
    return prior


class CosmeticSeedControls(unittest.TestCase):
    """Synthetic files exercise the existing Python seed rule, without build/Go setup."""
    def fixture(self):
        return (b"// Source: Platform/01-store/spec/01.2-store.norms.md\n// sha256: " + b"a" * 64
                + b"\npackage coreadapter\nfunc (s *Store) Rights(c Ctx) apidoor.Answer { return notInStage(apidoor.OpRights) }\n")

    def test_00_machine_identity_varies_hash_preserving_declarations(self):
        normal = self.fixture()
        prior = _seed_prior_machine_identity(normal)
        self.assertNotEqual(prior, normal)
        self.assertNotEqual(hashlib.sha256(prior).digest(), hashlib.sha256(normal).digest())
        self.assertEqual(prior.split(b"package coreadapter", 1)[1], normal.split(b"package coreadapter", 1)[1])
        self.assertEqual(build_kit.declarations(prior), build_kit.declarations(normal))

    def test_seed_refresh_uses_prior_hash_and_keeps_model_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); seed, dst = root / 'seed', root / 'dst'
            rel = '01-store/internal/coreadapter/rights.go'; path = seed / rel; path.parent.mkdir(parents=True)
            generated = self.fixture(); prior = _seed_prior_machine_identity(generated); path.write_bytes(prior)
            manifest = {'files': [dict(path=rel, editable=True, sha256=hashlib.sha256(prior).hexdigest())]}
            (seed / 'kit.manifest.json').write_text(json.dumps(manifest))
            taken, kept, refreshed = build_kit.seed_rule(dst, seed)
            self.assertFalse(taken(dst / rel, generated))
            self.assertEqual((kept, refreshed), ([], [rel]))
            self.assertEqual(path.read_bytes(), prior, 'classification must preserve seed bytes')
            mine = prior + b'\n// mine\n'; path.write_bytes(mine)
            taken, kept, refreshed = build_kit.seed_rule(dst, seed)
            self.assertTrue(taken(dst / rel, generated))
            self.assertEqual((kept, refreshed), ([rel], []))
            self.assertEqual(path.read_bytes(), mine)

    def test_missing_or_malformed_identity_cannot_make_noop_fixture(self):
        for wrong in (b'package coreadapter\n', self.fixture().replace(b'// sha256:', b'// digest:'),
                      self.fixture().replace(b'a' * 64, b'a' * 63)):
            with self.subTest(data=wrong), self.assertRaises(AssertionError):
                _seed_prior_machine_identity(wrong)


class Kit(unittest.TestCase):
    def test_edit_kept(self):
        with tempfile.TemporaryDirectory() as t:
            store = build(t)
            core = store / "internal/coreadapter/core.go"
            core.write_text(core.read_text(encoding="utf-8") + "\n// mine\n", encoding="utf-8")
            build_kit.build(t, MOD, PARTS)
            self.assertTrue(core.read_text(encoding="utf-8").endswith("// mine\n"))

    def test_one_operation_per_file(self):
        """Replacing one operation's whole file leaves other methods intact; one editable file per method, without DO NOT EDIT."""
        with tempfile.TemporaryDirectory() as t:
            store = build(t)
            pkg = store / "internal/coreadapter"
            for name in gen_core.OPS:
                text = (pkg / f"{name.lower()}.go").read_text(encoding="utf-8")
                self.assertEqual(re.findall(r"^func \(s \*Store\) (\w+)\(", text, re.M), [name])
                self.assertNotIn("DO NOT EDIT", text)
            before = {p.name: p.read_bytes() for p in pkg.glob("*.go") if p.name != "write.go"}
            (pkg / "write.go").write_text(
                f'package coreadapter\n\nimport "{MOD}/internal/apidoor"\n\n'
                "func (s *Store) Write(c Ctx, body []byte) apidoor.Answer { return notImplemented(apidoor.OpWrite) }\n"
                "\n// mine\n", encoding="utf-8")
            build_kit.build(t, MOD, PARTS)
            self.assertTrue((pkg / "write.go").read_text(encoding="utf-8").endswith("// mine\n"))
            self.assertEqual({p.name: p.read_bytes() for p in pkg.glob("*.go") if p.name != "write.go"}, before)
            done = subprocess.run(["go", "vet", "./internal/coreadapter/"], cwd=store, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_seed(self):
        """--seed excludes edited/moved implementation code from kit replacement, refreshes untouched prior scaffolds and keeps the overlaid seeded package buildable."""
        with tempfile.TemporaryDirectory() as t:
            seed = build(Path(t) / "seed").parent
            pkg = seed / "01-store/internal/coreadapter"
            (pkg / "core.go").write_text((pkg / "core.go").read_text(encoding="utf-8") + "\n// mine\n", encoding="utf-8")
            status = (pkg / "status.go").read_text(encoding="utf-8").split('/internal/apidoor"\n', 1)[1]
            (pkg / "status.go").unlink()
            (pkg / "get.go").write_text((pkg / "get.go").read_text(encoding="utf-8") + status, encoding="utf-8")
            old = (pkg / "rights.go").read_bytes()
            (pkg / "rights.go").write_bytes(_seed_prior_machine_identity(old))
            m = json.loads((seed / "kit.manifest.json").read_text(encoding="utf-8"))
            for f in m["files"]:
                if f["path"].endswith("coreadapter/rights.go"):
                    f["sha256"] = build_kit.sha256((pkg / "rights.go").read_bytes())
            (seed / "kit.manifest.json").write_text(json.dumps(m), encoding="utf-8")
            kit = Path(t) / "kit"
            m = build_kit.build(kit, MOD, PARTS, seed=seed)
            rel = "01-store/internal/coreadapter/"
            self.assertEqual(m["seed"]["kept"], [rel + "core.go", rel + "get.go", rel + "status.go"])
            self.assertIn(rel + "rights.go", m["seed"]["refreshed"])
            self.assertIn(rel + "join.go", m["seed"]["refreshed"])
            for n in ("core.go", "get.go", "status.go"):
                self.assertFalse((kit / rel / n).exists(), n)
            self.assertEqual((kit / rel / "rights.go").read_bytes(), old)
            shutil.copytree(kit, seed, dirs_exist_ok=True)
            self.assertTrue((pkg / "core.go").read_text(encoding="utf-8").endswith("// mine\n"))
            done = subprocess.run(["go", "vet", "./..."], cwd=seed / "01-store", capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_legacy_core_file(self):
        """For older combined cores with every method in core.go, do not install duplicate per-method stubs."""
        with tempfile.TemporaryDirectory() as t:
            store = build(t)
            pkg = store / "internal/coreadapter"
            methods = [pkg / f"{n.lower()}.go" for n in gen_core.OPS]
            merged = (pkg / "core.go").read_text(encoding="utf-8") + "".join(
                p.read_text(encoding="utf-8").split('import "example.com/w2c/store/internal/apidoor"\n', 1)[1]
                for p in methods)
            (pkg / "core.go").write_text(merged, encoding="utf-8")
            for p in methods:
                p.unlink()
            build_kit.build(t, MOD, PARTS)
            self.assertFalse(any(p.exists() for p in methods))
            done = subprocess.run(["go", "vet", "./internal/coreadapter/"], cwd=store, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_needs_parts(self):
        with tempfile.TemporaryDirectory() as t:
            for parts in (["core", "door"], ["core", "stagetests"]):
                with self.assertRaises(build_kit.KitError):
                    build_kit.build(t, MOD, parts)

    def test_stale_out(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "out"
            gen_core.generate(out)
            f = out / "core/coreadapter/core.go"
            f.write_text(f.read_text(encoding="utf-8") + "// x\n", encoding="utf-8")
            with self.assertRaises(gen_core.GenError):
                gen_core.kit_files(MOD, out)

    def test_handler_table_closed(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        door = gen_core.DOOR.read_text(encoding="utf-8")
        names = [m[0] for m in gen_core.handler_methods(door)]
        self.assertEqual(set(names), set(gen_core.OPS))
        extra = door.replace("\tMetrics(c C) Answer", "\tMetrics(c C) Answer\n\tPing(c C) Answer", 1)
        self.assertEqual(len(gen_core.handler_methods(extra)), len(names) + 1)


def z21_ready_p01(output, source_root, code_root, *, expected_manifest_sha256=None):
    """Validate the entire declared set before selecting P01; never prepare or reseal it."""
    from test_gen_machine import CheckingError
    receipt = (os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV) if expected_manifest_sha256 is None
               else expected_manifest_sha256)
    try:
        manifest = output_lesson.output_manifest(output, expected_manifest_sha256=receipt)
        kind = manifest["context"]["kind"]
        if kind == "current":
            profiles = output_lesson.PROFILES
        elif kind == "component" and manifest["profiles"] == ["p01-1"]:
            profiles = ("p01-1",)
        else:
            raise CheckingError("Z21 helpers require current full9 or an explicit P01-only component")
        return output_lesson.ready_outputs(output_root=output, source_root=source_root, code_root=code_root,
                                           profiles=profiles, expected_manifest_sha256=receipt)
    except (output_lesson.LessonError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise CheckingError(f"Z21 prepared input checking error: {exc}") from exc


class Z21PreparedContextControls(unittest.TestCase):
    """Synthetic filesystem/metadata fixtures, not generated profiles or Source-semantic execution."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="z21-context-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.serial = 0

    def fixture(self, kind="current", profiles=None):
        profiles = list(output_lesson.PROFILES if profiles is None else profiles)
        root = Path(self.temp.name) / str(self.serial)
        self.serial += 1
        output, source, code = (root / name for name in ("output", "source", "code"))
        output.mkdir(parents=True)
        def directory(base, relative):
            path = base / relative
            path.mkdir(parents=True, exist_ok=True); path.chmod(0o755)
            return {"path": relative, "type": "directory", "mode": 0o755, "bytes": 0, "sha256": None}
        def file(base, relative, data):
            path = base / relative
            path.write_bytes(data); path.chmod(0o644)
            return {"path": relative, "type": "file", "mode": 0o644, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()}
        inputs = {"source": [directory(source, "Platform"), file(source, "Platform/witness.txt", b"synthetic source")],
                  "code": [directory(code, "tools/normgen"), file(code, "tools/normgen/witness.py", b"# synthetic code\n")]}
        records = []
        for slug in dict.fromkeys(profiles):
            records += [directory(output, slug), directory(output, slug + "/go"),
                        file(output, slug + "/go/go.mod", b"module synthetic/metadata\n\ngo 1.22\n"),
                        file(output, slug + "/witness.txt", b"synthetic payload")]
        value = {"version": 1, "context": {"kind": kind}, "profiles": profiles,
                 "parts": {slug: ["door"] for slug in profiles}, "inputs": inputs,
                 "files": sorted(records, key=lambda row: row["path"])}
        # This fixture creator holds its own serialized bytes; consumers never derive their receipt from the set.
        raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
        manifest = output / output_lesson.OUTPUT_MANIFEST
        manifest.write_bytes(raw); manifest.chmod(0o600)
        return SimpleNamespace(root=root, output=output, source=source, code=code, manifest=manifest,
                               value=value, receipt=hashlib.sha256(raw).hexdigest())

    @staticmethod
    def snapshot(fixture):
        return [(p.relative_to(fixture.root).as_posix(), p.stat().st_mode & 0o777,
                 hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
                for p in sorted(fixture.root.rglob("*"))]

    def accept(self, fixture, *, receipt=None):
        before = self.snapshot(fixture)
        try:
            return z21_ready_p01(fixture.output, fixture.source, fixture.code,
                                 expected_manifest_sha256=fixture.receipt if receipt is None else receipt)
        finally:
            self.assertEqual(self.snapshot(fixture), before, "verification modified the set/inputs")

    def refuse(self, fixture, *, receipt=None):
        from test_gen_machine import CheckingError
        compared = []
        with self.assertRaises(CheckingError):
            self.accept(fixture, receipt=receipt)
            compared.append("semantic comparison reached")
        self.assertEqual(compared, [])

    def test_current_validates_all_nine_before_p01_selection(self):
        fixture = self.fixture()
        got = self.accept(fixture)
        self.assertEqual(set(got), set(output_lesson.PROFILES))
        self.assertEqual(got["p01-1"], fixture.output / "p01-1")

    def test_explicit_component_one_keeps_selected_support(self):
        fixture = self.fixture("component", ["p01-1"])
        self.assertEqual(self.accept(fixture), {"p01-1": fixture.output / "p01-1"})

    def test_partial_empty_duplicate_and_unknown_current_profiles_are_errors(self):
        for profiles in (["p01-1"], list(output_lesson.PROFILES)[:-1], [],
                         list(output_lesson.PROFILES) + ["p01-1"], list(output_lesson.PROFILES) + ["p07"]):
            with self.subTest(profiles=profiles):
                self.refuse(self.fixture("current", profiles))

    def test_component_cannot_select_foreign_or_extra_profiles(self):
        for profiles in (["p02"], ["p01-1", "p02"], list(output_lesson.PROFILES)):
            with self.subTest(profiles=profiles):
                self.refuse(self.fixture("component", profiles))

    def test_historical_export_and_unknown_contexts_are_not_adopted(self):
        for kind in ("historical", "export", "unknown", True):
            with self.subTest(kind=kind):
                self.refuse(self.fixture(kind, ["p01-1"]))

    def test_missing_malformed_wrong_receipts_and_explicit_priority(self):
        from test_gen_machine import CheckingError
        fixture = self.fixture()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(output_lesson.OUTPUT_RECEIPT_ENV, None)
            before = self.snapshot(fixture)
            with self.assertRaises(CheckingError):
                z21_ready_p01(fixture.output, fixture.source, fixture.code)
            self.assertEqual(self.snapshot(fixture), before)
        for receipt in ("", "x", "A" * 64, "0" * 64, True):
            with self.subTest(receipt=receipt):
                self.refuse(fixture, receipt=receipt)
        with patch.dict(os.environ, {output_lesson.OUTPUT_RECEIPT_ENV: "0" * 64}):
            self.assertIn("p01-1", self.accept(fixture))
        with patch.dict(os.environ, {output_lesson.OUTPUT_RECEIPT_ENV: fixture.receipt}):
            self.refuse(fixture, receipt="0" * 64)
            self.assertIn("p01-1", z21_ready_p01(fixture.output, fixture.source, fixture.code))

    def test_source_code_and_payload_changes_are_errors_without_healing(self):
        for target in ("source", "code", "payload", "missing", "extra", "mode"):
            fixture = self.fixture()
            if target == "source":
                (fixture.source / "Platform/witness.txt").write_bytes(b"changed source")
            elif target == "code":
                (fixture.code / "tools/normgen/witness.py").write_bytes(b"# changed code\n")
            else:
                path = fixture.output / "p01-1/witness.txt"
                if target == "missing": path.unlink()
                elif target == "extra": (fixture.output / "p10/extra.txt").write_bytes(b"extra")
                elif target == "mode": path.chmod(0o600)
                else: path.write_bytes(b"changed payload")
            with self.subTest(target=target):
                self.refuse(fixture)

    def test_coupled_payload_manifest_and_omission_do_not_replace_creation_identity(self):
        for omission in (False, True):
            fixture = self.fixture()
            value = copy.deepcopy(fixture.value)
            path = fixture.output / "p01-1/witness.txt"
            if omission:
                path.unlink()
                value["files"] = [r for r in value["files"] if r["path"] != "p01-1/witness.txt"]
            else:
                changed = b"changed payload"
                path.write_bytes(changed)
                record = next(r for r in value["files"] if r["path"] == "p01-1/witness.txt")
                record.update(bytes=len(changed), sha256=hashlib.sha256(changed).hexdigest())
            fixture.manifest.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
            with self.subTest(omission=omission):
                self.refuse(fixture)

    def test_teardown_held_receipt_cannot_follow_a_replaced_manifest(self):
        fixture = self.fixture()
        self.accept(fixture)
        replacement = copy.deepcopy(fixture.value)
        replacement["context"]["source_pin"] = "1" * 40
        raw = (json.dumps(replacement, sort_keys=True, indent=2) + "\n").encode()
        fixture.manifest.write_bytes(raw)
        with patch.dict(os.environ, {output_lesson.OUTPUT_RECEIPT_ENV: hashlib.sha256(raw).hexdigest()}):
            self.refuse(fixture, receipt=fixture.receipt)


def z21_source_requirement(root, chapter, identity):
    text = (root / f"Platform/01-store/spec/01.{chapter}-store.norms.md").read_text(encoding="utf-8")
    pattern = rf"<!-- req: {re.escape(identity)} -->\s*(.*?)(?=\n<!-- req:|\n#|\Z)"
    matches = re.findall(pattern, text, re.S)
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError("missing or ambiguous Source requirement " + identity)
    # These generated prose comments retain a Markdown link's label, not its URL syntax.
    paragraph = re.sub(r"\[([^\]\n]+)\]\([^\)\n]+\)", r"\1", matches[0])
    return " ".join(paragraph.replace("**", "").strip().removeprefix("- ").split())


def z21_assert_requirement_comment(text, identity, source, *, abbreviated=False):
    """Compare the Source paragraph, never a producer-selected anchor list."""
    # Remove Go comment prefixes; whitespace wrapping carries no semantic content.
    comment = " ".join(re.sub(r"^//[ \t]*", "", text, flags=re.M).split())
    wanted = source[:80] if abbreviated else source
    if f"req: {identity} — {wanted}" not in comment:
        raise AssertionError("missing or stale Source comment " + identity)


Z21_CORE_TEST = r'''package coreadapter
import (
    "testing"
    "normgen/p01-1/apidoor"
)
var _ Core = (*Store)(nil)
type z21Core struct{*Store; brokenHead bool}
func (s z21Core) CopyHead(Ctx) apidoor.Answer {if s.brokenHead{return apidoor.Answer{Code:299}};return apidoor.Answer{Code:$HEADCODE,Allow:true}}
func TestZ21CoreCopyStubs(t *testing.T) {
    s:=&Store{}
    for _,p:=range []struct{op apidoor.Op;a apidoor.Answer}{{apidoor.OpCopyGet,s.CopyGet(nil)},{apidoor.OpCopyHead,s.CopyHead(nil)}} {
        r,err:=apidoor.Encode(p.op,p.a)
        if err!=nil || r.Code!=503 {t.Fatalf("existing not-in-stage stub: %v %v",r,err)}
        if p.op==apidoor.OpCopyHead && len(r.Body)!=0{t.Fatal("HEAD stub has a body")}
    }
}
func TestZ21HeadDispatchProjection(t *testing.T) {
    c:=z21Core{Store:&Store{}}
    code,h,body:=Handle(c,Config{BodyLimit:16},Call{Sock:"admin"},"HEAD","/v1/copy",nil,nil)
    if code!=$HEADCODE || h["Allow"]!=$ALLOW || len(body)!=0 {t.Fatalf("HEAD projection: %d %v %q",code,h,body)}
    context:=c.Context(Call{Sock:"admin"},map[string]string{"X-Test":"é"})
    if context.Call.Sock!="admin" || context.Header["X-Test"]!="é" {t.Fatal("context identity changed")}
}
func TestZ21HeadEarlyAndErrorProjection(t *testing.T) {
    for _,p:=range []struct{c z21Core;target string;body []byte;code int}{
        {z21Core{Store:&Store{}},"/v1/copy",[]byte("oversize"),413},
        {z21Core{Store:&Store{}},"/absent",nil,404},
        {z21Core{Store:&Store{},brokenHead:true},"/v1/copy",nil,500},
    } {
        code,_,body:=Handle(p.c,Config{BodyLimit:1},Call{Sock:"admin"},"HEAD",p.target,nil,p.body)
        if code!=p.code || len(body)!=0 {t.Fatalf("existing adapter branch: %d %q",code,body)}
    }
}
func TestZ21GetIsNotHeadProjection(t *testing.T) {
    code,_,body:=Handle(&Store{},Config{BodyLimit:16},Call{Sock:"admin"},"GET","/v1/copy",nil,nil)
    if code!=503 || len(body)==0 {t.Fatalf("GET stub was changed by HEAD projection: %d %q",code,body)}
}
'''


class Z21CoreSource(unittest.TestCase):
    source_root = HERE.parent.parent
    code_root = HERE.parent.parent
    go_names = ["TestZ21CoreCopyStubs", "TestZ21HeadDispatchProjection", "TestZ21HeadEarlyAndErrorProjection",
                "TestZ21GetIsNotHeadProjection"]

    @classmethod
    def setUpClass(cls):
        cls.output = output_lesson.output_root()
        cls.output_receipt = os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV)
        cls.ready = z21_ready_p01(cls.output, cls.source_root, cls.code_root,
                                 expected_manifest_sha256=cls.output_receipt)
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-core-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        z21_ready_p01(cls.output, cls.source_root, cls.code_root, expected_manifest_sha256=cls.output_receipt)

    def test_actual_source_comments_and_missing_stale_neighbours(self):
        for file, chapter, identity, short in (("copyget", 3, "P/01.3-R033", False),
                ("copyget", 3, "P/01.3-R034", False), ("copyhead", 3, "P/01.3-R033", False),
                ("write", 1, "P/01.1-R148", True), ("frame", 1, "P/01.1-R147", False)):
            source = z21_source_requirement(self.source_root, chapter, identity)
            relative = "go/frame/frame.go" if file == "frame" else f"core/coreadapter/{file}.go"
            text = (self.ready["p01-1"] / relative).read_text()
            _assert_requirement_marker(text, identity, source)
            with self.subTest(file=file, identity=identity):
                for changed in (text.replace(identity, "P/00.0-R000"),
                                re.sub(r"(?m)^\s*// req: " + re.escape(identity) + r"[ \t]*$", "", text)):
                    self.assertNotEqual(changed, text)
                    with self.assertRaises(AssertionError):
                        _assert_requirement_marker(changed, identity, source)

    def module(self, name):
        import yaml
        path = Path(self.tmp.name) / name
        shutil.copytree(self.ready["p01-1"] / "go", path)
        # Explicitly overlay the generated editable scaffolds in this owned module only.
        for item in (self.ready["p01-1"] / "core/coreadapter").glob("*.go"):
            shutil.copy(item, path / "coreadapter" / item.name)
        api = yaml.safe_load((self.source_root / "Platform/01-store/spec/01-store.api.openapi.yaml").read_text())
        head = api["paths"]["/v1/copy"]["head"]["responses"]
        self.assertNotIn("content", head["405"])
        self.assertTrue(head["405"]["headers"]["Allow"]["required"])
        allow = head["405"]["headers"]["Allow"]["schema"]["const"]
        test = Z21_CORE_TEST.replace("$HEADCODE", str(int("405"))).replace("$ALLOW", json.dumps(allow))
        (path / "coreadapter/z21_copy_test.go").write_text(test, encoding="utf-8")
        return path

    def run_module(self, module):
        from test_gen_machine import CheckingError, complete_go_tests
        try:
            done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^(" + "|".join(self.go_names) + ")$",
                                   "./coreadapter"], cwd=module, capture_output=True, timeout=120)
            observed = SimpleNamespace(returncode=done.returncode, stdout=done.stdout.decode("utf-8", "strict"),
                                       stderr=done.stderr.decode("utf-8", "strict"))
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise CheckingError("cannot obtain complete core-adapter report") from exc
        return complete_go_tests(observed, self.go_names, "normgen/p01-1/coreadapter")

    def test_compiled_scaffold_and_all_existing_head_projection_branches(self):
        self.assertEqual(self.run_module(self.module("normal")), [])

    def test_valid_adapter_and_copy_operation_mutants_need_named_failures(self):
        self.assertEqual(self.run_module(self.module("mutant-baseline")), [])
        cases = (("head-body", "coreadapter/coreadapter.go", 'if method == "HEAD" {', 'if method == "not-HEAD" {',
                  "TestZ21HeadEarlyAndErrorProjection"),
                 ("head-op", "coreadapter/copyhead.go", "return notInStage(apidoor.OpCopyHead)",
                  "return notInStage(apidoor.OpCopyGet)", "TestZ21CoreCopyStubs"),
                 ("get-op", "coreadapter/copyget.go", "return notInStage(apidoor.OpCopyGet)",
                  "return notInStage(apidoor.OpCopyHead)", "TestZ21CoreCopyStubs"))
        for name, file, before, after, killed_by in cases:
            with self.subTest(mutant=name):
                module = self.module(name)
                path = module / file
                text = path.read_text()
                self.assertEqual(text.count(before), 1)
                path.write_text(text.replace(before, after), encoding="utf-8")
                self.assertIn(killed_by, self.run_module(module), "surviving compiled mutant " + name)


if __name__ == "__main__":
    unittest.main()
