"""Test command-based flags from operator-commands.tsv (P/02). Require cmdflag_judge PASS on output and FAIL for short-prefix, exponent-number, missing-required, unbounded-positionals and duplicate-option mutants. P/01 keeps its existing parser without a command form."""
import lesson as output_lesson
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
P02 = "02-installer"


def run_judge(module_dir):
    env = dict(os.environ, NORMGEN_LESSON=P02)
    return subprocess.run([sys.executable, str(HERE / "cmdflag_judge.py"), "--module-dir", str(module_dir)],
                          capture_output=True, text=True, env=env)


@unittest.skipUnless((HERE.parent.parent / "Platform/02-installer/forms/operator-commands.tsv").is_file(), "no P/02 forms")
class CommandFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        cls.tmp = tempfile.TemporaryDirectory(prefix="cmdflags-")
        cls.out = Path(cls.tmp.name) / "out"
        env = dict(os.environ, NORMGEN_LESSON=P02)
        done = subprocess.run([sys.executable, str(HERE / "gen_flags.py"), str(HERE.parent.parent / "Platform/02-installer/forms/daemon-flags.tsv"),
                               str(cls.out)], capture_output=True, text=True, env=env)
        assert done.returncode == 0, done.stderr
        cls.mod = cls.out / "go"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        kept = output_lesson.output_root() / 'p02/go/flags/flags.go'
        self.assertEqual((self.mod / "flags/flags.go").read_bytes(), kept.read_bytes(), "run gen_flags.py --lesson 02-installer")

    def test_judge_pass(self):
        done = run_judge(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PASS", done.stdout)

    def test_vet(self):
        env = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
        done = subprocess.run(["go", "vet", "./flags/"], cwd=self.mod, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)

    def mutant(self, old, new):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        f = t / "go/flags/flags.go"
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text)
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        return run_judge(t / "go")

    def test_mutants_killed(self):
        for old, new, why in (
                # Shortest-prefix selection is equivalent here: one process has no nested prefixes.
                ("if argv[k] != w {", "if k == 0 && argv[k] != w {", "only the first word of the prefix"),
                ("`^-?(0|[1-9][0-9]*)(\\.[0-9]+)?$`", "`^-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][0-9]+)?$`", "exponent"),
                ("&& isTrue(required", "&& false && isTrue(required", "required CEL ignored"),
                ("(c.Max >= 0 && len(fl.Args) > c.Max)", "false", "max positionals"),
                ("\t\tif fl.Given[name] {\n\t\t\treturn nil, refuse(name, \"the option is repeated\")",
                 "\t\tif false {\n\t\t\treturn nil, refuse(name, \"the option is repeated\")", "repeat")):
            done = self.mutant(old, new)
            self.assertNotEqual(done.returncode, 0, f"mutant survived: {why}\n{done.stdout[-500:]}")


if __name__ == "__main__":
    unittest.main()
