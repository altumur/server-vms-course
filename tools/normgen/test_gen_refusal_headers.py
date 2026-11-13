"""Dynamic refusal headers: independent metadata, compiled wire witnesses and semantic mutants."""
import contextlib
import copy
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gen_door
import gen_refusals
import refusal_judge
import test_gen_refusals as legacy

HEADER = "chapter\trow\tname\tsurface\tcode\tkind\tfields\theaders\tlog\tnorm\n"
ROW = "1.3\t1\tfixture\thttp\t503\tunavailable\t-\t{}\t-\tfixture\n"


class HeaderMetadata(unittest.TestCase):
    def test_mixed_names_keep_fixed_values_separate_without_inventing_a_delay(self):
        text = HEADER + ROW.format(" RETRY-AFTER ; Connection: close; X-Wait")
        generated = gen_refusals.Table(text).rows[0]
        self.assertEqual(generated["header_list"], [("Connection", "close")])
        self.assertEqual(generated["dynamic_header_list"], ["RETRY-AFTER", "X-Wait"])
        emitted = gen_refusals.go_spec(generated)
        self.assertIn('Headers: [][2]string{{"Connection", "close"}}, RetryAfter: true', emitted)
        self.assertIn('DynamicHeaders: []string{"RETRY-AFTER", "X-Wait"}', emitted)
        self.assertNotIn('{"RETRY-AFTER", "1"}', emitted)
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "refusals.tsv"
            table.write_text(text)
            independently_read = refusal_judge.read_table(table)[0]
        self.assertEqual(independently_read["header_pairs"], [["Connection", "close"]])
        self.assertEqual(independently_read["dynamic_headers"], ["RETRY-AFTER", "X-Wait"])

    def test_legacy_fixed_only_repeats_keep_both_values_and_order(self):
        text = HEADER + ROW.format("Retry-After: 1; retry-after: 2")
        self.assertEqual(gen_refusals.Table(text).rows[0]["header_list"],
                         [("Retry-After", "1"), ("retry-after", "2")])
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "refusals.tsv"
            table.write_text(text)
            self.assertEqual(refusal_judge.read_table(table)[0]["header_pairs"],
                             [["Retry-After", "1"], ["retry-after", "2"]])

    def test_malformed_empty_and_repeated_names_refuse_in_both_readers(self):
        bad = ("Retry-After:", "Retry-After: ", "Retry-After 1", "Retry-After;", ";Retry-After",
               "Retry-After; retry-after", "Retry-After: 1; RETRY-AFTER", "Bad_Name", "-;Retry-After")
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "refusals.tsv"
            for headers in bad:
                text = HEADER + ROW.format(headers)
                table.write_text(text)
                with self.subTest(headers=headers), self.assertRaises(gen_refusals.GenError):
                    gen_refusals.Table(text)
                with self.subTest(headers=headers), self.assertRaises(refusal_judge.CheckingError):
                    refusal_judge.read_table(table)

    def test_witness_checks_transport_and_integer_form_without_fixing_a_deadline(self):
        for value in ("0", "1", "17", "9000", "-1"):
            witness = [{"op": "Write", "requested": [["RETRY-AFTER", value]],
                        "headers": [["Retry-After", value]]}]
            self.assertIsNone(refusal_judge.dynamic_header_error(["retry-after"], witness))
        for value in ("", "1.0", "1e1", "true", "17\r\nX: injected"):
            witness = [{"op": "Write", "requested": [["Retry-After", value]],
                        "headers": [["Retry-After", value]]}]
            self.assertIsNotNone(refusal_judge.dynamic_header_error(["Retry-After"], witness))
        for requested, observed in (("17", "1"), ("17", None)):
            witness = [{"op": "Write", "requested": [["Retry-After", requested]],
                        "headers": [] if observed is None else [["Retry-After", observed]]}]
            self.assertIsNotNone(refusal_judge.dynamic_header_error(["Retry-After"], witness))

    def test_new_private_members_are_strict_and_complete(self):
        row = legacy.RefusalReportControls.row()
        row["DynamicHeaders"] = ["Retry-After"]
        row["RetryAfter"] = True
        row["probes"][0]["wire"] = [{"op": "Fixture", "requested": [["Retry-After", "17"]],
                                     "headers": [["Retry-After", "17"]]}]
        good = legacy.RefusalReportControls.frame([row])
        self.assertEqual(refusal_judge.read_report(json.dumps(good)), [row])
        bad = []
        missing = copy.deepcopy(row)
        del missing["DynamicHeaders"]
        bad.append(missing)
        for value in ("Retry-After", [17], False):
            bad.append(dict(row, DynamicHeaders=value))
        for change in (lambda p: p.pop("wire"), lambda p: p.update(wire=None), lambda p: p.update(wire=[]),
                       lambda p: p["wire"][0].update(op="Other"),
                       lambda p: p["wire"][0].pop("requested"),
                       lambda p: p["wire"][0].update(requested=[["Retry-After", 17]]),
                       lambda p: p["wire"][0].update(headers=[["Retry-After", "17"], ["RETRY-AFTER", "17"]])):
            changed = copy.deepcopy(row)
            change(changed["probes"][0])
            bad.append(changed)
        for changed in bad:
            with self.subTest(row=changed), self.assertRaises(refusal_judge.CheckingError):
                refusal_judge.read_report(json.dumps(legacy.RefusalReportControls.frame([changed])))


class CompiledHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-refusal-headers-")
        cls.base = Path(cls.tmp.name) / "p01-1"
        gen_door.generate(out=cls.base)
        gen_refusals.generate(out=cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def compare(self, module, table=None):
        report = module / "judge-result.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(refusal_judge, "TABLE", table or gen_refusals.DEFAULT_TABLE), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = refusal_judge.main(["--module-dir", str(module), "--json", str(report)])
        self.assertIn(code, (0, 1), stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        result = legacy.normal_result(code, report.read_bytes())
        return code, {r["name"] for r in result["results"] if not r["ok"]}

    def module(self, label):
        path = Path(self.tmp.name) / label
        shutil.copytree(self.base / "go", path)
        return path

    def test_actual_catalogue_has_distinct_fixed_and_dynamic_headers_and_variable_wire(self):
        module = self.module("positive")
        self.assertEqual(self.compare(module), (0, set()))
        with tempfile.TemporaryDirectory() as tmp:
            rows = refusal_judge.harness(module, tmp)
        actual = {r["Name"]: r for r in rows}
        self.assertEqual(actual["connection_limit"]["Headers"], [["Retry-After", "1"]])
        self.assertIsNone(actual["connection_limit"]["DynamicHeaders"])
        replay = actual["replay_limit"]
        self.assertIsNone(replay["Headers"])
        self.assertEqual(replay["DynamicHeaders"], ["Retry-After"])
        self.assertTrue(any(["Retry-After", "17"] in w["headers"]
                            and ["Retry-After", "17"] in w["requested"]
                            for p in replay["probes"] for w in p["wire"]))

    def test_case_insensitive_header_names_bind_typed_answer_and_wire(self):
        original = gen_refusals.DEFAULT_TABLE.read_text()
        for number, name in enumerate(("retry-after", "RETRY-AFTER", "ReTrY-AfTeR")):
            module = self.module("case" + str(number))
            table = module / "refusals.tsv"
            lines = original.splitlines()
            for i, line in enumerate(lines):
                cells = line.split("\t")
                if len(cells) == 10 and cells[2] == "replay_limit":
                    cells[7] = name
                    lines[i] = "\t".join(cells)
            table.write_text("\n".join(lines) + "\n")
            gen_refusals.generate(table, module.parent / ("case-output" + str(number)))
            generated = module.parent / ("case-output" + str(number)) / "go/refusals/refusals.go"
            shutil.copy(generated, module / "refusals/refusals.go")
            self.assertEqual(self.compare(module, table), (0, set()))

    def test_metadata_and_constant_or_missing_wire_mutants_fail_semantically(self):
        prefix = 'Name: "replay_limit", Surface: "http", Code: 503, Kind: "unavailable", Fields: nil, Headers: nil, RetryAfter: true, DynamicHeaders: []string{"Retry-After"}'
        cases = (
            ("missing-name", "refusals/refusals.go", prefix, prefix.replace('[]string{"Retry-After"}', 'nil')),
            ("changed-name", "refusals/refusals.go", prefix, prefix.replace('[]string{"Retry-After"}', '[]string{"X-Lost"}')),
            ("false-marker", "refusals/refusals.go", prefix, prefix.replace("RetryAfter: true", "RetryAfter: false")),
            ("invented-fixed-one", "refusals/refusals.go", prefix,
             prefix.replace('Headers: nil', 'Headers: [][2]string{{"Retry-After", "1"}}').replace('[]string{"Retry-After"}', 'nil')),
            ("serialized-one", "apidoor/door.go", 'strconv.FormatInt(*a.RetryAfter, 10)', '"1"'),
            ("missing-wire", "apidoor/door.go", 'header = append(header, [2]string{"Retry-After", strconv.FormatInt(*a.RetryAfter, 10)})', '// no Retry-After emitted'),
        )
        for label, relative, before, after in cases:
            with self.subTest(mutant=label):
                module = self.module(label)
                path = module / relative
                source = path.read_text()
                self.assertEqual(source.count(before), 1)
                path.write_text(source.replace(before, after, 1))
                code, failures = self.compare(module)
                self.assertEqual(code, 1, label)
                self.assertTrue(any("replay_limit" in n for n in failures), failures)


if __name__ == "__main__":
    unittest.main()
