"""Тесты части refusals уроков P/03, P/04 (gen_refusals.py, режим урока без двери; ADR-0125 доп. (5)): out свежий;
судья refusal_judge.py — PASS; мутанты выхода в новых проекциях (поля и заголовки ответа импортированной двери у peer, word — названные исходы и ячейка,
глава урока одной главой) — FAIL судьи; форма вне грамматики (fields/headers не у peer) — отказ генератора."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04", "05-resource": "p05"}
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
        }
        for (lesson, name), text in muts.items():
            with self.subTest(mutant=name):
                base = {"03-worker": src, "04-controller": p04, "05-resource": p05}[lesson]
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


if __name__ == "__main__":
    unittest.main()
