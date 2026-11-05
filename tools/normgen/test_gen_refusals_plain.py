"""Тесты каталога отказов урока без двери (P/02: refusals.tsv на 15 колонок; ADR-0125 доп. (5)): out свежий, судья
refusal_judge PASS на выходе и FAIL на мутантах пакета (код выхода, word, «exit !0», фрагмент лога); P/01 — прежний
каталог с HTTP (его тесты — test_gen_refusals.py)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
P02 = "02-installer"
ENV = dict(os.environ, NORMGEN_LESSON=P02)


def judge(module_dir):
    return subprocess.run([sys.executable, str(HERE / "refusal_judge.py"), "--module-dir", str(module_dir)],
                          capture_output=True, text=True, env=ENV)


@unittest.skipUnless((HERE.parent.parent / "Platform/02-installer/forms/refusals.tsv").is_file(), "no P/02 forms")
class Plain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="refplain-")
        cls.out = Path(cls.tmp.name) / "out"
        done = subprocess.run([sys.executable, str(HERE / "gen_refusals.py"),
                               str(HERE.parent.parent / "Platform/02-installer/forms/refusals.tsv"), str(cls.out)],
                              capture_output=True, text=True, env=ENV)
        assert done.returncode == 0, done.stderr
        cls.mod = cls.out / "go"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_fresh(self):
        self.assertEqual((self.mod / "refusals/refusals.go").read_bytes(),
                         (HERE / "out/p02/go/refusals/refusals.go").read_bytes(), "run gen_refusals.py --lesson 02-installer")

    def test_judge_pass(self):
        done = judge(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_no_prose(self):
        """Четыре колонки прозы (cause, outcome, diagnostic, caller) в код не идут."""
        text = (self.mod / "refusals/refusals.go").read_text(encoding="utf-8")
        for word in ("Cause", "Outcome", "Diagnostic", "Caller"):
            self.assertNotIn(word + " ", text)

    def mutant(self, old, new):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        f = t / "go/refusals/refusals.go"
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text)
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        return judge(t / "go")

    def test_mutants_killed(self):
        for old, new, why in (
                ('Name: "secrets_unknown_family", Surface: "cli", Exit: 1,', 'Name: "secrets_unknown_family", Surface: "cli", Exit: 2,', "exit code"),
                ('Word: "unknown-row-form"', 'Word: ""', "word"),
                ('Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: true,',
                 'Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: false,', "exit !0"),
                ('Words: []string{"manifest changed, restart"}', 'Words: []string{"manifest changed"}', "log fragment")):
            done = self.mutant(old, new)
            self.assertNotEqual(done.returncode, 0, f"mutant survived: {why}\n{done.stdout[-400:]}")


if __name__ == "__main__":
    unittest.main()
