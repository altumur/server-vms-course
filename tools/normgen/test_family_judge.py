"""Independent private service/accounting controls for the family judge."""
import copy
import io
import json
import subprocess
import unittest
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
import family_judge as judge


def source_case(name="owned-case"):
    return dict(case=name, family="fixture", key="fixture/key", kind="row", mode="writer",
                who=[], text="{}", verdict="ok", paths=[], outcome=[], note="owned source fixture")


class FamilyJudgeControls(unittest.TestCase):
    def answer(self, case=None, identity=1):
        case = case or source_case()
        return dict(id=identity, case=case["case"], verdict=case["verdict"],
                    paths=copy.deepcopy(case["paths"]), outcome=copy.deepcopy(case["outcome"]))

    def report(self, frames, exit=0, stderr=b""):
        raw = b"".join(json.dumps(f, ensure_ascii=False).encode("utf-8") + b"\n" for f in frames)
        return subprocess.CompletedProcess([], exit, raw, stderr)

    def test_runs_must_be_positive_integer_before_source_or_preparation(self):
        for value in (0, -1, True, False, 1.0, None, "1"):
            with self.subTest(runs=value), patch.object(judge, "rows", return_value=[source_case()]) as rows, \
                    patch.object(judge, "harness", return_value=[]) as service:
                with self.assertRaises(ValueError):
                    judge.judge("unused", runs=value)
                rows.assert_not_called()
                service.assert_not_called()

    def test_cli_zero_runs_is_rejected_before_default_output_validation(self):
        with patch.object(judge.lesson, "ready_outputs", side_effect=AssertionError("readiness reached")) as ready, \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit:
                judge.main(["--runs", "0"])
            self.assertEqual(exit.exception.code, 2)
            ready.assert_not_called()

    def test_complete_positive_and_repeats_preserve_public_report(self):
        case = source_case()
        with patch.object(judge, "rows", return_value=[case]), \
                patch.object(judge, "harness", return_value=[self.answer(case)]) as service:
            got = judge.judge("unused", runs=2)
        self.assertEqual(got, {"lesson": judge.L.nn, "cases": 1, "pass": 1, "runs": 2, "failures": []})
        self.assertEqual(service.call_count, 2)

    def test_complete_semantic_difference_is_not_a_checking_error(self):
        case = source_case()
        answer = dict(self.answer(case), verdict="refused")
        with patch.object(judge, "rows", return_value=[case]), patch.object(judge, "harness", return_value=[answer]):
            got = judge.judge("unused", runs=1)
        self.assertEqual(got["pass"], 0)
        self.assertEqual([x["case"] for x in got["failures"]], [case["case"]])

    def test_full_missing_family_observation_is_a_semantic_difference(self):
        case = source_case()
        answer = dict(id=1, case=case["case"], error="no family fixture")
        with patch.object(judge, "rows", return_value=[case]), patch.object(judge, "harness", return_value=[answer]):
            self.assertEqual(judge.judge("unused", runs=1)["pass"], 0)

    def test_empty_or_duplicate_source_never_prepares_a_service(self):
        for cases in ([], [source_case(), source_case()]):
            with self.subTest(cases=cases), patch.object(judge, "rows", return_value=cases), \
                    patch.object(judge, "harness") as service:
                with self.assertRaises(judge.CheckingError):
                    judge.judge("unused", runs=1)
                service.assert_not_called()

    def test_every_answer_is_checked_before_the_first_source_comparison(self):
        cases = [source_case("first"), source_case("last")]
        answers = [self.answer(cases[0]), dict(self.answer(cases[1], 2), id=1)]
        with patch.object(judge, "rows", return_value=cases), patch.object(judge, "harness", return_value=answers), \
                patch.object(judge, "compare") as oracle:
            with self.assertRaises(judge.CheckingError):
                judge.judge("unused", runs=1)
            oracle.assert_not_called()

    def test_missing_extra_duplicate_or_unknown_frame_identity_is_checking(self):
        case = source_case()
        normal = self.answer(case)
        self.assertEqual(judge.checked_answers([case], [normal]), [normal])
        for frames in ([], [normal, normal], [dict(normal, id=0)], [dict(normal, id=True)],
                       [dict(normal, id=2)], [dict(normal, case="unknown")], [dict(normal, extra="value")]):
            with self.subTest(frames=frames), self.assertRaises(judge.CheckingError):
                judge.checked_answers([case], frames)

    def test_missing_or_mistyped_computed_fields_are_checking(self):
        case, normal = source_case(), self.answer()
        changes = [{k: v for k, v in normal.items() if k != "outcome"}, dict(normal, verdict=True),
                   dict(normal, paths=None), dict(normal, paths=[True]), dict(normal, outcome=None),
                   dict(normal, outcome={}), dict(id=1, case=case["case"], error="")]
        for frame in changes:
            with self.subTest(frame=frame), self.assertRaises(judge.CheckingError):
                judge.checked_answers([case], [frame])

    def test_reader_roles_and_utf8_lf_are_preserved(self):
        case = source_case("unicode-σ")
        case.update(mode="reader", who=["domain"], paths=["/line\nσ"], outcome={"domain": ["/line\nσ"]})
        answer = self.answer(case)
        self.assertEqual(judge.read_report([case], self.report([answer])), [answer])
        with self.assertRaises(judge.CheckingError):
            judge.checked_answers([case], [dict(answer, outcome={"domain": [False]})])

    def test_invalid_utf8_json_constants_duplicate_keys_and_truncation_are_checking(self):
        case, answer = source_case(), self.answer()
        raw = self.report([answer]).stdout
        bad = [b"", b"\xff", raw[:-3], raw + b"\n", raw.replace(b'"id": 1', b'"id": NaN'),
               raw.replace(b'"id": 1', b'"id": 1, "id": 1'), b"[]\n", raw + b"extra"]
        for value in bad:
            with self.subTest(raw=value), self.assertRaises(judge.CheckingError):
                judge.read_report([case], subprocess.CompletedProcess([], 0, value, b""))

    def test_nonzero_signal_or_service_stderr_is_not_semantic(self):
        case = source_case()
        for code, err in ((1, b""), (-9, b""), (0, b"service error")):
            with self.subTest(code=code), self.assertRaises(judge.CheckingError):
                judge.read_report([case], self.report([self.answer(case)], code, err))

    def test_harness_echoes_exact_input_identity_and_preserves_payload(self):
        case = source_case()
        build = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(judge.subprocess, "run", side_effect=[build, self.report([self.answer(case)])]) as process:
            self.assertEqual(judge.harness("unused", [case]), [self.answer(case)])
        sent = json.loads(process.call_args_list[1].kwargs["input"])
        self.assertEqual(sent, {"id": 1, "case": case["case"], **{k: case[k] for k in
                         ("family", "key", "mode", "who", "text")}})

    def test_build_start_and_timeout_errors_are_checking(self):
        for outcome in (subprocess.CompletedProcess([], 1, b"", b"compiler error"),
                        OSError("no compiler"), subprocess.TimeoutExpired(["go"], 1)):
            with self.subTest(outcome=outcome), patch.object(judge.subprocess, "run", side_effect=outcome
                    if isinstance(outcome, BaseException) else [outcome]):
                with self.assertRaises(judge.CheckingError):
                    judge.harness("unused", [source_case()])

    def test_cli_checking_error_never_prints_success(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(judge, "judge", side_effect=judge.CheckingError("partial report")), \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(judge.main(["--module-dir", "unused", "--runs", "1"]), 2)
        self.assertNotIn("PASS", out.getvalue())
        self.assertIn("partial report", err.getvalue())

    def test_cli_output_write_failure_precedes_success(self):
        normal = {"lesson": judge.L.nn, "cases": 1, "pass": 1, "runs": 1, "failures": []}
        out, err = io.StringIO(), io.StringIO()
        with patch.object(judge, "judge", return_value=normal), \
                patch.object(Path, "write_text", side_effect=OSError("synthetic write failure")), \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(judge.main(["--module-dir", "unused", "--runs", "1", "--json", "owned.json"]), 2)
        self.assertNotIn("PASS", out.getvalue())

    def test_cli_complete_semantic_mismatch_keeps_exit_one(self):
        mismatch = {"lesson": judge.L.nn, "cases": 1, "pass": 0, "runs": 1,
                    "failures": [{"case": "owned-case", "why": "wrong verdict"}]}
        with patch.object(judge, "judge", return_value=mismatch), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(judge.main(["--module-dir", "unused", "--runs", "1"]), 1)
        self.assertIn("FAIL", out.getvalue())



class FamilyReportShapeControls(unittest.TestCase):
    """New audit deltas; do not replay the completed original controls."""

    def test_source_unknown_kind_or_verdict_never_starts_service(self):
        for changes in (dict(kind="unknown"), dict(verdict="UNKNOWN")):
            case = dict(source_case(), **changes)
            with patch.object(judge, "rows", return_value=[case]), patch.object(judge, "harness") as process:
                with self.assertRaises(judge.CheckingError):
                    judge.judge("unused", runs=1)
                process.assert_not_called()

    def test_unknown_verdict_and_missing_final_lf_are_checking_before_compare(self):
        case = source_case()
        normal = dict(id=1, case=case["case"], verdict="ok", paths=[], outcome=[])
        done = subprocess.CompletedProcess([], 0, json.dumps(normal).encode(), b"")
        with self.assertRaises(judge.CheckingError):
            judge.read_report([case], done)
        with patch.object(judge, "rows", return_value=[case]), \
                patch.object(judge, "harness", return_value=[dict(normal, verdict="UNKNOWN")]), \
                patch.object(judge, "compare") as compare:
            with self.assertRaises(judge.CheckingError):
                judge.judge("unused", runs=1)
            compare.assert_not_called()


class R008TimeControls(unittest.TestCase):
    """Independent Source244 Time deltas; no producer execution or old-suite replay."""

    def base(self, kind="row", mode="reader"):
        # Exact normal shape of Source244 configstore-doors and heartbeat bases.
        if kind == "row":
            return dict(case="source-positive", family="platform/configstore-doors/<id>",
                        key="platform/configstore-doors/t1", kind=kind, mode=mode,
                        who=["configstore-door"], text='{"seen_at":"1"}', verdict="ok",
                        paths=[], outcome=[] if mode == "writer" else {"configstore-door": []}, note="base")
        return dict(case="source-positive", family="<sub>/heartbeats/<name>",
                    key="testsub/heartbeats/w-1", kind=kind, mode=mode, who=["console"],
                    text='{"worker":"w-1","ts":"1","status":[{"id":"a","phase":"a",'
                         '"epoch":1,"observed_revision":1,"revision":1}],"server":"a","instance":"a"}',
                    verdict="ok", paths=[], outcome=[] if mode == "writer" else {"console": []}, note="base")

    def cases(self, kind="row", mode="reader"):
        return judge._r008_mutations(self.base(kind, mode), "seen_at" if kind == "row" else "ts", "")

    def test_r008_source_time_normal_is_first_in_each_transport_and_mode(self):
        for kind in ("row", "object"):
            for mode in ("writer", "reader"):
                cases = self.cases(kind, mode)
                self.assertIn("-normal-string", cases[0]["case"])
                self.assertEqual((cases[0]["verdict"], cases[0]["paths"]), ("ok", []))
                if kind == "object":
                    self.assertIn("-normal-number", cases[1]["case"])
                    self.assertEqual(cases[1]["verdict"], "ok")
                self.assertEqual(judge._cases(cases), cases)

    def test_r008_precision_is_lexical_including_excess_trailing_zeros(self):
        for text in ("1.1234", "1.1230", "1.0000", "0.0001", "0.9999", "1.00000000000000001"):
            self.assertFalse(judge._r008_time_lexeme(text), text)
        for mode in ("writer", "reader"):
            cases = self.cases("object", mode)
            for label in ("excess", "excess-zero", "four-zeros", "no-truncate", "no-round", "float-collapse"):
                selected = [c for c in cases if c["case"].endswith("-" + label + "-number")]
                self.assertEqual(len(selected), 1)
                self.assertEqual((selected[0]["verdict"], selected[0]["paths"]), ("refused", ["/ts"]))
                self.assertEqual(selected[0]["outcome"], [] if mode == "writer" else {"console": [""]})

    def test_r008_boundaries_preserve_time_domain_without_uint53_cap(self):
        for text in ("0", "0.001", "1.1", "1.12", "1.120", "1.000", "9007199254740992", "1" + "0" * 308):
            self.assertTrue(judge._r008_time_lexeme(text), text)
        self.assertFalse(judge._r008_time_lexeme("1" + "0" * 309))
        for text in ("-1", "-0", "+1", "01", "1e0", " 1", "1\n", "1.", ".1", "", "1970-01-01T00:00:01Z"):
            self.assertFalse(judge._r008_time_lexeme(text), repr(text))
        for value in (1, 1.123, True, None):
            self.assertFalse(judge._r008_time_lexeme(value))

    def test_r008_row_items_remain_strings_numeric_time_only_in_object(self):
        for mode in ("writer", "reader"):
            for case in self.cases("row", mode):
                value = json.loads(case["text"])["seen_at"]
                if type(value) is not str:
                    self.assertIn("numeric-", case["case"])
                    self.assertEqual(case["verdict"], "refused")
                self.assertEqual(case["family"], "platform/configstore-doors/<id>")
            numeric = [c for c in self.cases("object", mode) if c["case"].endswith("-normal-number")][0]
            self.assertEqual(json.loads(numeric["text"])["ts"], 1.123)
            self.assertEqual(numeric["verdict"], "ok")

    def test_r008_json_whitespace_is_not_misclassified_as_numeric_precision(self):
        for mode in ("writer", "reader"):
            cases = self.cases("object", mode)
            for label in ("space", "final-lf"):
                selected = [c for c in cases if "-" + label + "-" in c["case"]]
                self.assertEqual(len(selected), 1)
                self.assertTrue(selected[0]["case"].endswith("-string"))
                self.assertEqual(selected[0]["verdict"], "refused")

    def test_r008_raw_numeric_spelling_survives_float_collapse(self):
        cases = self.cases("object")
        case = next(c for c in cases if c["case"].endswith("-float-collapse-number"))
        self.assertIn('"ts":1.00000000000000001', case["text"])
        self.assertEqual(json.loads(case["text"])["ts"], 1.0)
        # A synthetic permissive reader is a semantic difference only after a
        # complete valid frame. This is fixture evidence, not actual Go evidence.
        answer = dict(id=1, case=case["case"], verdict="ok", paths=[], outcome={"console": []})
        judge.checked_answers([case], [answer])
        self.assertIsNotNone(judge.compare(case, answer))

    def test_r008_time_cases_keep_full_report_checking_errors(self):
        case = next(c for c in self.cases("object") if c["verdict"] == "refused")
        normal = dict(id=1, case=case["case"], verdict="refused", paths=["/ts"], outcome={"console": [""]})
        for answer in (dict(normal, verdict="UNKNOWN"), dict(normal, paths=None), dict(normal, outcome=None)):
            with self.assertRaises(judge.CheckingError):
                judge.checked_answers([case], [answer])
        raw = (json.dumps(normal) + "\n").encode()
        for exit, stdout in ((1, raw), (0, raw[:-1]), (0, b"")):
            with self.assertRaises(judge.CheckingError):
                judge.read_report([case], subprocess.CompletedProcess([], exit, stdout, b""))

    def test_r008_explicit_source_pin_missing_context_and_changed_input_are_checking(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must reject pin first")):
            with self.assertRaises(judge.CheckingError):
                judge.r008_time_cases("unused", source_pin="Source237", lesson="01")
        for failure in (OSError("missing public input"), b"changed Source bytes", b"\xff"):
            with patch.object(Path, "read_bytes", side_effect=failure if isinstance(failure, OSError) else None,
                              return_value=failure if isinstance(failure, bytes) else b""):
                with self.assertRaises(judge.CheckingError):
                    judge.r008_time_cases("unused", source_pin=judge.R008_SOURCE, lesson="01")
        with self.assertRaises(judge.CheckingError):
            judge.r008_time_cases("unused", source_pin=judge.R008_SOURCE, lesson="08")

if __name__ == "__main__":
    unittest.main()
