"""Focused controls for the optional solver, never imported by check_spec."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import solver_run as runner


SAT = b"(declare-const p Bool)\n(assert p)\n(check-sat)\n"
UNSAT = b"(declare-const p Bool)\n(assert (! p :named yes))\n(assert (! (not p) :named no))\n(check-sat)\n"


class OptionalSolverControls(unittest.TestCase):
    def test_actual_sat_model_and_tracked_unsat_core(self):
        sat = runner.solve_encoding(SAT)
        self.assertEqual(sat["result"], "sat")
        self.assertIn("define-fun p", sat["model_smt2"])
        self.assertNotIn("unsat_core", sat)
        unsat = runner.solve_encoding(UNSAT)
        self.assertEqual(unsat["result"], "unsat")
        self.assertEqual(unsat["unsat_core"], ["no", "yes"])
        self.assertEqual(unsat["assertions"], 2)
        self.assertEqual(unsat["tracked_assertions"], 2)
        self.assertNotIn("model_smt2", unsat)

    def test_direct_python_model_with_parameterized_define_fun(self):
        encoding = b"""(declare-const x Int)
(define-fun next ((n Int)) Int (+ n 1))
(assert (= (next x) 3))
(check-sat)
"""
        result = runner.solve_encoding(encoding)
        self.assertEqual(result["result"], "sat")
        self.assertIn("define-fun x", result["model_smt2"])
        self.assertIn("2", result["model_smt2"])

    def test_actual_unknown_is_not_sat_or_unsat(self):
        result = runner.solve_encoding(UNSAT, resource_limit=1)
        self.assertEqual(result["result"], "unknown")
        self.assertTrue(result["reason_unknown"])
        self.assertNotIn("model_smt2", result)
        self.assertNotIn("unsat_core", result)
        self.assertEqual(result["limits"]["resource_limit"], 1)

    def test_only_one_declarative_query_no_state_or_file_commands(self):
        for raw in (b'(include "elsewhere.smt2")\n(assert true)',
                    b'(set-option :trace_file_name "elsewhere")\n(assert true)',
                    b'(assert true)(push 1)(assert false)',
                    b'(assert true)(check-sat)(assert false)',
                    b'(assert true)(check-sat)(check-sat)',
                    b'(assert true)(check-sat extra)',
                    b'(declare-const p Bool)', b'(assert true', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(runner.InputError):
                runner.solve_encoding(raw)
        harmless = b'; (include "not-a-command")\n(assert (= "(include) :named q" "(include) :named q"))\n'
        self.assertEqual(runner.solve_encoding(harmless)["result"], "sat")

    def test_named_tracking_cannot_change_the_original_formula(self):
        for raw in (b'(declare-const p Bool)(assert (! p :named p))',
                    b'(assert (! true :named same))(assert (! false :named same))',
                    b'(assert (! true :named a))(assert a)'):
            with self.subTest(raw=raw), self.assertRaises(runner.InputError):
                runner.solve_encoding(raw)
        quoted = b'(assert (! false :named |a label|))'
        self.assertEqual(runner.solve_encoding(quoted)["unsat_core"], ["a label"])

    def test_native_syntax_failure_and_caller_limits_remain_errors(self):
        with self.assertRaises(runner.InputError):
            runner.solve_encoding(b'(assert missing)')
        for kwargs in ({"timeout_ms": -1}, {"resource_limit": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(runner.InputError):
                runner.solve_encoding(SAT, **kwargs)

    def test_exact_optional_dependency_pin_is_checked(self):
        z3, info = runner.load_z3()
        self.assertEqual(info["package_version"], "4.16.0.0")
        self.assertEqual(tuple(z3.get_version()), (4, 16, 0, 0))
        with tempfile.TemporaryDirectory() as temp:
            pin = Path(temp) / "requirements.txt"
            pin.write_text("z3-solver==0.0.0.0\n")
            with patch.object(runner, "PIN_FILE", pin), self.assertRaisesRegex(runner.DependencyError, "version differs"):
                runner.load_z3()


class HashBindingControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="form-smt-binding-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "source"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        self.form = self.repo / "form.tsv"
        self.form.write_bytes(b"when\toutcome\nflag\trefused\n")
        self.git("add", "--", "form.tsv")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Synthetic form fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.encoding = self.root / "question.smt2"
        self.encoding.write_bytes(UNSAT)
        self.binding_path = self.root / "binding.json"
        self.binding = {"version": 1, "source_commit": self.commit,
                        "question": "Synthetic contradiction; no course form meaning",
                        "form": {"path": "form.tsv", "sha256": runner.sha256(self.form.read_bytes())},
                        "encoding": {"path": "question.smt2", "sha256": runner.sha256(UNSAT)},
                        "translator_provider": "openai",
                        "abstraction": "Synthetic test only"}
        self.save()

    def git(self, *args):
        self.assertEqual(Path(subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "--show-toplevel"], text=True).strip()), self.repo)
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.PIPE)

    def save(self):
        self.binding_path.write_text(json.dumps(self.binding))

    def review(self, **overrides):
        review = {"form_sha256": self.binding["form"]["sha256"],
                  "encoding_sha256": self.binding["encoding"]["sha256"],
                  "translator_provider": "openai", "reviewer_provider": "anthropic",
                  "status": "approved"}
        review.update(overrides)
        path = self.root / "review.json"
        path.write_text(json.dumps(review))
        self.binding["review"] = {"path": path.name, "sha256": runner.sha256(path.read_bytes())}
        self.save()

    def test_pinned_form_and_encoding_bind_without_a_form_semantic_claim(self):
        encoding, result = runner.read_binding(self.binding_path, self.repo)
        self.assertEqual(encoding, UNSAT)
        self.assertEqual(result["form"]["source_commit"], self.commit)
        self.assertEqual(result["form"]["sha256"], self.binding["form"]["sha256"])
        self.assertEqual(result["translation_review"]["status"], "pending")
        self.assertEqual(result["form_semantic_claim"], "not established by the runner")
        self.form.write_bytes(b"dirty working tree; not the pinned form")
        self.assertEqual(runner.read_binding(self.binding_path, self.repo)[1]["form"]["sha256"],
                         self.binding["form"]["sha256"])

    def test_changed_committed_form_or_encoding_refuses_as_stale(self):
        self.form.write_bytes(b"when\toutcome\nflag\tallowed\n")
        self.git("add", "--", "form.tsv")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Changed synthetic form")
        self.binding["source_commit"] = self.git("rev-parse", "HEAD").strip()
        self.save()
        with self.assertRaisesRegex(runner.InputError, "STALE form"):
            runner.read_binding(self.binding_path, self.repo)
        self.binding["source_commit"] = self.commit
        self.save()
        self.encoding.write_bytes(SAT)
        with self.assertRaisesRegex(runner.InputError, "STALE encoding"):
            runner.read_binding(self.binding_path, self.repo)

    def test_review_is_hash_bound_and_different_provider_is_reported_only(self):
        self.review()
        result = runner.read_binding(self.binding_path, self.repo)[1]
        self.assertEqual(result["translation_review"]["status"], "reported_approved")
        self.assertTrue(result["translation_review"]["different_provider_reported"])
        self.assertIn("not performed", result["translation_review"]["identity_authentication"])
        self.review(reviewer_provider=" OpenAI ")
        with self.assertRaisesRegex(runner.InputError, "different provider"):
            runner.read_binding(self.binding_path, self.repo)
        self.review(form_sha256="0" * 64)
        with self.assertRaisesRegex(runner.InputError, "STALE review"):
            runner.read_binding(self.binding_path, self.repo)

    def test_changed_review_file_and_wrong_translator_refuse(self):
        self.review()
        (self.root / "review.json").write_text("{}")
        with self.assertRaisesRegex(runner.InputError, "STALE review"):
            runner.read_binding(self.binding_path, self.repo)
        self.review(translator_provider="moonshot")
        with self.assertRaisesRegex(runner.InputError, "translator does not match"):
            runner.read_binding(self.binding_path, self.repo)

    def test_bad_identity_path_shape_and_duplicate_json_refuse(self):
        for change in ({"source_commit": "main"}, {"source_commit": "0" * 40},
                       {"version": True}, {"unexpected": 1}):
            with self.subTest(change=change):
                original = dict(self.binding)
                self.binding.update(change)
                self.save()
                with self.assertRaises(runner.InputError):
                    runner.read_binding(self.binding_path, self.repo)
                self.binding = original
        self.binding["form"]["path"] = "../form.tsv"
        self.save()
        with self.assertRaises(runner.InputError):
            runner.read_binding(self.binding_path, self.repo)
        self.binding_path.write_text('{"version":1,"version":1}')
        with self.assertRaisesRegex(runner.InputError, "duplicate"):
            runner.read_binding(self.binding_path, self.repo)

    def test_actual_bound_cli_report_is_new_external_and_does_not_clobber(self):
        output = self.root / "report.json"
        args = [sys.executable, "-I", "-B", str(Path(runner.__file__)), "bound",
                "--binding", str(self.binding_path), "--source-root", str(self.repo), "--output", str(output)]
        first = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report["solver"]["result"], "unsat")
        self.assertEqual(report["solver"]["unsat_core"], ["no", "yes"])
        before = output.read_bytes()
        second = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(runner.InputError, "outside the source"):
            runner.write_report(self.repo / "report.json", {}, [self.repo])


if __name__ == "__main__":
    unittest.main()
