"""Тесты части core (ADR-0083 доп. (95) п. 3, тот же принцип): gen_core.py — заготовка ядра, редактируемая моделью.

Пакет со всеми частями собирается и проходит go vet; Open части core возвращает Store; Store — coreadapter.Core:
Get — пустое хранилище (этап launch остаётся закрытым пакетом), Write/List — 503 «not implemented», Rights и главы
1.3 — 503 «not in this stage»; тесты этапов идут и красные без паники; над каждым методом главы 1.1 — путь Н3 и
якоря req; правка ядра не перетирается пересборкой; часть core без door или stagetests и устаревший выход — отказ.
Только Linux (CT 103), Go 1.22."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import build_kit  # noqa: E402
import gen_core  # noqa: E402

MOD = "example.com/w2c/store"
PARTS = ["door", "flags", "refusals", "vectors", "stagetests", "launch", "core"]

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
                               ("QueryRefused", ["Н2.1 Request parsing"])):
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
        """Над Context — места личности (якоря P/01.2 Н1.1, Н3 «check», P/01.1 Н2.1, «list»), порядок, заголовок, строки
        refusals.tsv; тело Context — прежнее (не код решения)."""
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
        """Над заглушками глав 1.2/1.3 — места норм (STUBS) и строки refusals.tsv двери; тело — notInStage."""
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
        """Правка одной операции файлом целиком не задевает другие; файлы — по методу, без DO NOT EDIT."""
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
        """--seed: код модели посева (правленый editable, перенесённый метод) в пакет не идёт; нетронутая заглушка
        прежнего пакета обновляется; посев с пакетом поверх (как копирует цикл) собирается."""
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
        """Пакет до разнесения: все методы в core.go — заглушки по файлам не кладутся (двойного объявления нет)."""
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
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "out"
            gen_core.generate(out)
            f = out / "core/coreadapter/core.go"
            f.write_text(f.read_text(encoding="utf-8") + "// x\n", encoding="utf-8")
            with self.assertRaises(gen_core.GenError):
                gen_core.kit_files(MOD, out)

    def test_handler_table_closed(self):
        door = gen_core.DOOR.read_text(encoding="utf-8")
        names = [m[0] for m in gen_core.handler_methods(door)]
        self.assertEqual(set(names), set(gen_core.OPS))
        extra = door.replace("\tMetrics(c C) Answer", "\tMetrics(c C) Answer\n\tPing(c C) Answer", 1)
        self.assertEqual(len(gen_core.handler_methods(extra)), len(names) + 1)


if __name__ == "__main__":
    unittest.main()
