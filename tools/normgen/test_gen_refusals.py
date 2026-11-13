"""Test gen_refusals/refusal_judge (ADR-0125 generator 4): output freshness, judge PASS on generated code and FAIL on status/field/header/name mutants, malformed-table GenError, door+refusals kit build/vet, and Check/LogLine/Exit catalog behavior. Go 1.22, no network."""
import lesson as output_lesson
import contextlib
import copy
import csv
import hashlib
import io
import json
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

import gen_refusals  # noqa: E402
import refusal_judge  # noqa: E402 -- the judge under test, never the expected-source parser
from gen_checks import GenError  # noqa: E402

OUT = output_lesson.output_root() / 'p01-1/go'
TABLE = gen_refusals.DEFAULT_TABLE.read_text(encoding="utf-8")


def judge(module_dir):
    with tempfile.TemporaryDirectory(prefix="refusal-report-") as tmp:
        report = Path(tmp) / "result.json"
        try:
            done = subprocess.run([sys.executable, str(HERE / "refusal_judge.py"), "--module-dir", str(module_dir),
                                   "--json", str(report)], capture_output=True, timeout=600)
            if type(done.returncode) is not int or done.returncode not in (0, 1) or done.stderr:
                raise refusal_judge.CheckingError(f"judge process failed: {done.returncode}, {done.stderr!r}")
            normal_result(done.returncode, report.read_bytes())
            stdout = done.stdout.decode("utf-8", "strict")
            stderr = done.stderr.decode("utf-8", "strict")
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise refusal_judge.CheckingError(f"cannot obtain complete judge report: {exc}") from exc
    return done.returncode, stdout + stderr


def normal_result(code, raw):
    """A killed mutant needs a normal, complete semantic result, not merely a nonzero process."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate result key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs)
        if (type(code) is not int or code not in (0, 1) or type(value) is not dict or
                set(value) != {"passed", "total", "verdict", "results"} or
                type(value["passed"]) is not int or type(value["total"]) is not int or
                type(value["results"]) is not list or not value["results"] or
                value["total"] != len(value["results"])):
            raise ValueError("empty/malformed result summary")
        names, passed = set(), 0
        for row in value["results"]:
            if (type(row) is not dict or set(row) != {"name", "ok", "why"} or
                    type(row["name"]) is not str or not row["name"] or row["name"] in names or
                    type(row["ok"]) is not bool or
                    (row["why"] is not None and type(row["why"]) is not str) or
                    (row["ok"] and row["why"] is not None) or (not row["ok"] and not row["why"])):
                raise ValueError("incomplete/duplicate/mistyped named result")
            row["name"].encode("utf-8", "strict")
            if row["why"] is not None:
                row["why"].encode("utf-8", "strict")
            names.add(row["name"])
            passed += row["ok"]
        verdict = "PASS" if passed == len(names) else "FAIL"
        if (value["passed"] != passed or value["verdict"] != verdict or
                code != (0 if verdict == "PASS" else 1)):
            raise ValueError("result summary and process exit disagree")
        return value
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise refusal_judge.CheckingError(f"invalid semantic report: {exc}") from exc


def mutate(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


BEHAVIOUR = '''package refusals

import (
	"strings"
	"testing"
)

func TestBehaviour(t *testing.T) {
	if CasMismatch.Check(map[string]any{"index": "1"}) != nil || CasMismatch.Check(map[string]any{"index": "1", "key": "k"}) != nil {
		t.Fatal("cas_mismatch: index and optional key")
	}
	if CasMismatch.Check(map[string]any{}) == nil || CasMismatch.Check(map[string]any{"index": "1", "size": 3}) == nil {
		t.Fatal("cas_mismatch: no index or an extra field passes")
	}
	if Weight.Check(map[string]any{"limit": int64(1), "key": "k", "size": 2.5}) == nil {
		t.Fatal("a float passes")
	}
	line, err := StartFlags.LogLine(map[string]string{"flag": "-x"})
	if err != nil || !strings.Contains(line, `flag="-x"`) {
		t.Fatal(line, err)
	}
	if _, err := StartFlags.LogLine(map[string]string{}); err == nil {
		t.Fatal("a log naming nothing passes")
	}
	if _, err := StartFlags.LogLine(map[string]string{"dir": "/d"}); err == nil {
		t.Fatal("a value outside the log passes")
	}
	if l, _ := BoxNoRaft.LogLine(nil); !strings.Contains(l, "this build has no raft") {
		t.Fatal(l)
	}
	var logged string
	if BoxAdmit.Exit(func(s string) { logged = s }, nil) == 0 || logged == "" {
		t.Fatal("exit !0")
	}
	if StartFlags.Code != 2 || ByName("connection_limit") != ConnectionLimit || !ConnectionLimit.RetryAfter || ByName("nope") != nil {
		t.Fatal("catalogue")
	}
}
'''


class GenRefusals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-refusals-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_is_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name, text in gen_refusals.render().items():
            self.assertEqual((OUT / "refusals" / name).read_text(encoding="utf-8"), text, "run gen_refusals.py")

    def test_judge_passes(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        code, out = judge(OUT)
        self.assertEqual(code, 0, out[-3000:])
        self.assertRegex(out, r"refusals: (\d+)/\1 PASS")

    def test_judge_catches_mutants(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        mutants = [
            ('Name: "cas_mismatch", Surface: "http", Code: 409', 'Name: "cas_mismatch", Surface: "http", Code: 410'),
            ('Fields: []Field{{"index", false}, {"key", true}}', 'Fields: []Field{{"index", false}}'),
            ('Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: true',
             'Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: false'),
            ('"guard_mismatch", Surface: "http", Code: 412, Kind: "guard"',
             '"guard_mismatch", Surface: "http", Code: 412, Kind: "guards"'),
            ('Name: "start_flags", Surface: "start", Code: 2', 'Name: "start_flags", Surface: "start", Code: 1'),
        ]
        for k, (old, new) in enumerate(mutants):
            with self.subTest(mutant=new):
                mod = Path(self.tmp.name) / f"mut{k}"
                shutil.copytree(OUT, mod)
                path = mod / "refusals/refusals.go"
                path.write_text(mutate(path.read_text(encoding="utf-8"), old, new), encoding="utf-8")
                code, out = judge(mod)
                self.assertEqual(code, 1, f"the judge passed the mutant {new!r}: {out[-500:]}")

    def test_table_out_of_form(self):
        cases = [
            ("1.1\t1\tkey_rules\thttp\t400", "1.1\t1\tkey_rules\thttp\t4000"),
            ("1.1\t1\tkey_rules\thttp", "1.1\t1\tKeyRules\thttp"),
            ("1.1\t2\tbody_form\thttp", "1.1\t2\tkey_rules\thttp"),
            ("\tstart\texit 2\t-\t-\t-\trights file", "\tstart\texit 3\t-\t-\t-\trights file"),
            ("\tstart\texit 2\t-\t-\t-\trights file", "\tstart\texit 2\tbadkey\t-\t-\trights file"),
            ("\thttp\t409\tconflict\tindex,key?", "\thttp\t409\tconflict\tindex,index"),
            ("Retry-After: 1\t-\tP/01.1 N4; P/01.3", "Retry-After 1\t-\tP/01.1 N4; P/01.3"),
            ("key_rules\thttp\t400", "key_rules\tgate\t400"),
        ]
        for old, new in cases:
            with self.subTest(new=new):
                with self.assertRaises(GenError) as raised:
                    gen_refusals.Table(mutate(TABLE, old, new))
                if new.startswith("Retry-After 1"):
                    self.assertIn("header 'Retry-After 1'", str(raised.exception))

    def test_kit_part_refusals(self):
        import build_kit
        dst = Path(self.tmp.name) / "kit"
        manifest = build_kit.build(dst, "example.com/attempt/01-store", ["door", "refusals"])
        self.assertEqual(manifest["parts"], ["writecheck", "door", "refusals"])
        prov = manifest["provenance"]["refusals"]
        self.assertEqual(set(prov), {"form", "generator", "generators", "judge", "output", "judged"})
        root = HERE.parent.parent
        generators = {f["path"]: f["sha256"] for f in prov["generators"]}
        helper = "tools/normgen/tsv_input.py"
        self.assertEqual(generators[helper], hashlib.sha256((root / helper).read_bytes()).hexdigest())
        forms = {f["path"]: f["sha256"] for f in prov["form"]}
        table = gen_refusals.DEFAULT_TABLE.relative_to(root).as_posix()
        self.assertEqual(forms[table], hashlib.sha256((root / table).read_bytes()).hexdigest())
        proof = "Platform/common/data/cell-json-sha256.tsv"
        self.assertEqual(forms[proof], hashlib.sha256((root / proof).read_bytes()).hexdigest())
        mod = dst / "01-store"
        (mod / "go.mod").write_text("module example.com/attempt/01-store\n\ngo 1.22\n", encoding="utf-8")
        (mod / "internal/refusals/behaviour_test.go").write_text(BEHAVIOUR, encoding="utf-8")
        for cmd in (["go", "vet", "./..."], ["go", "test", "./internal/refusals/"]):
            done = subprocess.run(cmd, cwd=mod, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## Part `refusals`", (dst / "KIT.md").read_text(encoding="utf-8"))


class RefusalReportControls(unittest.TestCase):
    """Synthetic service controls; none is an executed semantic mutant."""

    @staticmethod
    def row(name="fixture"):
        return {"Chapter": "1.1", "Row": 1, "Name": name, "Surface": "http", "Code": 400,
                "Kind": "badrequest", "Fields": None, "Headers": None, "RetryAfter": False, "DynamicHeaders": None,
                "Log": None, "Words": None, "Norm": "fixture",
                "probes": [{"fields": None, "ints": [], "ops": ["Fixture"], "retry": False,
                            "body": '{"kind":"badrequest","error":"é"}\n',
                            "wire": [{"op": "Fixture", "requested": [], "headers": []}]}]}

    @classmethod
    def frame(cls, rows=None):
        rows = [cls.row()] if rows is None else rows
        return {"version": 1, "declared": len(rows), "completed": len(rows), "rows": rows}

    def test_complete_typed_frame_preserves_unicode_and_lf(self):
        frame = self.frame()
        raw = json.dumps(frame, ensure_ascii=False).encode()
        self.assertEqual(refusal_judge.read_report(raw), frame["rows"])
        self.assertEqual(refusal_judge.read_report(json.dumps(self.frame([]))), [])
        optional = self.row()
        optional["Fields"] = [{"Name": "index", "Optional": False}, {"Name": "key", "Optional": True}]
        optional["probes"] = [dict(optional["probes"][0], fields=["index"]),
                              dict(optional["probes"][0], fields=["index", "key"])]
        self.assertEqual(refusal_judge.read_report(json.dumps(self.frame([optional]))), [optional])

    def test_missing_extra_partial_empty_and_mistyped_frames_are_checking_errors(self):
        good = self.frame()
        bad = []
        for key in good:
            value = copy.deepcopy(good)
            del value[key]
            bad.append(value)
        for key, value in (("version", True), ("version", 2), ("declared", True), ("declared", 0),
                           ("completed", 1.0), ("completed", 0), ("rows", None), ("rows", [])):
            bad.append(dict(good, **{key: value}))
        bad += [dict(good, extra=1), dict(good, rows=good["rows"] * 2)]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(refusal_judge.CheckingError):
                refusal_judge.read_report(json.dumps(value))

    def test_row_probe_and_unicode_corruption_are_checking_errors(self):
        bad = []
        for key, value in (("Code", True), ("Row", 1.0), ("RetryAfter", 0),
                           ("Fields", {}), ("Headers", [["Connection"]]), ("Log", [1]),
                           ("Norm", "\ud800"), ("probes", [])):
            bad.append(dict(self.row(), **{key: value}))
        missing = self.row()
        del missing["Norm"]
        bad.append(missing)
        for key, value in (("body", 1), ("retry", 0), ("ops", [False]), ("fields", ["other"])):
            row = self.row()
            row["probes"][0][key] = value
            bad.append(row)
        row = self.row()
        row["probes"] *= 2
        bad.append(row)
        for row in bad:
            with self.subTest(row=row), self.assertRaises(refusal_judge.CheckingError):
                refusal_judge.read_report(json.dumps(self.frame([row])))
        raw = json.dumps(self.frame())
        self.assertEqual(raw.count('"version": 1'), 1)
        corrupt = [b"\xff", raw + "{}", raw[:-1],
                   raw.replace('"version": 1', '"version": 1, "version": 1', 1),
                   raw.replace('"Code": 400', '"Code": NaN', 1)]
        for value in corrupt:
            with self.subTest(raw=repr(value)), self.assertRaises(refusal_judge.CheckingError):
                refusal_judge.read_report(value)

    def test_process_compile_start_nonzero_and_parse_errors_never_return_rows(self):
        raw = json.dumps(self.frame()).encode()
        failures = [SimpleNamespace(returncode=1, stdout=raw, stderr=b"compile failure"),
                    SimpleNamespace(returncode=-9, stdout=raw, stderr=b""),
                    SimpleNamespace(returncode=0, stdout=raw, stderr=b"encoder diagnostic"),
                    SimpleNamespace(returncode=0, stdout=b"[]", stderr=b"")]
        with tempfile.TemporaryDirectory(prefix="refusal-service-control-") as tmp:
            for number, outcome in enumerate(failures):
                work = Path(tmp) / str(number)
                work.mkdir()
                with self.subTest(outcome=outcome), patch.object(subprocess, "run", return_value=outcome), \
                        self.assertRaises(refusal_judge.CheckingError):
                    refusal_judge.harness(work, work)
            for number, error in enumerate((OSError("cannot start"), subprocess.TimeoutExpired("go", 1)), 20):
                work = Path(tmp) / str(number)
                work.mkdir()
                with self.subTest(error=error), patch.object(subprocess, "run", side_effect=error), \
                        self.assertRaises(refusal_judge.CheckingError):
                    refusal_judge.harness(work, work)

    def test_main_checking_error_cannot_publish_a_semantic_report(self):
        with tempfile.TemporaryDirectory(prefix="refusal-main-control-") as tmp:
            output = Path(tmp) / "result.json"
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(refusal_judge.shutil, "which", return_value="go"), \
                    patch.object(refusal_judge, "harness", side_effect=refusal_judge.CheckingError("service error")), \
                    patch.object(refusal_judge, "expectations", side_effect=AssertionError("comparison reached")), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = refusal_judge.main(["--module-dir", tmp, "--json", str(output)])
            self.assertEqual(code, 2)
            self.assertIn("checking error", stderr.getvalue())
            self.assertNotIn("PASS", stdout.getvalue())
            self.assertFalse(output.exists())

    def test_complete_compiled_missing_or_extra_row_is_a_source_mismatch(self):
        header = "chapter\trow\tname\tsurface\tcode\tkind\tfields\theaders\tlog\tnorm\n"
        line = "1.1\t1\tfixture\thttp\t400\tbadrequest\t-\t-\t-\tfixture\n"
        with tempfile.TemporaryDirectory(prefix="refusal-semantic-control-") as tmp:
            table = Path(tmp) / "refusals.tsv"
            table.write_text(header + line + line.replace("\tfixture\thttp", "\tsecond\thttp"))
            output = Path(tmp) / "result.json"
            cohorts = (([self.row(), self.row("second")], 0), ([], 1), ([self.row()], 1),
                       ([self.row(), self.row("second"), self.row("extra")], 1))
            for observed, expected_exit in cohorts:
                complete = refusal_judge.read_report(json.dumps(self.frame(observed)))
                stdout, stderr = io.StringIO(), io.StringIO()
                with self.subTest(observed=len(observed)), patch.object(refusal_judge, "TABLE", table), \
                        patch.object(refusal_judge.shutil, "which", return_value="go"), \
                        patch.object(refusal_judge, "harness", return_value=complete), \
                        patch.object(refusal_judge, "expectations", return_value=[]), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = refusal_judge.main(["--module-dir", tmp, "--json", str(output)])
                self.assertEqual(code, expected_exit)
                self.assertEqual(stderr.getvalue(), "")
                result = normal_result(code, output.read_bytes())
                self.assertIn("catalogue second", {r["name"] for r in result["results"]})
                self.assertEqual(any(not r["ok"] for r in result["results"]), expected_exit == 1)

    def test_mutant_accounting_requires_a_nonempty_complete_normal_report(self):
        good = {"passed": 1, "total": 1, "verdict": "PASS", "results": [{"name": "case", "ok": True, "why": None}]}
        self.assertEqual(normal_result(0, json.dumps(good).encode()), good)
        mismatch = {"passed": 0, "total": 1, "verdict": "FAIL",
                    "results": [{"name": "case", "ok": False, "why": "named semantic disagreement"}]}
        self.assertEqual(normal_result(1, json.dumps(mismatch).encode()), mismatch)
        for value in (dict(good, total=2), dict(good, passed=True), dict(good, results=[]),
                      dict(good, results=good["results"] * 2, total=2, passed=2),
                      {"passed": 0, "total": 0, "verdict": "FAIL", "results": []}):
            with self.subTest(value=value), self.assertRaises(refusal_judge.CheckingError):
                normal_result(1, json.dumps(value).encode())
        with self.assertRaises(refusal_judge.CheckingError):
            normal_result(1, json.dumps(good).encode())


class Z21RefusalSource(unittest.TestCase):
    """Source-derived expectations; an external bounded run may bind source_root to its immutable Source input."""

    source_root = HERE.parent.parent
    names = ("input_timeout", "copy_method", "copy_admin_only", "copy_snapshot_unavailable")

    def test_new_causes_are_read_from_actual_source_without_a_numeric_oracle(self):
        table = self.source_root / "Platform/01-store/forms/refusals.tsv"
        raw = [x for x in table.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
        source = list(csv.DictReader(raw, delimiter="\t", quoting=csv.QUOTE_NONE))
        expected = {r["name"]: r for r in source}
        actual = {r["name"]: r for r in refusal_judge.read_table(table)}
        self.assertTrue(set(self.names) <= set(expected), "the frozen Source must contain all four named causes")
        self.assertEqual(list(actual), list(expected))
        for name in self.names:
            r, g = expected[name], actual[name]
            with self.subTest(name=name):
                self.assertEqual(g["code_n"], int(r["code"]))
                self.assertEqual((g["chapter"], g["row"], g["kind"], g["surface"]),
                                 (r["chapter"], r["row"], r["kind"], r["surface"]))
                headers = [] if r["headers"] == "-" else [h.split(": ", 1) for h in r["headers"].split(";")]
                self.assertEqual(g["header_pairs"], headers)
                self.assertEqual(g["norm"], r["norm"])

    def test_source_shape_failures_do_not_become_empty_catalogues(self):
        header = "chapter\trow\tname\tsurface\tcode\tkind\tfields\theaders\tlog\tnorm\n"
        row = "1.1\t1\tfixture\thttp\t400\tbadrequest\t-\tConnection: close\t-\tfixture\n"
        corrupt = [header, header + row + row, (header + row).replace("\t400\t", "\tTrue\t"),
                   (header + row).replace("Connection: close", "Connection close"),
                   (header + row).replace("\t-\tConnection", "\tindex,index\tConnection"),
                   (header + row).replace("\tfixture\n", "\tfixture\textra\n")]
        with tempfile.TemporaryDirectory(prefix="refusal-source-control-") as tmp:
            table = Path(tmp) / "refusals.tsv"
            for text in corrupt:
                table.write_text(text)
                with self.subTest(text=text), self.assertRaises(refusal_judge.CheckingError):
                    refusal_judge.read_table(table)


class Z21RefusalCompiled(unittest.TestCase):
    """The existing private service reads real generated rows; Source remains the independent oracle."""
    source_root = HERE.parent.parent
    code_root = HERE.parent.parent

    @classmethod
    def setUpClass(cls):
        from test_gen_core import z21_ready_p01
        cls.output = output_lesson.output_root()
        cls.output_receipt = os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV)
        cls.ready = z21_ready_p01(cls.output, cls.source_root, cls.code_root,
                                 expected_manifest_sha256=cls.output_receipt)
        cls.rows = refusal_judge.read_table(cls.source_root / "Platform/01-store/forms/refusals.tsv")
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-refusals-")

    @classmethod
    def tearDownClass(cls):
        from test_gen_core import z21_ready_p01
        cls.tmp.cleanup()
        z21_ready_p01(cls.output, cls.source_root, cls.code_root, expected_manifest_sha256=cls.output_receipt)

    def module(self, name):
        path = Path(self.tmp.name) / name
        shutil.copytree(self.ready["p01-1"] / "go", path)
        return path

    def compare(self, module):
        report = module / "z21_judge.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(refusal_judge, "TABLE", self.source_root / "Platform/01-store/forms/refusals.tsv"), \
                patch.object(refusal_judge, "ACCEPTANCE", self.source_root / "Platform/01-store/acceptance"), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = refusal_judge.main(["--module-dir", str(module), "--json", str(report)])
        if code not in (0, 1) or stderr.getvalue():
            raise refusal_judge.CheckingError(stderr.getvalue() or f"checking exit {code}")
        result = normal_result(code, report.read_bytes())
        self.assertTrue({"catalogue " + r["name"] for r in self.rows} <= {r["name"] for r in result["results"]})
        return code, [r["name"] for r in result["results"] if not r["ok"]]

    def test_source_new_causes_each_reject_code_kind_and_header_mutants(self):
        self.assertEqual(self.compare(self.module("normal")), (0, []))
        source = {r["name"]: r for r in self.rows}
        mutations = []
        for name in Z21RefusalSource.names:
            row = source[name]
            prefix = f'Name: "{name}", Surface: "http", Code: {row["code_n"]}, Kind: "{row["kind"]}"'
            mutations.append((name + "-code", prefix, prefix.replace(f'Code: {row["code_n"]}', f'Code: {row["code_n"] + 1}')))
            mutations.append((name + "-kind", prefix, prefix.replace(f'Kind: "{row["kind"]}"', 'Kind: "wrong"')))
            if row["header_pairs"]:
                pairs = ", ".join("{" + json.dumps(k) + ", " + json.dumps(v) + "}" for k, v in row["header_pairs"])
                before = prefix + ", Fields: nil, Headers: [][2]string{" + pairs + "}"
                mutations.append((name + "-header", before, prefix + ", Fields: nil, Headers: nil"))
        for name, before, after in mutations:
            with self.subTest(mutant=name):
                module = self.module(name)
                path = module / "refusals/refusals.go"
                text = path.read_text()
                self.assertEqual(text.count(before), 1)
                path.write_text(text.replace(before, after, 1), encoding="utf-8")
                code, mismatches = self.compare(module)
                self.assertEqual(code, 1, "surviving Source mutant " + name)
                self.assertTrue(mismatches)

    def test_complete_compiled_catalogue_missing_and_zero_are_semantic_mismatches(self):
        self.assertEqual(self.compare(self.module("catalogue-normal")), (0, []))
        for name, body in (("missing", None), ("zero", "")):
            module = self.module("catalogue-" + name)
            path = module / "refusals/refusals.go"
            text = path.read_text()
            matches = list(re.finditer(r"var All = \[\]\*Spec\{([^\n]*)\}", text))
            self.assertEqual(len(matches), 1)
            match = matches[0]
            new = match[1].replace(", InputTimeout,", ",", 1) if body is None else body
            self.assertNotEqual(new, match[1])
            path.write_text(text[:match.start(1)] + new + text[match.end(1):], encoding="utf-8")
            code, mismatches = self.compare(module)
            self.assertEqual(code, 1)
            self.assertIn("catalogue input_timeout", mismatches)

    def test_old_status_optional_field_retry_kind_and_start_controls_still_fail_semantically(self):
        self.assertEqual(self.compare(self.module("old-controls-normal")), (0, []))
        cases = (
            ('Name: "cas_mismatch", Surface: "http", Code: 409', 'Name: "cas_mismatch", Surface: "http", Code: 410'),
            ('Fields: []Field{{"index", false}, {"key", true}}', 'Fields: []Field{{"index", false}}'),
            ('Name: "connection_limit", Surface: "http", Code: 503, Kind: "unavailable", Fields: nil, Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: true',
             'Name: "connection_limit", Surface: "http", Code: 503, Kind: "unavailable", Fields: nil, Headers: [][2]string{{"Retry-After", "1"}}, RetryAfter: false'),
            ('"guard_mismatch", Surface: "http", Code: 412, Kind: "guard"', '"guard_mismatch", Surface: "http", Code: 412, Kind: "guards"'),
            ('Name: "start_flags", Surface: "start", Code: 2', 'Name: "start_flags", Surface: "start", Code: 1'),
        )
        for number, (before, after) in enumerate(cases):
            with self.subTest(legacy_control=number):
                module = self.module("old-control-" + str(number))
                path = module / "refusals/refusals.go"
                text = path.read_text()
                self.assertEqual(text.count(before), 1)
                path.write_text(text.replace(before, after, 1), encoding="utf-8")
                code, mismatches = self.compare(module)
                self.assertEqual(code, 1)
                self.assertTrue(mismatches, "old control survived")

    def test_actual_compile_and_encoder_errors_are_checking_errors(self):
        module = self.module("compile-error")
        path = module / "refusals/refusals.go"
        path.write_text(path.read_text() + "\nnot valid Go\n")
        with self.assertRaises(refusal_judge.CheckingError):
            self.compare(module)
        # Execute the unchanged private encoder with a real failing output descriptor.
        module = self.module("encoder-error")
        work = Path(self.tmp.name) / "encoder-service"
        work.mkdir()
        shutil.copy(HERE / "refusals/harness/main.go", work / "main.go")
        (work / "go.mod").write_text("module normgen/refusalharness\n\ngo 1.22\n\nrequire normgen/p01-1 v0.0.0\n\n"
                                     f"replace normgen/p01-1 => {module}\n", encoding="utf-8")
        with open("/dev/full", "wb", buffering=0) as failing:
            done = subprocess.run(["go", "run", "."], cwd=work, stdout=failing, stderr=subprocess.PIPE, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(b"refusal readback encoding:", done.stderr)
        unused = Path(self.tmp.name) / "unused-readback"
        unused.mkdir()
        with patch.object(refusal_judge.subprocess, "run", return_value=SimpleNamespace(
                returncode=done.returncode, stdout=b"", stderr=done.stderr)):
            with self.assertRaises(refusal_judge.CheckingError):
                refusal_judge.harness(module, unused)


if __name__ == "__main__":
    unittest.main()
