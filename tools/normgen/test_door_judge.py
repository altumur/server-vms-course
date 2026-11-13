"""Owned source/report fixtures; no build, native command or implementation runs."""
from contextlib import redirect_stdout, nullcontext
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import door_judge as judge
import tsv_input


ROWS = [
    ("plain", "1", "GET /v1/status", "200 {}"),
    ("mixed", "1", "GET /v1/get?key=x", '200 {"items":null}'),
    ("mixed", "2", 'POST /v1/write {"id":"once"}', "200 {}"),
    ("mixed", "3", "GET /v1/get?key=x", "200 {}"),
    ("refused", "1", "POST /v1/write {}", '409 {"kind":"conflict"}'),
    ("literal", "1", r'POST /v1/write {"items":{"note":"\\u0069d"}}', "200 {}"),
]
COLUMNS = ("scenario", "step", "request", "expect")
RELATIVE = "Platform/01-store/acceptance/1/scenarios.tsv"
PROOF = "Platform/common/data/cell-json-sha256.tsv"
PROOF_HEADER = "table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n"


class DoorJudge(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="door-judge-owned-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, rows=ROWS, *, marked=False, header="comment"):
        lines = []
        if marked:
            lines.append("# cell-json: request,expect")
        if header != "none":
            lines.append(("# " if header == "comment" else "") + "\t".join(COLUMNS))
        proofs = []
        for row in rows:
            cells = list(row)
            if marked:
                for index in (2, 3):
                    value = cells[index]
                    digest = hashlib.sha256(value.encode()).hexdigest()
                    proofs.append(f"{RELATIVE}\t{len(lines) + 1}\t{COLUMNS[index]}\t{digest}\t{digest}\n")
                    cells[index] = json.dumps(value, ensure_ascii=True)
            lines.append("\t".join(cells))
        path = self.root / RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        proof = self.root / PROOF
        proof.parent.mkdir(parents=True, exist_ok=True)
        if marked:
            proof.write_text(PROOF_HEADER + "".join(proofs))
        elif proof.exists():
            proof.unlink()
        return path

    @staticmethod
    def report(rows):
        scenarios = {}
        for name, step, *_ in rows:
            scenarios.setdefault(name, {"steps": []})["steps"].append({"step": int(step), "ok": True})
        return {"scenarios": scenarios}

    def run_judge(self, path, report, *, root=None):
        folder = self.root / "report"
        folder.mkdir(exist_ok=True)
        source = folder / "P-01.1-door.json"
        if report is None:
            source.unlink(missing_ok=True)
        else:
            source.write_text(report if isinstance(report, str) else json.dumps(report))
        result = self.root / "result.json"
        result.unlink(missing_ok=True)
        output = io.StringIO()
        with patch.object(judge, "ROOT", root) if root else nullcontext():
            with redirect_stdout(output):
                code = judge.main([str(folder), "--scenarios", str(path), "--json", str(result)])
        return code, json.loads(result.read_text()), output.getvalue()

    def test_canonical_346_rows_40_scenarios_have_76_prefix_and_149_own_steps(self):
        path = judge.ROOT / RELATIVE
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "4a7431e62c6e5484d906f58a9a6b990d74181e27fa4a37979ba4b114eefc0dfe")
        # Scenario/step ids do not need cell decoding and do not use the judge as oracle.
        rows = [tuple(line.split("\t")) for line in path.read_text().split("\n")
                if line and not line.startswith("#")]
        self.assertEqual((len(rows), len({r[0] for r in rows})), (346, 40))
        code, result, _ = self.run_judge(path, self.report(rows))
        self.assertEqual(code, 0)
        self.assertEqual((result["passed"], result["total"], result["core_steps"]), (76, 76, 270))
        self.assertEqual((result["own"]["passed"], result["own"]["total"]), (149, 149))
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["scenarios"]), 40)

    def test_encoded_and_unmarked_are_equal_for_all_existing_header_forms(self):
        expected = [(name, [(step, request + "\t" + expect)
                            for n, step, request, expect in ROWS if n == name])
                    for name in dict.fromkeys(r[0] for r in ROWS)]
        for header in ("comment", "none", "header"):
            for marked in (False, True):
                with self.subTest(header=header, marked=marked):
                    path = self.source(marked=marked, header=header)
                    with patch.object(judge, "ROOT", self.root):
                        self.assertEqual(judge.expected_steps(path), expected)
                    code, result, _ = self.run_judge(path, self.report(ROWS), root=self.root)
                    self.assertEqual(code, 0)
                    self.assertEqual((result["total"], result["core_steps"], result["own"]["total"]), (3, 3, 4))

    def test_one_decode_retains_a_logical_json_string_and_unmarked_quotes(self):
        text = json.dumps('POST /v1/write {"id":"literal"}')
        rows = [("s", "1", text, "200 {}")]
        for marked in (False, True):
            with self.subTest(marked=marked):
                path = self.source(rows, marked=marked)
                with patch.object(judge, "ROOT", self.root):
                    self.assertEqual(judge.expected_steps(path), [("s", [("1", text + "\t200 {}")])])

    def test_legacy_unmarked_external_source_and_header_remain_valid(self):
        path = self.source(header="header")
        code, result, _ = self.run_judge(path, self.report(ROWS))
        self.assertEqual(code, 0)
        self.assertEqual((result["total"], result["own"]["total"]), (3, 4))

    def test_logical_tabs_and_lf_are_not_split_into_another_row(self):
        text = 'POST /v1/write {"id"\n:\t"once"}'
        path = self.source([("s", "1", text, "200 {}")], marked=True)
        with patch.object(judge, "ROOT", self.root):
            self.assertEqual(judge.expected_steps(path), [("s", [("1", text + "\t200 {}")])])

    def test_bad_missing_and_extra_proofs_fail_api_and_cli_without_fallback(self):
        for mutation in ("absent", "missing-row", "extra-row", "wrong-digest", "before-mismatch"):
            with self.subTest(mutation=mutation):
                path = self.source(marked=True)
                proof = self.root / PROOF
                lines = proof.read_text().splitlines(keepends=True)
                if mutation == "absent":
                    proof.unlink()
                elif mutation == "missing-row":
                    proof.write_text("".join(lines[:-1]))
                elif mutation == "extra-row":
                    extra = lines[1].split("\t"); extra[1] = "999"
                    proof.write_text("".join(lines) + "\t".join(extra))
                else:
                    cells = lines[1].rstrip("\n").split("\t")
                    cells[3] = "0" * 64
                    if mutation == "wrong-digest":
                        cells[4] = cells[3]
                    lines[1] = "\t".join(cells) + "\n"
                    proof.write_text("".join(lines))
                with patch.object(judge, "ROOT", self.root), self.assertRaises(tsv_input.TSVError):
                    judge.expected_steps(path)
                code, result, _ = self.run_judge(path, self.report(ROWS), root=self.root)
                self.assertEqual(code, 1)
                self.assertTrue(any("scenario source" in e for e in result["errors"]), result)

    def test_marked_source_outside_declared_root_is_not_a_legacy_fallback(self):
        path = self.source(marked=True)
        with patch.object(judge, "ROOT", self.root / "different"), self.assertRaises(tsv_input.TSVError):
            judge.expected_steps(path)

    def test_invalid_cell_transport_and_width_are_typed_source_errors(self):
        for raw in (b'# cell-json: request\ns\t1\t{}\t200 {}\n',
                    b'# cell-json: unknown\ns\t1\t"GET /"\t200 {}\n',
                    b's\t1\tGET /\n', b's\t1\tGET /\t200 {}\textra\n', b'\xff\n'):
            with self.subTest(raw=raw):
                path = self.source()
                path.write_bytes(raw)
                code, result, _ = self.run_judge(path, self.report(ROWS), root=self.root)
                self.assertEqual(code, 1)
                self.assertTrue(any("scenario source" in e for e in result["errors"]), result)

    def test_tainted_tail_remains_excluded_but_is_counted_as_own_text(self):
        path = self.source(marked=True)
        report = self.report(ROWS)
        report["scenarios"]["mixed"]["steps"][2]["ok"] = False
        code, result, _ = self.run_judge(path, report, root=self.root)
        self.assertEqual(code, 0)  # Own-text diagnostics do not change the prefix criterion.
        self.assertEqual((result["passed"], result["total"]), (3, 3))
        self.assertEqual((result["own"]["passed"], result["own"]["total"]), (3, 4))
        self.assertEqual(len(result["own"]["fails"]), 1)

    def test_missing_core_step_still_fails_report_completeness(self):
        path = self.source(marked=True)
        report = self.report(ROWS)
        report["scenarios"]["mixed"]["steps"].pop(1)
        code, result, _ = self.run_judge(path, report, root=self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("without an outcome" in e for e in result["errors"]))

    def test_missing_extra_and_nontrue_prefix_outcomes_cannot_pass(self):
        path = self.source(marked=True)
        for mutation in ("missing-scenario", "extra-scenario", "extra-step", "nontrue"):
            with self.subTest(mutation=mutation):
                report = self.report(ROWS)
                if mutation == "missing-scenario":
                    report["scenarios"].pop("mixed")
                elif mutation == "extra-scenario":
                    report["scenarios"]["foreign"] = {"steps": []}
                elif mutation == "extra-step":
                    report["scenarios"]["plain"]["steps"].append({"step": 99, "ok": True})
                else:
                    report["scenarios"]["plain"]["steps"][0]["ok"] = "true"
                self.assertEqual(self.run_judge(path, report, root=self.root)[0], 1)

    def test_absent_empty_and_truncated_reports_fail(self):
        path = self.source(marked=True)
        for report in (None, {"scenarios": {}}, '{"scenarios":'):
            with self.subTest(report=report):
                code, result, _ = self.run_judge(path, report, root=self.root)
                self.assertEqual(code, 1)
                self.assertTrue(result["errors"])

    def test_empty_and_all_core_sources_preserve_the_nonzero_measure_requirement(self):
        for rows in ([], [("s", "1", 'POST /v1/write {"id":"x"}', "200 {}")]):
            with self.subTest(rows=rows):
                path = self.source(rows, marked=True)
                code, result, _ = self.run_judge(path, self.report(rows), root=self.root)
                self.assertEqual(code, 1)
                self.assertEqual(result["total"], 0)
                self.assertTrue(any("measure is empty" in e for e in result["errors"]))

    def test_missing_source_is_a_failed_typed_report(self):
        path = self.root / "missing.tsv"
        code, result, _ = self.run_judge(path, self.report(ROWS), root=self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("scenario source" in e for e in result["errors"]), result)


if __name__ == "__main__":
    unittest.main()
