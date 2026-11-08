"""Test editable gen_core scaffolds (ADR-0083 addendum 95, item 3). All-part kits must compile/vet; Open returns Store implementing coreadapter.Core. Get keeps the empty-store launch behavior; Write/List return503 not implemented; Rights/chapter 1.3 return503 not in this stage. Stage tests fail without panic. Verify N3/req comments, seed preservation, required door/stagetests and stale-output refusal. Linux CT103, Go 1.22 only."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
        norms = gen_core.NORMS.read_text(encoding="utf-8")
        for name, sections in (("Get", ["read("]), ("List", ["list("]),
                               ("Write", ["write(", "delete(", "write batch(", "Admission time", "Replay by identifier"]),
                               ("QueryRefused", ["N2.1 Request parsing"])):
            m = re.search(rf"((?://.*\n)+)func \(s \*Store\) {name}\(", self.core)
            self.assertTrue(m, name)
            doc = m[1]
            for sec in sections:
                self.assertIn(f"«{sec}", doc, name)
            anchors = re.findall(r"req: (P/01\.1-R\d+)", doc)
            self.assertTrue(anchors, name)
            for a in anchors:
                self.assertIn(f"<!-- req: {a} -->", norms)
        write = re.search(r"((?://.*\n)+)func \(s \*Store\) Write\(", self.core)[1]
        for a in ("P/01.1-R072", "P/01.1-R099", "P/01.1-R117", "P/01.1-R068", "P/01.1-R141"):
            self.assertIn(a, write)
        for name in ("Rights", "Status", "Join", "Leave", "Metrics"):
            self.assertRegex(self.core, rf"func \(s \*Store\) {name}\([^)]*\) apidoor.Answer {{\n\treturn notInStage\(")

    def test_identity_over_context(self):
        """Context comments bind identity anchors from P/01.2 N1.1/check, P/01.1 parsing/list, ordering, header and refusals; Context's body is unchanged, not a solution."""
        m = re.search(r"((?://.*\n)+)func \(s \*Store\) Context\(call Call, header map\[string\]string\) Ctx \{\n"
                      r"\treturn &Request\{Call: call, Header: header\}\n\}", self.core)
        self.assertTrue(m)
        doc = m[1]
        texts = {}
        for path, _, anchor, _ in gen_core.IDENTITY:
            self.assertIn(f"req: {anchor} — ", doc)
            texts.setdefault(path, path.read_text(encoding="utf-8"))
            self.assertIn(f"<!-- req: {anchor} -->", texts[path])
        for want in ("403 with the role of the socket", "return `403` before the body is parsed",
                     "«frame → route → identity → body»", "P/01.3-07", "X-Configstore-Role",
                     "1.2 row 7 role_header — 403 forbidden", "refusals.RoleHeader", "1.1 row 4 identity",
                     "QueryRefused too"):
            self.assertIn(want, doc)
        kit = (Path(self.tmp.name) / "KIT.md").read_text(encoding="utf-8")
        self.assertIn("**Context — the identity of the call: what to check.**", kit)

    def test_anchors_over_stubs(self):
        """Chapter1.2/1.3 stub comments include STUBS norm locations and door refusal rows; bodies remain notInStage."""
        texts = {}
        for name, refs in gen_core.STUBS.items():
            m = re.search(rf"((?://.*\n)+)func \(s \*Store\) {name}\(", self.core)
            self.assertTrue(m, name)
            doc = m[1]
            for path, anchor, sel in refs:
                self.assertIn(f"req: {anchor} — ", doc, name)
                texts.setdefault(path, path.read_text(encoding="utf-8"))
                self.assertIn(f"<!-- req: {anchor} -->", texts[path])
                if sel and sel.startswith("door:"):
                    self.assertIn(f"{anchor} — {sel[5:]}: ", doc, name)
            for r in gen_core.STUB_REFUSALS[name]:
                self.assertIn(f" {r} — ", doc, name)
            self.assertIn("Identity first", doc)
        rights = re.search(r"((?://.*\n)+)func \(s \*Store\) Rights\(", self.core)[1]
        for want in ("`404 badrequest`", "Access is checked by the identity admin", "refusals.RightsNotAdmin"):
            self.assertIn(want, rights)
        leave = re.search(r"((?://.*\n)+)func \(s \*Store\) Leave\(", self.core)[1]
        self.assertIn("«the last voter»", leave)
        self.assertIn("identity (403) → body and membership (400, 409)", leave)

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
            (pkg / "rights.go").write_bytes(old.replace(b"By the norms:", b"By the norms (old kit):"))
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
        cls.ready = output_lesson.ready_outputs(output_root=cls.output, source_root=cls.source_root,
                                                code_root=cls.code_root, profiles=("p01-1",))
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-core-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        output_lesson.ready_outputs(output_root=cls.output, source_root=cls.source_root,
                                    code_root=cls.code_root, profiles=("p01-1",))

    def test_actual_source_comments_and_missing_stale_neighbours(self):
        for file, chapter, identity, short in (("copyget", 3, "P/01.3-R033", False),
                ("copyget", 3, "P/01.3-R034", False), ("copyhead", 3, "P/01.3-R033", False),
                ("write", 1, "P/01.1-R148", True), ("frame", 1, "P/01.1-R147", False)):
            relative = "go/frame/frame.go" if file == "frame" else f"core/coreadapter/{file}.go"
            text = (self.ready["p01-1"] / relative).read_text()
            source = z21_source_requirement(self.source_root, chapter, identity)
            z21_assert_requirement_comment(text, identity, source, abbreviated=short)
            with self.subTest(file=file, identity=identity):
                for changed in (text.replace(identity, "P/00.0-R000"), text.replace(source[:30], "stale source", 1)):
                    self.assertNotEqual(changed, text)
                    with self.assertRaises(AssertionError):
                        z21_assert_requirement_comment(changed, identity, source, abbreviated=short)

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
