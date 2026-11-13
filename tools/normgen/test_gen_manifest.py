"""Judge the P/02 loader and canonical view against lesson data. With Go 1.22 and cached pinned modules, no network, require fresh manifest files/module requirements/sums and vet. Check951 verdicts and text/form/relations classes, 220exact canonical bytes and402yaml-suite layer1 outcomes. Each runtime mutant must disagree with data. The corpus cannot distinguish extra empty-value refusal, layer2 normalization4.0->4 (JCS/text bytes coincide), or x-opaque projection with no nested defaults; preserve V7 rules despite those equivalent mutants."""
import lesson as output_lesson
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("NORMGEN_LESSON", "02-installer")
import gen_manifest  # noqa: E402

OUT = gen_manifest.DEFAULT_OUT / "go"
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")

HARNESS = r'''package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"%(module)s/manifest"
)

func mustRead(p string) []byte {
	b, err := os.ReadFile(p)
	if err != nil {
		panic(err)
	}
	return b
}

func tsv(p string) [][]string {
	b := mustRead(p)
	var out [][]string
	for _, l := range strings.Split(string(b), "\n") {
		if l == "" || strings.HasPrefix(l, "#") {
			continue
		}
		out = append(out, strings.Split(l, "\t"))
	}
	return out
}

func observe(group, name, kind string, ok bool, detail string) {
	b, err := json.Marshal(struct {
		Group string `json:"group"`
		Case string `json:"case"`
		Kind string `json:"kind"`
		OK bool `json:"ok"`
		Detail string `json:"detail"`
	}{group, name, kind, ok, detail})
	if err != nil { panic(err) }
	fmt.Printf("CASE %%s\n", b)
}

func checkStartup(ref *manifest.Refusal) {
	if ref != nil && ref.Class == "loader" {
		panic("checking loader failure: " + ref.Message)
	}
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
		data := mustRead(filepath.Join(acc, "cases", r[0]+".subsystem.yaml"))
		_, ref := manifest.Load(r[0]+".subsystem.yaml", data)
		checkStartup(ref)
		got := "ok"
		if ref != nil {
			got = "refused"
		}
		kind, detail := "verdict", ""
		passed := true
		switch {
		case got != r[1]:
			msg := ""
			if ref != nil {
				msg = ref.Message
			}
			passed = false
			detail = fmt.Sprintf("want %%s, got %%s %%s", r[1], got, msg)
		case ref != nil && classes[r[0]] != "" && ref.Class != classes[r[0]]:
			passed, kind = false, "class"
			detail = fmt.Sprintf("want %%s, got %%s %%s", classes[r[0]], ref.Class, ref.Message)
		default:
			ok++
			if classes[r[0]] != "" {
				cl++
			}
		}
		observe("verdicts", r[0], kind, passed, detail)
	}
	fmt.Printf("SUM verdicts %%d %%d classes %%d\n", ok, n, cl)
	vec := filepath.Join(root, "Platform/02-installer/vectors/canonical")
	cn, cok := 0, 0
	for _, r := range tsv(filepath.Join(vec, "cases.tsv")) {
		if r[0] == "case" {
			continue
		}
		cn++
		data := mustRead(filepath.Join(root, r[1]))
		want := mustRead(filepath.Join(vec, r[2]))
		got, ref := manifest.Canonical(filepath.Base(r[1]), data)
		checkStartup(ref)
		passed, detail := false, ""
		if ref == nil && bytes.Equal(got, want) {
			cok++
			passed = true
		} else if ref != nil {
			detail = "refused " + ref.Message
		} else {
			detail = "bytes differ"
		}
		observe("canonical", r[0], "canonical", passed, detail)
	}
	fmt.Printf("SUM canonical %%d %%d\n", cok, cn)
	yd := filepath.Join(root, "Platform/common/vectors/yaml-suite")
	yn, yok := 0, 0
	for _, r := range tsv(filepath.Join(yd, "expect.tsv")) {
		if r[0] == "id" {
			continue
		}
		yn++
		data := mustRead(filepath.Join(yd, "inputs", r[0]+".yaml"))
		_, _, refused := manifest.Layer1(data)
		got := "ok"
		if refused {
			got = "refused"
		}
		passed, detail := got == r[2], ""
		if passed {
			yok++
		} else {
			detail = fmt.Sprintf("want %%s, got %%s", r[2], got)
		}
		observe("yaml-suite", r[0], "yaml-suite", passed, detail)
	}
	fmt.Printf("SUM yaml-suite %%d %%d\n", yok, yn)
}
'''


class CheckingError(RuntimeError):
    """Execution or evidence failure, never a semantic mutant kill."""


GROUPS = ("verdicts", "canonical", "yaml-suite")


def source_roster(root):
    """Read expected case identities independently of the producer and Go output."""
    root = Path(root)
    def rows(rel, width, header=None):
        try:
            lines = (root / rel).read_text(encoding="utf-8").split("\n")
        except (OSError, UnicodeError) as exc:
            raise CheckingError(f"cannot read report source {rel}: {exc}") from exc
        cells = [line.split("\t") for line in lines if line and not line.startswith("#")]
        if header is not None:
            if not cells or cells.pop(0) != header:
                raise CheckingError(f"wrong report source header: {rel}")
        if not cells or any(len(row) != width or not row[0] for row in cells):
            raise CheckingError(f"empty or malformed report source: {rel}")
        if len({row[0] for row in cells}) != len(cells):
            raise CheckingError(f"duplicate report source case: {rel}")
        return cells

    acc = "Platform/02-installer/acceptance/1/"
    verdicts = dict(rows(acc + "verdicts.tsv", 2))
    classes = dict(rows(acc + "classes.tsv", 2))
    if any(value not in ("ok", "refused") for value in verdicts.values()) or \
            any(verdicts.get(name) != "refused" for name in classes) or \
            any(value not in ("text", "form", "relations") for value in classes.values()):
        raise CheckingError("invalid verdict/class source roster")
    canonical = rows("Platform/02-installer/vectors/canonical/cases.tsv", 4,
                     ["case", "input", "expect", "note"])
    yaml_suite = rows("Platform/common/vectors/yaml-suite/expect.tsv", 4, ["id", "suite", "layer1", "rule"])
    if any(row[2] not in ("ok", "refused") for row in yaml_suite):
        raise CheckingError("invalid YAML layer1 source outcome")
    return {"verdicts": set(verdicts), "canonical": {row[0] for row in canonical},
            "yaml-suite": {row[0] for row in yaml_suite}}, set(classes)


def unique_record(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CheckingError(f"duplicate report field {key}")
        out[key] = value
    return out


def parse_report(stdout, expected, class_cases):
    """Only complete named observations with consistent summaries are evidence."""
    if not isinstance(stdout, str) or not stdout.endswith("\n"):
        raise CheckingError("empty or truncated report")
    records, sums = {group: {} for group in GROUPS}, {}
    integer = r"(0|[1-9][0-9]*)"
    summary = re.compile(r"SUM (verdicts|canonical|yaml-suite) " + integer + " " + integer +
                         r"(?: classes " + integer + r")?")
    for line in stdout.split("\n")[:-1]:
        if line.startswith("CASE "):
            try:
                record = json.loads(line[5:], object_pairs_hook=unique_record)
            except ValueError as exc:
                raise CheckingError(f"malformed case report: {line[:160]}") from exc
            if not isinstance(record, dict) or set(record) != {"group", "case", "kind", "ok", "detail"}:
                raise CheckingError("wrong case report fields")
            group, case, kind = record["group"], record["case"], record["kind"]
            if not all(isinstance(value, str) for value in (group, case, kind, record["detail"])) or \
                    type(record["ok"]) is not bool:
                raise CheckingError("wrong case report types")
            if group not in records or case not in expected[group]:
                raise CheckingError(f"unknown reported case {group}/{case}")
            if case in records[group]:
                raise CheckingError(f"duplicate reported case {group}/{case}")
            kinds = ("verdict", "class") if group == "verdicts" else (group,)
            if kind not in kinds or kind == "class" and (case not in class_cases or record["ok"]):
                raise CheckingError(f"invalid observation kind {group}/{case}/{kind}")
            if bool(record["detail"]) == record["ok"]:
                raise CheckingError(f"inconsistent observation detail {group}/{case}")
            records[group][case] = record
        else:
            match = summary.fullmatch(line)
            if match is None:
                raise CheckingError(f"unrecognized report line: {line[:160]}")
            group, passed, total, classes = match.groups()
            if group in sums:
                raise CheckingError(f"duplicate SUM group {group}")
            if (group == "verdicts") != (classes is not None):
                raise CheckingError(f"wrong SUM fields for {group}")
            sums[group] = [passed, total] + (["classes", classes] if classes is not None else [])
    if set(sums) != set(GROUPS):
        raise CheckingError("incomplete SUM groups")
    bad = []
    for group in GROUPS:
        if not expected[group] or set(records[group]) != expected[group]:
            raise CheckingError(f"incomplete case roster for {group}")
        passed, total = sums[group][:2]
        observed = sum(record["ok"] for record in records[group].values())
        if total != str(len(expected[group])) or passed != str(observed):
            raise CheckingError(f"inconsistent SUM/case counts for {group}")
        for record in records[group].values():
            if not record["ok"]:
                bad.append(f"BAD {record['kind']} {record['case']}: {record['detail']}")
    class_count = sum(record["ok"] for case, record in records["verdicts"].items() if case in class_cases)
    if sums["verdicts"][3] != str(class_count):
        raise CheckingError("inconsistent class count")
    return sums, bad


def run(mod_dir, root=ROOT):
    expected, class_cases = source_roster(root)
    (mod_dir / "cmd/manifestjudge").mkdir(parents=True, exist_ok=True)
    (mod_dir / "cmd/manifestjudge/main.go").write_text(HARNESS % {"module": gen_manifest.L.go_module})
    try:
        p = subprocess.run(["go", "run", "./cmd/manifestjudge", str(root)], cwd=mod_dir, capture_output=True, text=True,
                           env=ENV, timeout=1800)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise CheckingError(f"cannot execute manifest judge: {exc}") from exc
    if p.returncode:
        raise CheckingError(f"manifest judge exited {p.returncode}: {p.stderr[-2000:]}")
    return parse_report(p.stdout, expected, class_cases)


class ReportControls(unittest.TestCase):
    """Owned case identities and outcomes, independent of the producer and report parser."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = {"verdicts": {"accepted", "refused"}, "canonical": {"vector"}, "yaml-suite": {"yaml"}}
        self.classes = {"refused"}
        self.records = [
            {"group": "verdicts", "case": "accepted", "kind": "verdict", "ok": True, "detail": ""},
            {"group": "verdicts", "case": "refused", "kind": "verdict", "ok": True, "detail": ""},
            {"group": "canonical", "case": "vector", "kind": "canonical", "ok": True, "detail": ""},
            {"group": "yaml-suite", "case": "yaml", "kind": "yaml-suite", "ok": True, "detail": ""},
        ]

    def report(self, records=None):
        records = self.records if records is None else records
        lines = ["CASE " + json.dumps(record, ensure_ascii=False) for record in records]
        for group in ("verdicts", "canonical", "yaml-suite"):
            observations = [record for record in records if record["group"] == group]
            passed = sum(record["ok"] is True for record in observations)
            line = f"SUM {group} {passed} {len(observations)}"
            if group == "verdicts":
                line += " classes " + str(sum(record["ok"] is True and record["case"] == "refused"
                                             for record in observations))
            lines.append(line)
        return "\n".join(lines) + "\n"

    def parse(self, text):
        return parse_report(text, self.expected, self.classes)

    def put(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def source_fixture(self):
        self.put("Platform/02-installer/acceptance/1/verdicts.tsv", "accepted\tok\nrefused\trefused\n")
        self.put("Platform/02-installer/acceptance/1/classes.tsv", "refused\tform\n")
        self.put("Platform/02-installer/vectors/canonical/cases.tsv",
                 "case\tinput\texpect\tnote\nvector\towned.yaml\texpect/vector.json\towned\n")
        self.put("Platform/common/vectors/yaml-suite/expect.tsv", "id\tsuite\tlayer1\trule\nyaml\tok\tok\t-\n")

    def test_complete_clean_report(self):
        sums, bad = self.parse(self.report())
        self.assertEqual(sums, {"verdicts": ["2", "2", "classes", "1"],
                                "canonical": ["1", "1"], "yaml-suite": ["1", "1"]})
        self.assertEqual(bad, [])

    def test_each_named_semantic_difference_requires_complete_normal_report(self):
        for at, kind in ((0, "verdict"), (1, "class"), (2, "canonical"), (3, "yaml-suite")):
            with self.subTest(kind=kind):
                records = [dict(record) for record in self.records]
                records[at].update(ok=False, kind=kind, detail="observed wrong value\nnext line\u0085\u2028")
                _, bad = self.parse(self.report(records))
                self.assertEqual(bad, [f"BAD {kind} {records[at]['case']}: " + records[at]["detail"]])

    def test_missing_extra_duplicate_or_zero_summaries_are_checking_errors(self):
        text = self.report()
        for group, line in (("verdicts", "SUM verdicts 2 2 classes 1\n"),
                            ("canonical", "SUM canonical 1 1\n"), ("yaml-suite", "SUM yaml-suite 1 1\n")):
            mutations = [text.replace(line, ""), text + line, text.replace(line, f"SUM {group} 0 0\n")]
            for changed in mutations:
                with self.subTest(group=group, changed=changed):
                    self.assertNotEqual(changed, text)
                    with self.assertRaises(CheckingError):
                        self.parse(changed)
        for extra in ("SUM extra 1 1\n", "BAD canonical vector: bytes differ\n", "diagnostic\n", "\n"):
            with self.assertRaises(CheckingError):
                self.parse(text + extra)

    def test_missing_extra_duplicate_or_unknown_case_is_not_a_semantic_kill(self):
        text = self.report()
        lines = text.split("\n")
        for at in range(len(self.records)):
            with self.subTest(missing=at):
                with self.assertRaises(CheckingError):
                    self.parse("\n".join(lines[:at] + lines[at + 1:]))
            with self.subTest(duplicate=at):
                with self.assertRaises(CheckingError):
                    self.parse(lines[at] + "\n" + text)
        for key, value in (("case", "foreign"), ("group", "foreign")):
            record = dict(self.records[0], **{key: value})
            with self.assertRaises(CheckingError):
                self.parse("CASE " + json.dumps(record) + "\n" + text)
        with self.assertRaises(CheckingError):
            self.parse(self.report([]))

    def test_malformed_truncated_and_inconsistent_counters_fail(self):
        text = self.report()
        variants = ["", text[:-1], "CASE {\n" + text, text.replace("SUM canonical 1 1", "SUM canonical 0 1"),
                    text.replace("classes 1", "classes 0"), text.replace("SUM canonical 1 1", "SUM canonical 1 2"),
                    text.replace("SUM verdicts 2 2 classes 1", "SUM verdicts 2 2"),
                    text.replace("SUM canonical 1 1", "SUM canonical 1 1 classes 1")]
        for value in ("-1", "01", "1.0", "true", "١", "9" * 5000):
            variants.append(text.replace("SUM canonical 1 1", f"SUM canonical {value} 1"))
        for changed in variants:
            with self.subTest(report=changed[:200]):
                self.assertNotEqual(changed, text)
                with self.assertRaises(CheckingError):
                    self.parse(changed)

    def test_record_shapes_types_duplicate_fields_and_detail_consistency_fail(self):
        text = self.report()
        first, rest = text.split("\n", 1)
        variants = [None, [], {}, {**self.records[0], "extra": 1}, {**self.records[0], "ok": 1},
                    {**self.records[0], "ok": False}, {**self.records[0], "detail": "unexpected"},
                    {**self.records[0], "kind": "unknown"}, {**self.records[0], "kind": "class"},
                    {**self.records[0], "group": []}, {**self.records[0], "detail": 5}]
        for record in variants:
            with self.subTest(record=record):
                with self.assertRaises(CheckingError):
                    self.parse("CASE " + json.dumps(record) + "\n" + rest)
        with self.assertRaises(CheckingError):
            self.parse(first.replace('"ok": true', '"ok": true, "ok": false') + "\n" + rest)

    def test_nonzero_launch_timeout_and_bad_reports_are_errors_even_with_a_mismatch(self):
        self.source_fixture()
        records = [dict(record) for record in self.records]
        records[2].update(ok=False, detail="bytes differ")
        semantic = self.report(records)
        for code in (1, 2, -9):
            with patch("subprocess.run", return_value=subprocess.CompletedProcess([], code, semantic, "owned error")):
                with self.assertRaises(CheckingError):
                    run(self.root / "module", self.root)
        for exc in (FileNotFoundError("owned missing go"), subprocess.TimeoutExpired("go", 1),
                    UnicodeError("owned decode failure")):
            with patch("subprocess.run", side_effect=exc):
                with self.assertRaises(CheckingError):
                    run(self.root / "module", self.root)
        for bad in (semantic.replace("SUM yaml-suite 1 1\n", ""), semantic + "SUM canonical 0 1\n",
                    semantic.replace("SUM canonical 0 1", "SUM canonical 0 0")):
            with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, bad, "")):
                with self.assertRaises(CheckingError):
                    run(self.root / "module", self.root)
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, semantic, "")):
            self.assertEqual(run(self.root / "module", self.root)[1], ["BAD canonical vector: bytes differ"])

    def test_source_roster_is_read_independently_and_cannot_be_empty_or_ambiguous(self):
        self.source_fixture()
        self.assertEqual(source_roster(self.root), (self.expected, self.classes))
        rels = ("Platform/02-installer/acceptance/1/verdicts.tsv", "Platform/02-installer/acceptance/1/classes.tsv",
                "Platform/02-installer/vectors/canonical/cases.tsv", "Platform/common/vectors/yaml-suite/expect.tsv")
        for rel in rels:
            path = self.root / rel
            original = path.read_bytes()
            for content in (None, b"", b"\xff", original + original.split(b"\n")[-2] + b"\n"):
                with self.subTest(source=rel, content=content):
                    if content is None:
                        path.unlink()
                    else:
                        path.write_bytes(content)
                    with self.assertRaises(CheckingError):
                        source_roster(self.root)
                    path.write_bytes(original)
        self.put(rels[1], "foreign\tform\n")
        with self.assertRaises(CheckingError):
            source_roster(self.root)


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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        d = self.tmp / name
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        shutil.copytree(OUT / "manifest", d / "manifest")
        for f in ("go.mod", "go.sum"):
            shutil.copy(OUT / f, d / f)
        return d

    def test_fresh_and_vet(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for relp, data in self.files.items():
            self.assertEqual((OUT / relp).read_bytes(), data, f"{relp} is stale: run gen_manifest.py")
        mod, s = gen_manifest.go_mod(gen_manifest.DEFAULT_OUT)
        self.assertEqual((OUT / "go.mod").read_bytes(), mod)
        self.assertEqual((OUT / "go.sum").read_bytes(), s)
        v = subprocess.run(["go", "vet", "./manifest/"], cwd=self.copy("vet"), capture_output=True, text=True, env=ENV)
        self.assertEqual(v.returncode, 0, v.stderr)

    def test_corpus(self):
        sums, bad = run(self.copy("clean"))
        self.assertIsNotNone(sums, bad)
        self.assertEqual(bad, [])
        for k, (got, total) in ((k, v[:2]) for k, v in sums.items()):
            self.assertEqual(got, total, k)
        self.assertEqual(int(sums["verdicts"][1]), 951)
        self.assertEqual(int(sums["canonical"][1]), 220)
        self.assertEqual(int(sums["yaml-suite"][1]), 402)

    def test_actual_read_compile_and_start_failures_are_checking_errors(self):
        """Real Go fault controls on owned input/module copies, never semantic kills."""
        with tempfile.TemporaryDirectory(prefix="manifest-checking-source-") as tmp:
            root = Path(tmp)

            def put(rel, data):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data.encode() if isinstance(data, str) else data)
                return path

            acc = "Platform/02-installer/acceptance/1/"
            vec = "Platform/02-installer/vectors/canonical/"
            suite = "Platform/common/vectors/yaml-suite/"
            put(acc + "verdicts.tsv", "accepted\tok\nrefused\trefused\n")
            put(acc + "classes.tsv", "refused\tform\n")
            valid = (ROOT / acc / "cases/r38_unit_minimal.subsystem.yaml").read_bytes()
            put(acc + "cases/accepted.subsystem.yaml", valid)
            refused = put(acc + "cases/refused.subsystem.yaml", valid + b"\nowned_unknown_key: true\n")
            put(vec + "cases.tsv", "case\tinput\texpect\tnote\nvector\towned.yaml\texpect/vector.json\towned\n")
            inp = put("owned.yaml", (ROOT / vec / "inputs/sections.subsystem.yaml").read_bytes())
            want = put(vec + "expect/vector.json", (ROOT / vec / "expect/example-sections.json").read_bytes())
            put(suite + "expect.tsv", "id\tsuite\tlayer1\trule\nyaml\tok\tok\t-\n")
            yaml_input = put(suite + "inputs/yaml.yaml", "root: value\n")
            module = self.copy("checking-inputs")
            sums, bad = run(module, root)
            self.assertEqual(bad, [])
            self.assertEqual(sums, {"verdicts": ["2", "2", "classes", "1"],
                                    "canonical": ["1", "1"], "yaml-suite": ["1", "1"]})
            for path in (inp, want, refused, yaml_input):
                with self.subTest(unreadable=path.relative_to(root)):
                    saved = path.read_bytes()
                    try:
                        path.unlink()
                        with self.assertRaisesRegex(CheckingError, "exited"):
                            run(module, root)
                        print(f"CHECKING CONTROL missing {path.relative_to(root)}: ERROR, not killed", flush=True)
                    finally:
                        path.write_bytes(saved)
            broken = self.copy("checking-compile")
            (broken / "manifest/value.go").write_text("package manifest\nfunc broken(\n")
            with self.assertRaisesRegex(CheckingError, "exited"):
                run(broken, root)
            print("CHECKING CONTROL compiler failure: ERROR, not killed", flush=True)
            broken = self.copy("checking-start")
            (broken / "manifest/forms/schema.json").write_text("{")
            with self.assertRaisesRegex(CheckingError, "checking loader failure"):
                run(broken, root)
            print("CHECKING CONTROL loader startup failure: ERROR, not killed", flush=True)

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

    def test_mutants(self):
        mutants = [
            ("manifest.go", "if len(numbers) > 0 {", "if false {"),
            ("manifest.go", "if len(got) > 0 {", "if false {"),
            ("view.go", "\tsugar(t)\n", "\n"),
            ("view.go", "if _, ok := o.M[\"snapshot\"]; !ok {", "if false {"),
            ("view.go", "setDefault(j, \"deleted\", k+\".deleted\")", ""),
            ("view.go", "if _, has := d.M[\"form\"]; !has {", "if false {"),
            ("view.go", "\t\tsetDefault(f, \"default\", nil)\n", "\t\t_ = f\n"),
            ("view.go", "setDefault(e, \"decoded\", true)", ""),
            ("view.go", "if ordered && truthy(chain, \"x-ordered\") {", "if false {"),
            ("value.go", "sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })",
             "sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[j], keys[i]) })"),
            ("text.go", "if depth > maxDepth {", "if depth > maxDepth+1 {"),
        ]
        alive = []
        for i, (f, a, b) in enumerate(mutants):
            with self.subTest(mutant=i, file=f):
                d = self.copy(f"m{i}")
                p = d / "manifest" / f
                src = p.read_text()
                self.assertEqual(src.count(a), 1, f"mutant {i}: ambiguous or missing target in {f}")
                p.write_text(src.replace(a, b, 1))
                sums, bad = run(d)  # CheckingError is an ERROR of this test, never a kill.
                if not bad:
                    alive.append((f, a))
                else:
                    print(f"MUTANT {i} {f}: complete {sums}; semantic witness {bad[0][:240]}", flush=True)
        self.assertEqual(alive, [], "mutants not killed")


if __name__ == "__main__":
    unittest.main()
