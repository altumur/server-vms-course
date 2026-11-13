"""Test P/02's15-column refusal catalog: freshness, judge PASS and code/word/exit!0/log-fragment mutants FAIL. P/01 retains its HTTP catalog tests."""
import lesson as output_lesson
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        self.assertEqual((self.mod / "refusals/refusals.go").read_bytes(),
                         (output_lesson.output_root() / 'p02/go/refusals/refusals.go').read_bytes(), "run gen_refusals.py --lesson 02-installer")

    def test_judge_pass(self):
        done = judge(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_no_prose(self):
        """Never emit the four prose columns cause, outcome, diagnostic, caller into code."""
        text = (self.mod / "refusals/refusals.go").read_text(encoding="utf-8")
        for word in ("Cause", "Outcome", "Diagnostic", "Caller"):
            self.assertNotIn(word + " ", text)

    def test_review_restart_and_fixed_exit_catalogue(self):
        """Independent Go probes of the review's restart/corruption split and fixed/nonzero exit codes."""
        probe = self.mod / "refusals/review_test.go"
        probe.write_text('''package refusals
import "testing"
func TestReviewCatalogue(t *testing.T) {
    for _, want := range []struct{name, chapter string; row, code int; any bool}{
        {"view_reader_not_published", "2.2", 3, 1, false},
        {"view_reader_unreadable", "2.2", 3, 2, false},
        {"manifest_start_unavailable", "2.3", 1, 1, false},
        {"manifest_start", "2.3", 1, 2, false},
        {"process_environment", "2.4", 8, 2, false},
        {"process_budget_rights", "2.4", 8, 1, true},
        {"address_without_tls", "2.4", 17, 2, false},
        {"install_domain_server", "2.4", 22, 2, false},
    } { t.Run(want.name, func(t *testing.T) {
        got := ByName(want.name)
        if got == nil { t.Fatal("missing catalogue condition") }
        code, ok := got.ExitCode()
        if got.Chapter != want.chapter || got.Row != want.row || code != want.code || !ok || got.AnyNonZero != want.any {
            t.Fatalf("%+v exit %d,%v", got, code, ok)
        }
    }) }
    for name, word := range map[string]string{"view_reader_not_published":"not published", "view_reader_unreadable":"corruption"} {
        got := ByName(name)
        if len(got.Log) != 1 || got.Log[0] != "key" || len(got.Words) != 1 || got.Words[0] != word {
            t.Fatalf("diagnostic %s: %+v", name, got)
        }
    }
}
''')
        try:
            done = subprocess.run(["go", "test", "-count=1", "./refusals/"], cwd=self.mod,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        finally:
            probe.unlink()

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
                ('Word: "`unknown-row-form`"', 'Word: ""', "word"),
                ('Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: true,',
                 'Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: false,', "exit !0"),
                ('Words: []string{"manifest changed, restart"}', 'Words: []string{"manifest changed"}', "log fragment")):
            done = self.mutant(old, new)
            self.assertNotEqual(done.returncode, 0, f"mutant survived: {why}\n{done.stdout[-400:]}")


if __name__ == "__main__":
    unittest.main()
