"""Judge the P/02 loader and canonical view against lesson data. With Go 1.22 and cached pinned modules, no network, require fresh manifest files/module requirements/sums and vet. Check947 verdicts and text/form/relations classes, 220exact canonical bytes and402yaml-suite layer1 outcomes. Each runtime mutant must disagree with data. The corpus cannot distinguish extra empty-value refusal, layer2 normalization4.0->4 (JCS/text bytes coincide), or x-opaque projection with no nested defaults; preserve V7 rules despite those equivalent mutants."""
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
sys.path.insert(0, str(HERE))
os.environ.setdefault("NORMGEN_LESSON", "02-installer")
import gen_manifest  # noqa: E402

OUT = gen_manifest.DEFAULT_OUT / "go"
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off")

HARNESS = r'''package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"%(module)s/manifest"
)

func tsv(p string) [][]string {
	b, err := os.ReadFile(p)
	if err != nil {
		panic(err)
	}
	var out [][]string
	for _, l := range strings.Split(string(b), "\n") {
		if l == "" || strings.HasPrefix(l, "#") {
			continue
		}
		out = append(out, strings.Split(l, "\t"))
	}
	return out
}

func main() {
	root := os.Args[1]
	acc := filepath.Join(root, "Platform/02-installer/acceptance/1")
	classes := map[string]string{}
	for _, r := range tsv(filepath.Join(acc, "classes.tsv")) {
		classes[r[0]] = r[1]
	}
	n, ok, cl := 0, 0, 0
	for _, r := range tsv(filepath.Join(acc, "verdicts.tsv")) {
		if r[0] == "case" {
			continue
		}
		n++
		data, err := os.ReadFile(filepath.Join(acc, "cases", r[0]+".subsystem.yaml"))
		if err != nil {
			panic(err)
		}
		_, ref := manifest.Load(r[0]+".subsystem.yaml", data)
		got := "ok"
		if ref != nil {
			got = "refused"
		}
		switch {
		case got != r[1]:
			msg := ""
			if ref != nil {
				msg = ref.Message
			}
			fmt.Printf("BAD verdict %%s: want %%s, got %%s %%s\n", r[0], r[1], got, msg)
		case ref != nil && classes[r[0]] != "" && ref.Class != classes[r[0]]:
			fmt.Printf("BAD class %%s: want %%s, got %%s %%s\n", r[0], classes[r[0]], ref.Class, ref.Message)
		default:
			ok++
			if classes[r[0]] != "" {
				cl++
			}
		}
	}
	fmt.Printf("SUM verdicts %%d %%d classes %%d\n", ok, n, cl)
	vec := filepath.Join(root, "Platform/02-installer/vectors/canonical")
	cn, cok := 0, 0
	for _, r := range tsv(filepath.Join(vec, "cases.tsv")) {
		if r[0] == "case" {
			continue
		}
		cn++
		data, _ := os.ReadFile(filepath.Join(root, r[1]))
		want, _ := os.ReadFile(filepath.Join(vec, r[2]))
		got, ref := manifest.Canonical(filepath.Base(r[1]), data)
		if ref == nil && bytes.Equal(got, want) {
			cok++
		} else if ref != nil {
			fmt.Printf("BAD canonical %%s: refused %%s\n", r[0], ref.Message)
		} else {
			fmt.Printf("BAD canonical %%s: bytes differ\n", r[0])
		}
	}
	fmt.Printf("SUM canonical %%d %%d\n", cok, cn)
	yd := filepath.Join(root, "Platform/common/vectors/yaml-suite")
	yn, yok := 0, 0
	for _, r := range tsv(filepath.Join(yd, "expect.tsv")) {
		if r[0] == "id" {
			continue
		}
		yn++
		data, err := os.ReadFile(filepath.Join(yd, "inputs", r[0]+".yaml"))
		if err != nil {
			panic(err)
		}
		_, _, refused := manifest.Layer1(data)
		got := "ok"
		if refused {
			got = "refused"
		}
		if got == r[2] {
			yok++
		} else {
			fmt.Printf("BAD yaml-suite %%s: want %%s, got %%s\n", r[0], r[2], got)
		}
	}
	fmt.Printf("SUM yaml-suite %%d %%d\n", yok, yn)
}
'''


def run(mod_dir):
    (mod_dir / "cmd/manifestjudge").mkdir(parents=True, exist_ok=True)
    (mod_dir / "cmd/manifestjudge/main.go").write_text(HARNESS % {"module": gen_manifest.L.go_module})
    p = subprocess.run(["go", "run", "./cmd/manifestjudge", str(ROOT)], cwd=mod_dir, capture_output=True, text=True,
                       env=ENV, timeout=1800)
    if p.returncode:
        return None, [p.stderr[-2000:]]
    sums = {ln.split()[1]: ln.split()[2:] for ln in p.stdout.split("\n") if ln.startswith("SUM ")}
    bad = [ln for ln in p.stdout.split("\n") if ln.startswith("BAD ")]
    return sums, bad


class Loader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("go") is None:
            raise unittest.SkipTest("no go")
        try:
            cls.files = gen_manifest.render()
        except gen_manifest.GenError as exc:
            raise unittest.SkipTest(f"the forms are refused by the generator: {exc}")
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-manifest-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy(self, name):
        d = self.tmp / name
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        shutil.copytree(OUT / "manifest", d / "manifest")
        for f in ("go.mod", "go.sum"):
            shutil.copy(OUT / f, d / f)
        return d

    def test_fresh_and_vet(self):
        for relp, data in self.files.items():
            self.assertEqual((OUT / relp).read_bytes(), data, f"{relp} is stale: run gen_manifest.py")
        mod, s = gen_manifest.go_mod(gen_manifest.DEFAULT_OUT)
        self.assertEqual((OUT / "go.mod").read_bytes(), mod)
        self.assertEqual((OUT / "go.sum").read_bytes(), s)
        v = subprocess.run(["go", "vet", "./manifest/"], cwd=OUT, capture_output=True, text=True, env=ENV)
        self.assertEqual(v.returncode, 0, v.stderr)

    def test_corpus(self):
        sums, bad = run(self.copy("clean"))
        self.assertIsNotNone(sums, bad)
        self.assertEqual(bad, [])
        for k, (got, total) in ((k, v[:2]) for k, v in sums.items()):
            self.assertEqual(got, total, k)
        self.assertEqual(int(sums["verdicts"][1]), 947)
        self.assertEqual(int(sums["canonical"][1]), 220)
        self.assertEqual(int(sums["yaml-suite"][1]), 402)

    def test_pending_reserved_rows_and_table_witnesses(self):
        """Both accepted P04 witnesses must fail in the ordinary loader's form layer."""
        names = {"s46-loader-reserved-pending-rows", "s47-loader-reserved-pending-table"}
        cases = []
        seams = ROOT / "Platform/04-controller/acceptance/seams.tsv"
        for line in seams.read_text(encoding="utf-8").split("\n"):
            cells = line.split("\t")
            if cells[0] in names:
                self.assertTrue(cells[2].startswith("CALL controller-pass "))
                data = json.loads(cells[2].split(" ", 2)[2])
                cases.append({"source": cells[0] + ".yaml", "yaml": data["manifest_yaml"]})
        self.assertEqual({row["source"] for row in cases}, {name + ".yaml" for name in names})
        self.assertEqual(len(cases), 2)
        mod = self.copy("reserved-pending")
        (mod / "witnesses.json").write_text(json.dumps(cases), encoding="utf-8")
        cmd = mod / "cmd/reservedprobe"
        cmd.mkdir(parents=True)
        (cmd / "main.go").write_text(r'''package main
import (
    "encoding/json"
    "fmt"
    "os"
    "strings"
    "MODULE/manifest"
)
func main() {
    data, err := os.ReadFile(os.Args[1]); if err != nil { panic(err) }
    var cases []struct{ Source, Yaml string }
    if err := json.Unmarshal(data, &cases); err != nil { panic(err) }
    bad := false
    for _, c := range cases {
        _, refusal := manifest.Load(c.Source, []byte(c.Yaml))
        if refusal == nil || refusal.Class != "form" || !strings.Contains(refusal.Message, c.Source) {
            fmt.Printf("FAIL %s: %+v\n", c.Source, refusal); bad = true
        } else { fmt.Printf("PASS %s\n", c.Source) }
    }
    if bad { os.Exit(1) }
}
'''.replace("MODULE", gen_manifest.L.go_module), encoding="utf-8")
        done = subprocess.run(["go", "run", "./cmd/reservedprobe", "witnesses.json"], cwd=mod,
                              capture_output=True, text=True, env=ENV)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(set(done.stdout.splitlines()), {"PASS " + c["source"] for c in cases})

    def test_p06_numeric_supplement(self):
        import tsv_input

        roster = ROOT / "Platform/06-console/forms/numeric-loader.cases.tsv"
        if not roster.is_file():
            self.skipTest("this source has no P06 numeric-loader supplement")
        rows = tsv_input.read(roster, names=("case", "input", "expect", "relation", "norm"), root=ROOT).rows
        self.assertEqual(len(rows), 9)
        self.assertEqual(sum(row["expect"] == "ok" for _, row in rows), 5)
        cases = []
        paths = {roster}
        for _, row in rows:
            self.assertIn(row["expect"], ("ok", "refused:relations"))
            self.assertIn(row["relation"], ("160", "161", "162") if row["expect"] != "ok" else ("-",))
            path = roster.parent / row["input"]
            paths.add(path)
            cases.append({"Case": row["case"], "Source": path.relative_to(ROOT).as_posix(),
                          "Text": path.read_bytes().decode("utf-8"), "Expect": row["expect"],
                          "Rule": int(row["relation"]) if row["relation"] != "-" else 0})
        mod = self.copy("numeric-supplement")
        (mod / "witnesses.json").write_text(json.dumps(cases), encoding="utf-8")
        cmd = mod / "cmd/numericprobe"
        cmd.mkdir(parents=True)
        (cmd / "main.go").write_text(r'''package main
import (
    "encoding/json"
    "fmt"
    "os"
    "strings"
    "MODULE/manifest"
)
func main() {
    data, err := os.ReadFile(os.Args[1]); if err != nil { panic(err) }
    var cases []struct { Case, Source, Text, Expect string; Rule int }
    if err := json.Unmarshal(data, &cases); err != nil { panic(err) }
    bad := false
    for _, c := range cases {
        loaded, refusal := manifest.Load(c.Source, []byte(c.Text))
        ok := loaded != nil && refusal == nil
        if c.Expect == "refused:relations" {
            ok = loaded == nil && refusal != nil && refusal.Class == "relations" && refusal.Row == c.Rule &&
                 strings.Contains(refusal.Message, c.Source)
        }
        if !ok { fmt.Printf("FAIL %s: %+v\n", c.Case, refusal); bad = true
        } else { fmt.Printf("PASS %s\n", c.Case) }
    }
    if bad { os.Exit(1) }
}
'''.replace("MODULE", gen_manifest.L.go_module), encoding="utf-8")
        done = subprocess.run(["go", "run", "./cmd/numericprobe", "witnesses.json"], cwd=mod,
                              capture_output=True, text=True, env=ENV)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(set(done.stdout.splitlines()), {"PASS " + c["Case"] for c in cases})
        provenance_paths = {ROOT / entry["path"] for entry in gen_manifest.provenance()["judge_inputs"]}
        self.assertTrue(paths <= provenance_paths)

    def test_mutants(self):
        mutants = [
            ("manifest.go", "if len(numbers) > 0 {", "if false {"),
            ("manifest.go", "if len(got) > 0 {", "if false {"),
            ("view.go", "\tsugar(t)\n", "\n"),
            ("view.go", "if _, ok := o.M[\"snapshot\"]; !ok {", "if false {"),
            ("view.go", "setDefault(j, \"deleted\", k+\".deleted\")", ""),
            ("view.go", "if _, has := d.M[\"form\"]; !has {", "if false {"),
            ("view.go", "\t\tsetDefault(f, \"default\", nil)\n", "\n"),
            ("view.go", "setDefault(e, \"decoded\", true)", ""),
            ("view.go", "if ordered && truthy(chain, \"x-ordered\") {", "if false {"),
            ("value.go", "sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })", ""),
            ("text.go", "if depth > maxDepth {", "if depth > maxDepth+1 {"),
        ]
        alive = []
        for i, (f, a, b) in enumerate(mutants):
            d = self.copy(f"m{i}")
            p = d / "manifest" / f
            src = p.read_text()
            self.assertIn(a, src, f"mutant {i}: {a!r} not in {f}")
            p.write_text(src.replace(a, b, 1))
            sums, bad = run(d)
            if sums is not None and not bad:
                alive.append((f, a))
        self.assertEqual(alive, [], "mutants not killed")


if __name__ == "__main__":
    unittest.main()
