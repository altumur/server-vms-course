"""Test P/02 gen_vectors freshness, scaffold failures without panic except kit-executed family-read, fixture answers from expanded wire, and table-specific code/value/raw/ring-word/layer1 mutants. journal/modes.tsv stays excluded."""
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
ENV = dict(os.environ, NORMGEN_LESSON="02-installer")
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def gv():
    sys.path.insert(0, str(HERE))
    os.environ["NORMGEN_LESSON"] = "02-installer"
    import importlib
    import lesson
    lesson.CURRENT = lesson.get("02-installer")
    import gen_vectors
    return importlib.reload(gen_vectors)


def fake_go(mut=None):
    """Fixture adapter maps each package function's table/input to its row answer."""
    g = gv()
    decls, _ = g.plan(ROOT)
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    out = ['package vectoradapter', '', 'import (', '\t"encoding/json"', '\t"sort"', '\t"strings"', ')', '',
           'var _ = sort.Strings', 'var _ = strings.Join', '', 'func val(s string) any {', '\tvar v any',
           '\t_ = json.Unmarshal([]byte(s), &v)', '\treturn v', '}', '',
           'func key(table string, cells map[string]string) string {', '\tks := []string{}',
           '\tfor k := range cells {', '\t\tks = append(ks, k+"="+cells[k])', '\t}', '\tsort.Strings(ks)',
           '\treturn table + "|" + strings.Join(ks, "\\x00")', '}', '']
    for fn, ds in by_fn.items():
        ds = [x for x in ds if not x.get("per_list")]
        d = ds[0]
        entries = []
        import wire
        runs, _ = wire.expand(ROOT, "02-installer")
        for dd in ds:
            selected = [r for r in runs if r.binding.key == tuple(dd[k] for k in ("package", "table", "surface"))]
            for r in selected:
                import wire_fakes
                code, value, raw = r.code, wire_fakes.native_value(r), None
                if isinstance(value, bytes):
                    value, raw = None, value
                if dd["surface"] == "vectors":
                    k = dd["table"] + "|" + "\x00".join(sorted(f"{a}={b}" for a, b in r.cells.items()))
                elif dd["args"] == "source":
                    k = Path(r.arg_path).name
                elif dd["args"] == "none":
                    k = ""
                else:
                    k = r.arg.decode("utf-8")
                if mut and mut[0] == dd["table"] and mut[1] == dd["package"] and r is selected[0]:
                    code, value, raw = mut[2](code, value, raw)
                entries.append((k, code, json.dumps(value, ensure_ascii=False), raw))
        table = ",\n".join(f"\t{g.gstr(k)}: {{Code: {c}, Value: val({g.gstr(v)})"
                           + (f", Raw: []byte({g.go_bytes(raw)})" if raw is not None else "") + "}"
                           for k, c, v, raw in entries)
        out.append(f"var answers{fn} = map[string]Answer{{\n{table},\n}}\n")
        if d["args"] == "cells":
            out.append(f"func {fn}(table string, cells map[string]string, files map[string][]byte) Answer {{\n"
                       f"\treturn answers{fn}[key(table, cells)]\n}}\n")
        elif d["args"] == "source":
            out.append(f"func {fn}(source string, text []byte) Answer {{\n\treturn answers{fn}[source]\n}}\n")
        elif d["args"] == "none":
            out.append(f"func {fn}() Answer {{\n\treturn answers{fn}[\"\"]\n}}\n")
        else:
            out.append(f"func {fn}(input []byte) Answer {{\n\treturn answers{fn}[string(input)]\n}}\n")
    return "\n".join(out), list(by_fn)


def results(mod):
    done = subprocess.run(["go", "test", "-count=1", "-json", "./vectortests/"], cwd=mod, capture_output=True, text=True,
                          env=GOENV)
    res, panics = {}, 0
    for line in done.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") == "output" and "panic:" in e.get("Output", ""):
            panics += 1
        if e.get("Test") and e["Action"] in ("pass", "fail"):
            res[e["Test"]] = e["Action"]
    return res, panics, done


@unittest.skipUnless((ROOT / "Platform/02-installer/vectors/exec/cases.tsv").is_file(), "no P/02 vectors")
class Vectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="vecp02-")
        cls.out = Path(cls.tmp.name) / "out"
        for gen in ("gen_families.py", "gen_vectors.py"):
            done = subprocess.run([sys.executable, str(HERE / gen)] + (["02"] if gen == "gen_families.py" else []) +
                                  [str(cls.out)], capture_output=True, text=True, env=ENV)
            assert done.returncode == 0, done.stderr
        cls.mod = cls.out / "go"
        import wire
        cls.expected_count = len(wire.expand(ROOT, "02-installer")[0])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fake(self, mut=None):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        text, fns = fake_go(mut)
        for fn in fns:
            (t / "go/vectoradapter" / f"{fn.lower()}.go").unlink()
        (t / "go/vectoradapter/fake.go").write_text(text, encoding="utf-8")
        return t / "go"

    def test_out_fresh(self):
        for rel in ("vectorcmd/vectorcmd.go", "vectortests/helpers_test.go", "vectortests/exec_cases_test.go",
                    "vectoradapter/vectoradapter.go", "vectortests/inventory.tsv"):
            self.assertEqual((self.mod / rel).read_bytes(), (HERE / "out/p02/go" / rel).read_bytes(), rel)

    def test_inventory(self):
        inv = (self.mod / "vectortests/inventory.tsv").read_text(encoding="utf-8")
        self.assertIn("common/journal modes.tsv\texcluded: a layout test", inv)

    def test_stub_red(self):
        res, panics, done = results(self.mod)
        self.assertEqual(len(res), self.expected_count, done.stdout[-2000:] + done.stderr)
        self.assertEqual(panics, 0)
        red = {n.rsplit("_", 1)[0] for n, a in res.items() if a == "fail"}
        green = {n.rsplit("_", 1)[0] for n, a in res.items() if a == "pass"}
        self.assertEqual(green, {"TestCommonFamilyRead"})
        self.assertIn("TestYamlSuite_Expect", red)

    def test_fake_green(self):
        mod = self.fake()
        res, _, done = results(mod)
        self.assertEqual(len(res), self.expected_count, done.stdout[-2000:] + done.stderr)
        bad = {n for n, a in res.items() if a != "pass" and not n.startswith("TestCommon")}
        self.assertEqual(bad, set(), done.stdout[-2000:])

    def test_mutants(self):
        for table, pkg, f, test in (
                ("cases.tsv", "02-installer/exec", lambda c, v, r: (c, {"result": "refused"} if v != {"result": "refused"}
                                                                    else {"result": "ok", "argv": []}, r), "TestExec_Cases"),
                ("cases.tsv", "02-installer/canonical", lambda c, v, r: (c, v, (r or b"") + b"\n"), "TestCanonical_Cases"),
                ("cases.tsv", "common/loopback", lambda c, v, r: (0 if c == 2 else 2, None if c == 0 else "ip", r),
                 "TestLoopback_Cases"),
                ("ring.tsv", "common/sealing", lambda c, v, r: (c, "unreadable!", r), "TestSealing_Ring"),
                ("expect.tsv", "common/yaml-suite", lambda c, v, r: (c, {"layer1": "x"}, r), "TestYamlSuite_Expect")):
            res, _, done = results(self.fake((table, pkg, f)))
            self.assertEqual(len(res), self.expected_count, done.stdout[-2000:] + done.stderr)
            red = {n for n, a in res.items() if a == "fail" and not n.startswith("TestCommon")}
            self.assertTrue(red and all(n.startswith(test) for n in red), f"mutant {pkg} {table}: red {sorted(red)[:5]}")


if __name__ == "__main__":
    unittest.main()
