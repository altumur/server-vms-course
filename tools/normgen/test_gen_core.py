"""Тесты части core (ADR-0083 доп. (95) п. 3, тот же принцип): gen_core.py — заготовка ядра, редактируемая моделью.

Пакет со всеми частями собирается и проходит go vet; Open части core возвращает Store; Store — coreadapter.Core:
Get — пустое хранилище (этап launch остаётся закрытым пакетом), Write/List — 503 «not implemented», Rights и главы
1.3 — 503 «not in this stage»; тесты этапов идут и красные без паники; над каждым методом главы 1.1 — путь Н3 и
якоря req; правка ядра не перетирается пересборкой; часть core без door или stagetests и устаревший выход — отказ.
Только Linux (CT 103), Go 1.22."""
import re
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
        cls.core = (cls.store / "internal/coreadapter/core.go").read_text(encoding="utf-8")

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

    def test_manifest_and_doc(self):
        m = __import__("json").loads((Path(self.tmp.name) / "kit.manifest.json").read_text(encoding="utf-8"))
        own = {f["path"] for f in m["files"] if f.get("editable")}
        self.assertIn("01-store/internal/coreadapter/core.go", own)
        self.assertIn("01-store/internal/coreadapter/open.go", own)
        self.assertIn("core", m["provenance"])
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
