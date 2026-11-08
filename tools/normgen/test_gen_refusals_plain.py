"""Test P/02's15-column refusal catalog: freshness, judge PASS and code/word/exit!0/log-fragment mutants FAIL. P/01 retains its HTTP catalog tests."""
import lesson as output_lesson
import csv
import json
from unittest.mock import patch
import refusal_judge as independent
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
    return subprocess.run([sys.executable, "-B", str(HERE / "refusal_judge.py"), "--module-dir", str(module_dir)],
                          capture_output=True, text=True, env=ENV)


@unittest.skipUnless((HERE.parent.parent / "Platform/02-installer/forms/refusals.tsv").is_file(), "no P/02 forms")
class Plain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        producer = Path(os.environ["NORMGEN_PRODUCER_ROOT"])
        prepared = output_lesson.ready_outputs(source_root=producer, code_root=producer,
                                               profiles=("p02", "p04", "p06"))
        cls.tmp = tempfile.TemporaryDirectory(prefix="refplain-")
        cls.mod = prepared['p02'] / 'go'
        cls.prepared = prepared
        source = HERE.parent.parent / 'Platform/02-installer/forms/refusals.tsv'
        cls.rows = independent.read_plain_source(source)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_fresh(self):
        # Prepared bytes were verified against a held receipt; expectation comes only from Source.
        self.assertEqual(len(self.rows), 52)
        self.assertEqual(len({r['name'] for r in self.rows}), 52)

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

    def mutant(self, old, new, name=None):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        f = t / "go/refusals/refusals.go"
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text)
        if name is None:
            text = text.replace(old, new, 1)
        else:
            line = next(line for line in text.split('\n') if 'Name: "' + name + '"' in line)
            self.assertEqual(line.count(old), 1)
            text = text.replace(line, line.replace(old, new, 1), 1)
        f.write_text(text, encoding="utf-8")
        return judge(t / "go")

    def test_mutants_killed(self):
        for old, new, why in (
                ('Name: "secrets_unknown_family", Surface: "cli", Exit: 1,', 'Name: "secrets_unknown_family", Surface: "cli", Exit: 2,', "exit code"),
                ('Word: "unknown-row-form"', 'Word: ""', "word"),
                ('Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: true,',
                 'Name: "install_partial", Surface: "cli", Exit: -1, AnyNonZero: false,', "exit !0"),
                ('Words: []string{"manifest changed, restart"}', 'Words: []string{"manifest changed"}', "log fragment")):
            done = self.mutant(old, new)
            self.assertEqual(done.returncode, 1, f"not a semantic kill: {why}\n{done.stdout}\n{done.stderr}")

    def test_common_p02_nine_words_and_wordcells(self):
        fixed = {r['name']: r['word'][1:-1] for r in self.rows if r['word'].startswith('`')}
        self.assertEqual(len(fixed), 9)
        done = judge(self.mod)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # Individually changing every fixed Source word must be a semantic disagreement.
        for name, word in fixed.items():
            with self.subTest(name=name):
                done = self.mutant('Word: ' + json.dumps(word), 'Word: "wrong-fixed-word"', name=name)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_common_p02_projection_and_cell_mutants(self):
        for old, new in [('WordCell: "`unknown-row-form`"', 'WordCell: "unknown-row-form"'),
                         ('Fields: nil', 'Fields: []string{"invented"}'),
                         ('Headers: nil', 'Headers: [][2]string{{"Retry-After", "1"}}'),
                         ('Named: nil', 'Named: []string{"invented"}')]:
            with self.subTest(old=old):
                done = self.mutant(old, new)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_common_p04_neighbor_positive(self):
        done = subprocess.run([sys.executable, '-B', str(HERE / 'refusal_judge.py'), '--lesson', '04-controller',
                               '--module-dir', str(self.prepared['p04'] / 'go')], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_plain_strict_transport_changed_layout(self):
        keys = 'Chapter Row Name Surface Exit AnyNonZero Status Word Log Words Norm Fields Headers Named WordCell'.split()
        row = dict.fromkeys(keys, '')
        row.update(Row=1, Exit=-1, Status=0, AnyNonZero=False, Name='a', Log=None, Words=None,
                   Fields=None, Headers=None, Named=None)
        frame = dict(version=1, declared=1, completed=1, rows=[row])
        self.assertEqual(independent.read_plain_report(json.dumps(frame), self.rows), [row])
        bad = [dict(frame, rows=None), dict(frame, completed=0), dict(frame, declared=2),
               dict(frame, version=True), dict(frame, declared=0, completed=0, rows=[]),
               dict(frame, rows=[dict(row, Extra='x')]), dict(frame, rows=[dict(row, Row=True)]),
               dict(frame, rows=[dict(row, Fields='error')]),
               dict(frame, declared=2, completed=2, rows=[row, row])]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(independent.CheckingError):
                independent.read_plain_report(json.dumps(value), self.rows)
        for raw in (b'\xff', json.dumps(frame) + '{}', '{"version":1,"version":1}',
                    json.dumps(frame).replace('"Name": "a"', '"Name": "\\ud800"')):
            with self.subTest(raw=raw), self.assertRaises(independent.CheckingError):
                independent.read_plain_report(raw, self.rows)

    def test_compiled_consistent_missing_row_is_semantic(self):
        text = (self.mod / 'refusals/refusals.go').read_text()
        import re
        match = re.search(r'var All = \[\]\*Spec\{([^,]+),', text)
        self.assertIsNotNone(match)
        done = self.mutant(match.group(0), 'var All = []*Spec{')
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_compile_failure_is_checking_error(self):
        done = self.mutant('package refusals', 'package refusals\nTHIS IS NOT GO')
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn('checking error', done.stderr)

    def test_plain_process_and_parse_errors_never_semantic_kills(self):
        from types import SimpleNamespace
        from contextlib import redirect_stderr
        import io
        source = HERE.parent.parent / 'Platform/02-installer/forms/refusals.tsv'
        subject = SimpleNamespace(go_module='normgen/p02', code='P/02')
        process_cases = [subprocess.CompletedProcess(['go', 'run', '.'], 3, b'', b'process failed'),
                         subprocess.CompletedProcess(['go', 'run', '.'], 0, b'[]', b''),
                         subprocess.CompletedProcess(['go', 'run', '.'], 0, b'{}', b'warning'),
                         subprocess.CompletedProcess(['go', 'run', '.'], 0, b'\xff', b'')]
        with patch.object(independent, 'TABLE', source), patch.object(independent, 'L', subject):
            for observation in process_cases:
                with self.subTest(observation=observation), patch.object(independent.subprocess, 'run', return_value=observation):
                    with redirect_stderr(io.StringIO()) as error:
                        self.assertEqual(independent.main(['--module-dir', str(self.mod)]), 2)
                    self.assertIn('checking error', error.getvalue())
            for failure in (OSError('cannot start'), subprocess.TimeoutExpired(['go', 'run', '.'], 1)):
                with self.subTest(failure=failure), patch.object(independent.subprocess, 'run', side_effect=failure):
                    with redirect_stderr(io.StringIO()) as error:
                        self.assertEqual(independent.main(['--module-dir', str(self.mod)]), 2)
                    self.assertIn('checking error', error.getvalue())


if __name__ == "__main__":
    unittest.main()
