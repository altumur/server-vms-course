"""Тесты генератора тестов этапов урока без HTTP (gen_cmdtests.py; P/02, ADR-0125 доп. (5)): out свежий; на заглушках
адаптера всё красное без паники; на подставном адаптере (Command — семантика w2cctl швов, Load — правила швов и оракул
корпуса, LoadCatalogue и RolloutPoll — ответы, выписанные из самих швов) всё зелёное; мутанты адаптера и шва — красные;
puts — в описи excluded с причиной."""
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
P02 = "02-installer"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")

FAKE = r'''package lessonadapter

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"os"
	"fmt"
	"path/filepath"
	"strconv"
	"strings"
	"unicode/utf8"
)

var oracle = map[string]Loaded{}

func init() {
	f, err := os.Open(filepath.Join("testdata", "verdicts.jsonl"))
	if err != nil {
		return
	}
	defer f.Close()
	in := bufio.NewScanner(f)
	in.Buffer(make([]byte, 1<<20), 1<<26)
	for in.Scan() {
		var c struct{ Case, Verdict, Class, B64 string }
		_ = json.Unmarshal(in.Bytes(), &c)
		src := c.Case + ".subsystem.yaml"
		if c.Verdict == "ok" {
			oracle[src] = Loaded{OK: true, Name: c.Case}
		} else {
			cls := c.Class
			if cls == "" {
				cls = "form"
			}
			oracle[src] = Loaded{Class: cls, Message: "refused: " + src}
		}
	}
}

func Load(source string, text []byte) Loaded {
	if l, ok := oracle[source]; ok {
		return l
	}
	switch {
	case !utf8.Valid(text) || source == "text-first.yaml":
		return Loaded{Class: "text", Message: "refused:text " + source}
	case source == "relations.yaml":
		return Loaded{Class: "relations", Message: "refused:relations " + source}
	case strings.HasPrefix(source, "bad"):
		return Loaded{Class: "form", Message: "refused:form " + source}
	}
	for _, line := range strings.Split(string(text), "\n") {
		if strings.HasPrefix(line, "name: ") {
			return Loaded{OK: true, Name: strings.TrimPrefix(line, "name: ")}
		}
	}
	return Loaded{Class: "form", Message: "refused:form " + source}
}

func LoadCatalogue(ms []Source) Catalogue {
	key, _ := json.Marshal(ms)
	if c, ok := catalogues[string(key)]; ok {
		return c
	}
	return Catalogue{Class: "catalogue", Message: "unknown"}
}

func RolloutPoll(input json.RawMessage, events []Event) Poll {
	if len(events) == 0 {
		return Poll{}
	}
	last := events[len(events)-1]
	key := fmt.Sprintf("%d|%s|%s|%s", len(events), strconv.FormatFloat(last.T, 'g', -1, 64), last.Event,
		strconv.FormatFloat(events[0].T, 'g', -1, 64))
	return polls[key]
}

func Command(r Roots, process string, argv []string, stdin []byte) Result {
	if process != "w2cctl" || len(argv) < 3 {
		return Result{Exit: 2, Stderr: []byte("usage\n")}
	}
	path := argv[2]
	switch argv[0] + " " + argv[1] {
	case "manifest put":
		data, err := os.ReadFile(path)
		if err != nil {
			return Result{Exit: 2, Stderr: []byte(err.Error() + "\n")}
		}
		if l := Load(filepath.Base(path), data); !l.OK {
			return Result{Exit: 2, Stderr: []byte(l.Message + "\n")}
		}
		return Result{}
	case "secrets new":
		_ = os.MkdirAll(filepath.Dir(path), 0o755)
		f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err != nil {
			return Result{Exit: 1, Stderr: []byte("exists\n")}
		}
		_, _ = f.WriteString("ring-v1\n")
		_ = f.Close()
		return Result{}
	case "secrets rotate":
		data, err := os.ReadFile(path)
		if err != nil || !strings.HasPrefix(string(data), "ring") {
			return Result{Exit: 1, Stderr: []byte("not a ring\n")}
		}
		return Result{}
	}
	return Result{Exit: 2}
}

var _ = base64.StdEncoding
'''


def answers():
    """Ответы LoadCatalogue и RolloutPoll, выписанные из швов (ключ — вход в форме JSON адаптера)."""
    cats, polls = {}, {}
    for f in sorted((ROOT / "Platform/02-installer/acceptance").glob("*/seams.tsv")):
        for line in f.read_text(encoding="utf-8").split("\n"):
            cells = line.split("\t")
            if line.startswith("#") or len(cells) != 4 or not cells[2].startswith("CALL "):
                continue
            name, _, js = cells[2][5:].partition(" ")
            exp = cells[3]
            for prefix in ("each ", "one "):
                if exp.startswith(prefix):
                    exp = exp[len(prefix):].split("; rest ")[0]
            inp, want = json.loads(js), json.loads(exp)
            if name == "load-catalogue":
                ms = [{"Source": m["source"], "Text": __import__("base64").b64encode(m["text"].encode()).decode()}
                      for m in inp["manifests"]]
                if want["verdict"] == "ok":
                    cats[json.dumps(ms, separators=(",", ":"))] = ("ok", want["names"], "")
                else:
                    cats[json.dumps(ms, separators=(",", ":"))] = ("refused", [], want["class"])
            elif name == "rollout-poll":
                ev = inp["events"]
                key = f"{len(ev)}|{format(float(ev[-1]['t']), 'g')}|{ev[-1]['event']}|{format(float(ev[0]['t']), 'g')}"
                assert key not in polls, key
                polls[key] = want
    return cats, polls


def go_str(s):
    return json.dumps(s, ensure_ascii=False)


def fake_answers_go():
    cats, polls = answers()
    out = ["package lessonadapter", "", "var catalogues = map[string]Catalogue{"]
    for k, (v, names, cls) in cats.items():
        out.append(f"\t{go_str(k)}: {{OK: {'true' if v == 'ok' else 'false'}, Names: []string{{"
                   + ", ".join(go_str(n) for n in names) + f"}}, Class: {go_str(cls)}, Message: \"refused\"}},")
    out += ["}", "", "var polls = map[string]Poll{"]
    for k, w in polls.items():
        res = "nil" if w["result"] is None else f"&PollResult{{Code: {w['result']['code']}, Word: {go_str(w['result']['word'])}}}"
        out.append(f"\t{go_str(k)}: {{State: {go_str(w['state'])}, Result: {res}}},")
    out.append("}")
    return "\n".join(out) + "\n"


def gen(out, root=ROOT):
    env = dict(os.environ, NORMGEN_LESSON=P02)
    cmd = [sys.executable, "-c", "import sys; sys.path.insert(0, %r); import gen_cmdtests as g; "
           "from pathlib import Path; g.generate(Path(%r), Path(%r))" % (str(HERE), str(root), str(out))]
    done = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if done.returncode:
        raise AssertionError(done.stderr)


def results(mod):
    done = subprocess.run(["go", "test", "-count=1", "-json", "./stagetests/"], cwd=mod, capture_output=True, text=True,
                          env=GOENV)
    res, panics = {}, 0
    for line in done.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") == "output" and "panic:" in e.get("Output", "") and "a crash" not in e.get("Output", ""):
            panics += 1
        if e.get("Test") and "/" not in e["Test"] and e["Action"] in ("pass", "fail"):
            res[e["Test"]] = e["Action"]
    return res, panics, done


@unittest.skipUnless((ROOT / "Platform/02-installer/acceptance/1/verdicts.tsv").is_file(), "no P/02 acceptance")
class CmdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cmdtests-")
        cls.out = Path(cls.tmp.name) / "out"
        gen(cls.out)
        cls.mod = cls.out / "go"
        (cls.mod / "go.mod").write_text("module normgen/p02\n\ngo 1.22\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fake(self, mutate=None):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        ad = t / "go/lessonadapter"
        for f in ("command.go", "load.go", "catalogue.go", "poll.go"):
            (ad / f).unlink()
        text = FAKE
        if mutate:
            self.assertIn(mutate[0], text)
            text = text.replace(mutate[0], mutate[1], 1)
        (ad / "fake.go").write_text(text, encoding="utf-8")
        (ad / "answers.go").write_text(fake_answers_go(), encoding="utf-8")
        return t / "go"

    def test_out_fresh(self):
        for rel in ("stagetests/engine_test.go", "stagetests/manifest_load_test.go", "stagetests/operator_files_test.go", "stagetests/inventory.tsv",
                    "lessonadapter/lessonadapter.go", "lessonadapter/command.go"):
            self.assertEqual((self.mod / rel).read_bytes(), (HERE / "out/p02/go" / rel).read_bytes(),
                             f"{rel}: run gen_cmdtests.py --lesson 02-installer")

    def test_inventory(self):
        inv = (self.mod / "stagetests/inventory.tsv").read_text(encoding="utf-8")
        self.assertIn("2.3/puts.tsv/*\tmanifest-put\t-\texcluded\tneeds the store of P/01 (runner corpus puts)", inv)
        self.assertIn("2.2/puts.tsv/*\tcanonical-put\t-\texcluded", inv)
        self.assertEqual(inv.count("\ttranslated\t"), 947 + 33)

    def test_review_operator_file_and_ordinary_seams(self):
        operator = (self.mod / "stagetests/operator_files_test.go").read_text(encoding="utf-8")
        self.assertIn("$data/new.key", operator)
        self.assertNotIn("$data/keys/new.key", operator)
        seams = ROOT / "Platform/02-installer/acceptance/4/seams.tsv"
        ordinary = {line.split("\t", 1)[0] for line in seams.read_text(encoding="utf-8").splitlines()
                    if line.startswith(("s12-", "s13-"))}
        self.assertEqual(ordinary, {"s12-secrets-walk-unknown", "s13-secrets-walk-kept"})
        inventory = (self.mod / "stagetests/inventory.tsv").read_text(encoding="utf-8")
        for scenario in ordinary:
            self.assertNotIn(f"/seams.tsv/{scenario}/", inventory)

    def test_stub_red_without_panic(self):
        res, panics, _ = results(self.mod)
        self.assertTrue(res)
        self.assertEqual(set(res.values()), {"fail"})
        self.assertEqual(panics, 0)

    def test_fake_green(self):
        res, _, done = results(self.fake())
        self.assertEqual({n for n, a in res.items() if a != "pass"}, set(), done.stdout[-3000:])
        self.assertEqual(len(res), 1 + 4 + 4 + 7)          # Verdicts + s1–s4 (2.1) + s1–s4 (2.4) + s5–s11 (poll)

    def test_adapter_mutants(self):
        for old, new, want, why in (
                ('return Loaded{Class: "relations"', 'return Loaded{Class: "form"', {"TestManifestLoad_S4LoadLayerOrder"},
                 "class"),
                ("os.O_CREATE|os.O_EXCL|os.O_WRONLY", "os.O_CREATE|os.O_TRUNC|os.O_WRONLY",
                 {"TestOperatorFiles_S2NewExisting", "TestOperatorFiles_S4NewExclusive"}, "exclusive create"),
                ('if c.Verdict == "ok" {', 'if c.Verdict != "ok" {', {"TestManifestLoad_Verdicts"}, "corpus verdict"),
                ('Message: "refused: " + src', 'Message: "refused"', {"TestManifestLoad_Verdicts"}, "file not named"),
                ("return polls[key]", "p := polls[key]\n\tp.State = \"passed\"\n\treturn p",
                 None, "poll state")):
            res, _, _ = results(self.fake((old, new)))
            red = {n for n, a in res.items() if a != "pass"}
            if want is None:
                self.assertTrue(any(n.startswith("TestRolloutPoll_") for n in red), why)
            else:
                self.assertTrue(want <= red, f"mutant {why}: red {red}, want {want}")

    def test_seam_mutant(self):
        """Ожидание шва, изменённое в копии корня, даёт красный тест ровно этого сценария."""
        root = Path(self.tmp.name) / "root"
        shutil.copytree(ROOT / "Platform/02-installer", root / "Platform/02-installer")
        seams = root / "Platform/02-installer/acceptance/1/seams.tsv"
        text = seams.read_text(encoding="utf-8")
        old = '{"verdict":"refused","class":"relations"}'
        self.assertIn(old, text)
        seams.write_text(text.replace(old, '{"verdict":"refused","class":"form"}', 1), encoding="utf-8")
        out = Path(self.tmp.name) / "out-m"
        gen(out, root)
        mod = out / "go"
        (mod / "go.mod").write_text("module normgen/p02\n\ngo 1.22\n", encoding="utf-8")
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(mod, t / "go")
        for f in ("command.go", "load.go", "catalogue.go", "poll.go"):
            (t / "go/lessonadapter" / f).unlink()
        (t / "go/lessonadapter/fake.go").write_text(FAKE, encoding="utf-8")
        (t / "go/lessonadapter/answers.go").write_text(fake_answers_go(), encoding="utf-8")
        res, _, _ = results(t / "go")
        self.assertEqual({n for n, a in res.items() if a != "pass"}, {"TestManifestLoad_S4LoadLayerOrder"})


if __name__ == "__main__":
    unittest.main()
