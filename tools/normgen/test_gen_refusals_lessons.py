"""Test P/03/P/04 refusal projections: freshness, judge PASS, and FAIL for imported peer body/header, word-token/cell and single-chapter metadata mutants. Reject fields/headers outside peer grammar."""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05", "06-console": "p06", "09-agent": "p09"}
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def judge(lesson, mod):
    return subprocess.run([sys.executable, str(HERE / "refusal_judge.py"), "--lesson", lesson, "--module-dir", str(mod)],
                          capture_output=True, text=True, env=ENV)


class Refusals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="refusals-lessons-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gen(self, lesson, out, table=None):
        table = table or ROOT / "Platform" / lesson / "forms/refusals.tsv"
        return subprocess.run([sys.executable, str(HERE / "gen_refusals.py"), "--lesson", lesson, str(table), str(out)],
                              capture_output=True, text=True)

    def test_fresh_and_judged(self):
        for lesson, slug in LESSONS.items():
            out = self.tmp / f"fresh-{slug}"
            done = self.gen(lesson, out)
            self.assertEqual(done.returncode, 0, done.stderr)
            kept = HERE / "out" / slug / "go/refusals/refusals.go"
            self.assertEqual(kept.read_bytes(), (out / "go/refusals/refusals.go").read_bytes(), f"{kept} is stale")
            done = judge(lesson, HERE / "out" / slug / "go")
            self.assertEqual(done.returncode, 0, done.stdout[-1500:])

    def test_mutants(self):
        src = (HERE / "out/p03/go/refusals/refusals.go").read_text(encoding="utf-8")
        p04 = (HERE / "out/p04/go/refusals/refusals.go").read_text(encoding="utf-8")
        p05 = (HERE / "out/p05/go/refusals/refusals.go").read_text(encoding="utf-8")
        p06 = (HERE / "out/p06/go/refusals/refusals.go").read_text(encoding="utf-8")
        muts = {
            ("03-worker", "fields"): src.replace('Fields: []string{"error"}', "Fields: nil", 1),
            ("03-worker", "headers"): src.replace('{"Retry-After", "1"}', '{"Retry-After", "2"}', 1),
            ("03-worker", "named"): src.replace('Named: []string{"wrong_kind", "wrong_audience"}',
                                                'Named: []string{"wrong_kind"}', 1),
            ("03-worker", "word-cell"): src.replace('WordCell: "— (log)"', 'WordCell: "-"', 1),
            ("03-worker", "word"): src.replace('Word: "NameOnAnotherBox"', 'Word: ""', 1),
            ("04-controller", "chapter"): p04.replace('Chapter: "4", Row: 3,', 'Chapter: "4.1", Row: 3,', 1),
            ("05-resource", "response"): p05.replace('Response: "ResourceDenied"', 'Response: "ResourceError"', 1),
            ("05-resource", "http-status"): p05.replace('Status: 206,', 'Status: 200,', 1),
            ("06-console", "word-phrase"): p06.replace('Word: "no such book shown"', 'Word: ""', 1),
            ("06-console", "response-peer"): p06.replace('Response: "DomainRefusal"', 'Response: "Fault"', 1),
        }
        for (lesson, name), text in muts.items():
            with self.subTest(mutant=name):
                base = {"03-worker": src, "04-controller": p04, "05-resource": p05, "06-console": p06}[lesson]
                self.assertNotEqual(text, base, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(HERE / "out" / LESSONS[lesson] / "go", mod)
                (mod / "refusals/refusals.go").write_text(text, encoding="utf-8")
                done = judge(lesson, mod)
                self.assertEqual(done.returncode, 1, f"{name} survives: {done.stdout[-500:]}")

    def test_refusals(self):
        text = (ROOT / "Platform/03-worker/forms/refusals.tsv").read_text(encoding="utf-8")
        bad = {"fields-at-call": text.replace("\tslot_foreign_box\tcall\t-\t-\t-\t", "\tslot_foreign_box\tcall\t-\t-\terror\t", 1),
               "headers-at-call": text.replace("\tslot_guard\tcall\t-\t-\t-\t-\t", "\tslot_guard\tcall\t-\t-\t-\tRetry-After: 1\t", 1),
               "kind": text.replace("\tslot_guard\tcall\t-\t-\t", "\tslot_guard\tcall\t-\tbad\t", 1)}
        for name, t in bad.items():
            with self.subTest(form=name):
                self.assertNotEqual(t, text, f"{name}: the change does not apply")
                p = self.tmp / f"{name}.tsv"
                p.write_text(t, encoding="utf-8")
                done = self.gen("03-worker", self.tmp / f"out-{name}", p)
                self.assertNotEqual(done.returncode, 0, f"{name}: accepted")

    def test_p09_stored_outcome_has_no_http_body(self):
        source = ROOT / "Platform/09-agent/forms/refusals.tsv"
        rows = list(csv.DictReader([s for s in source.read_text(encoding="utf-8").split("\n")
                                    if s and not s.startswith("#")], delimiter="\t"))
        row = next(r for r in rows if r["name"] == "agent_edit_conflict")
        self.assertEqual((row["surface"], row["code"], row["response_schema"]), ("call", "412", "-"))
        src = (HERE / "out/p09/go/refusals/refusals.go").read_text(encoding="utf-8")
        declaration = next(line for line in src.split("\n") if line.startswith("var AgentEditConflict = "))
        self.assertIn('Surface: "call", Exit: -1, AnyNonZero: false, Status: 412,', declaration)
        self.assertIn('Response: ""', declaration)
        schema = next(r["response_schema"] for r in rows if r["response_schema"] != "-")
        for field, value in [("fields", "error"), ("headers", "Retry-After: 1"),
                             ("response_schema", schema), ("surface", "cli"), ("surface", "start")]:
            with self.subTest(field=field):
                changed = [dict(r) for r in rows]
                next(r for r in changed if r["name"] == row["name"])[field] = value
                path = self.tmp / f"p09-call-{field}.tsv"
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                    writer.writeheader()
                    writer.writerows(changed)
                done = self.gen("09-agent", self.tmp / ("bad-p09-" + field), path)
                self.assertNotEqual(done.returncode, 0, done.stderr)

    def test_p09_call_code_boundaries(self):
        source = ROOT / "Platform/09-agent/forms/refusals.tsv"
        rows = list(csv.DictReader([s for s in source.read_text(encoding="utf-8").split("\n")
                                    if s and not s.startswith("#")], delimiter="\t"))
        row = next(r for r in rows if r["name"] == "agent_edit_conflict")
        valid = [100, 199, 200, 299, 300, 399, 400, 499, 500, 599]
        path, out = self.tmp / "p09-code-bounds.tsv", self.tmp / "p09-code-bounds"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(dict(row, name="edge_" + str(n), code=str(n)) for n in valid)
        done = self.gen("09-agent", out, path)
        self.assertEqual(done.returncode, 0, done.stderr)
        generated = (out / "go/refusals/refusals.go").read_text(encoding="utf-8")
        for n in valid:
            declaration = next(line for line in generated.split("\n") if line.startswith(f"var Edge{n} = "))
            self.assertIn(f"Status: {n},", declaration)
        for code in ["0", "99", "600", "999", "0100", "+100", "100.0"]:
            with self.subTest(code=code):
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                    writer.writeheader()
                    writer.writerow(dict(row, code=code))
                done = self.gen("09-agent", out, path)
                self.assertNotEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
