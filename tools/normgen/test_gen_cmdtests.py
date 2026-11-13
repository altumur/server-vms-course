"""Test non-HTTP gen_cmdtests output: freshness, all scaffold tests fail without panic, fixture adapter tests pass, adapter/seam mutants fail and puts remain explicitly excluded. Fixture Command models seam w2cctl semantics; Load uses seams/corpus oracle; LoadCatalogue/RolloutPoll return seam-declared answers."""
import lesson as output_lesson
import tsv_input
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

func observation(name string, input json.RawMessage) (json.RawMessage, error) {
    var parsed any
    if err:=json.Unmarshal(input,&parsed);err!=nil {return nil,err}
    key,err:=json.Marshal(parsed)
    if err!=nil {return nil,err}
    out,ok:=observations[name+"|"+string(key)]
    if !ok {return nil,fmt.Errorf("fixture input not declared: %s",key)}
    return json.RawMessage(out),nil
}
func InstallerRoleUnitGroups(roots Roots, input json.RawMessage) (json.RawMessage,error) {
    return observation("installer-role-unit-groups",input)
}
func SecretsWalk(roots Roots, input json.RawMessage) (json.RawMessage,error) {
    return observation("secrets-walk",input)
}

var _ = base64.StdEncoding
'''


def answers():
    """Read LoadCatalogue/RolloutPoll fixture answers from seams, keyed by adapter-input JSON."""
    cats, polls = {}, {}
    for f in sorted((ROOT / "Platform/02-installer/acceptance").glob("*/seams.tsv")):
        table = tsv_input.read(f, names=("scenario", "step", "request", "expect"), positional=True, root=ROOT)
        for _, row in table.rows:
            cells = [row[k] for k in table.columns]
            if not cells[2].startswith("CALL "):
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
    out += ["}", "", "var observations = map[string]string{"]
    for path in (ROOT / "Platform/02-installer/acceptance").glob("*/seams.tsv"):
        table = tsv_input.read(path, names=("scenario", "step", "request", "expect"), positional=True, root=ROOT)
        for _, row in table.rows:
            if not row["request"].startswith("CALL "):
                continue
            name, _, data = row["request"][5:].partition(" ")
            if name in ("installer-role-unit-groups", "secrets-walk"):
                key = name + "|" + json.dumps(json.loads(data),sort_keys=True,separators=(",", ":"),ensure_ascii=False)
                out.append(f"\t{go_str(key)}: {go_str(row['expect'])},")
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        for f in ("command.go", "load.go", "catalogue.go", "poll.go", "installer_role_unit_groups.go", "secrets_walk.go"):
            (ad / f).unlink()
        text = FAKE
        if mutate:
            self.assertIn(mutate[0], text)
            text = text.replace(mutate[0], mutate[1], 1)
        (ad / "fake.go").write_text(text, encoding="utf-8")
        (ad / "answers.go").write_text(fake_answers_go(), encoding="utf-8")
        return t / "go"

    def test_out_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for rel in ("stagetests/engine_test.go", "stagetests/manifest_load_test.go", "stagetests/operator_files_test.go", "stagetests/inventory.tsv",
                    "lessonadapter/lessonadapter.go", "lessonadapter/command.go"):
            self.assertEqual((self.mod / rel).read_bytes(), (output_lesson.output_root() / 'p02/go' / rel).read_bytes(),
                             f"{rel}: run gen_cmdtests.py --lesson 02-installer")

    def test_inventory(self):
        inv = (self.mod / "stagetests/inventory.tsv").read_text(encoding="utf-8")
        self.assertIn("2.3/puts.tsv/*\tmanifest-put\t-\texcluded\tneeds the store of P/01 (runner corpus puts)", inv)
        self.assertIn("2.2/puts.tsv/*\tcanonical-put\t-\texcluded", inv)
        self.assertEqual(inv.count("\ttranslated\t"), 951 + 34)

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
        self.assertEqual(len(res), 1 + 4 + 5 + 7)          # Verdicts + s1–s4 (2.1) + s1–s4 (2.4) + s5–s11 (poll)

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

    def test_observation_call_errors_empty_json_and_panics_fail(self):
        old = 'return observation("installer-role-unit-groups",input)'
        for replacement in ('return nil,fmt.Errorf("owned error")', 'return nil,nil',
                            'return json.RawMessage(`not-json`),nil', 'panic("owned panic")'):
            with self.subTest(replacement=replacement):
                res, _, _ = results(self.fake((old, replacement)))
                red = {n for n, a in res.items() if a != "pass"}
                self.assertEqual(red, {"TestRunnerWorkers_S14UnitRoleSocketGroups"})

    def test_seam_mutant(self):
        """Mutating a seam expectation in an alternate source root must fail exactly that scenario."""
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
        for f in ("command.go", "load.go", "catalogue.go", "poll.go", "installer_role_unit_groups.go", "secrets_walk.go"):
            (t / "go/lessonadapter" / f).unlink()
        (t / "go/lessonadapter/fake.go").write_text(FAKE, encoding="utf-8")
        (t / "go/lessonadapter/answers.go").write_text(fake_answers_go(), encoding="utf-8")
        res, _, _ = results(t / "go")
        self.assertEqual({n for n, a in res.items() if a != "pass"}, {"TestManifestLoad_S4LoadLayerOrder"})



class SeamTransport(unittest.TestCase):
    """Transport expectations come from owned bytes and actual source, never render."""
    def setUp(self):
        import gen_cmdtests
        from unittest.mock import patch
        self.gen = gen_cmdtests
        selected = patch.object(self.gen, 'L', output_lesson.get('02-installer'))
        selected.start()
        self.addCleanup(selected.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='cmd-seam-transport-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'Platform/02-installer/acceptance/1/seams.tsv'
        self.path.parent.mkdir(parents=True)

    def marked(self):
        import hashlib
        # One escaped Unicode spelling and one nested quoted request: decode once.
        self.expected = [(4, '1', 'CALL port {"text":"\\u0410"}', '{"accepted":true}'),
                         (5, '2', '"RUN literal"', '"quoted result"')]
        lines = ['# cell-json: request,expect', '# scenario\tstep\trequest\texpect', '']
        proofs = ['table\tline\tcolumn\tbefore_sha256\tdecoded_sha256']
        for line, step, request, expect in self.expected:
            lines.append('first\t' + step + '\t' + json.dumps(request) + '\t' + json.dumps(expect))
            for column, value in [('request', request), ('expect', expect)]:
                digest = hashlib.sha256(value.encode()).hexdigest()
                proofs.append(f'{self.path.relative_to(self.root).as_posix()}\t{line}\t{column}\t{digest}\t{digest}')
        self.path.write_text('\n'.join(lines) + '\n')
        proof = self.root / 'Platform/common/data/cell-json-sha256.tsv'
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text('\n'.join(proofs) + '\n')
        return proof

    def test_marked_single_decode_physical_coordinates_and_first_data_row(self):
        self.marked()
        path, scenarios = self.gen.read_seams(self.root, '2.1')
        self.assertEqual(path, self.path)
        self.assertEqual(scenarios, {'first': self.expected})
        self.assertIn('\\u0410', scenarios['first'][0][2])
        self.assertEqual(scenarios['first'][1][2], '"RUN literal"')

    def test_plain_headerless_and_comment_header_keep_the_first_row(self):
        data = 'first\t1\tCALL port {}\t{}\n'
        for prefix, line in [('', 1), ('# scenario\tstep\trequest\texpect\n', 2), ('# history\n\n', 3)]:
            with self.subTest(prefix=prefix):
                self.path.write_text(prefix + data)
                self.assertEqual(self.gen.read_seams(self.root, '2.1')[1], {'first': [(line, '1', 'CALL port {}', '{}')]})

    def test_missing_bad_extra_and_duplicate_proof_are_typed_refusals(self):
        proof = self.marked()
        original = proof.read_text()
        lines = original.splitlines()
        mutations = ['', '\n'.join(lines[:-1]) + '\n', original.replace(lines[1].split('\t')[-1], '0' * 64),
                     original + lines[1] + '\n', original + lines[1].replace('\t4\t', '\t99\t') + '\n']
        for changed in mutations:
            with self.subTest(proof=changed[-40:]):
                proof.write_text(changed)
                with self.assertRaises(self.gen.GenError):
                    self.gen.read_seams(self.root, '2.1')
        proof.unlink()
        with self.assertRaises(self.gen.GenError):
            self.gen.read_seams(self.root, '2.1')

    def test_malformed_outer_cells_and_nonconsecutive_step_refuse(self):
        for cell in ('{}', 'true', '"unterminated', 'null'):
            self.marked()
            text = self.path.read_text()
            lines = text.split('\n')
            row = lines[3].split('\t')
            row[2] = cell
            lines[3] = '\t'.join(row)
            self.path.write_text('\n'.join(lines))
            with self.subTest(cell=cell), self.assertRaises(self.gen.GenError):
                self.gen.read_seams(self.root, '2.1')
        (self.root / 'Platform/common/data/cell-json-sha256.tsv').unlink()
        self.path.write_text('first\t2\tCALL port {}\t{}\n')
        with self.assertRaisesRegex(self.gen.GenError, 'seams.tsv:1: first step 2'):
            self.gen.read_seams(self.root, '2.1')

    def test_actual_p06_first_marked_row(self):
        from unittest.mock import patch
        with patch.object(self.gen, 'L', output_lesson.get('06-console')):
            path, scenarios = self.gen.read_seams(ROOT, '6.8')
        self.assertEqual(path, ROOT / 'Platform/06-console/acceptance/8/seams.tsv')
        first = scenarios['s01-folder-name-255-bytes'][0]
        self.assertEqual(first[:2], (4, '1'))
        self.assertTrue(first[2].startswith('CALL console-folder-create {"name":"'))
        request = json.loads(first[2].split(' ', 2)[2])
        self.assertEqual(len(request['name'].encode()), 255)
        self.assertEqual(json.loads(first[3])['status'], 201)

if __name__ == "__main__":
    unittest.main()
