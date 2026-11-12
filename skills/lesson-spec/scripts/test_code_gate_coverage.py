import tempfile
import unittest
from pathlib import Path

import check_forms


class CodeGateCoverageControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lesson = Path(self.temp.name) / "01-store"
        self.forms = self.lesson / "forms"
        self.forms.mkdir(parents=True)

    def code(self, stage):
        (self.forms / "code-rules.tsv").write_text(
            "id\tkind\tname\targs\tstage\tnorm\n"
            f"C01\tpure_core\tcore\t{{}}\t{stage}\tP/01.1 N1\n",
            encoding="utf-8")

    def stages(self, gates):
        path = self.forms / "stages.tsv"
        path.write_text("n\tstage\tgate\tdepends\n" + "".join(
            f"{i}\ts{i}\t{gate}\t-\n" for i, gate in enumerate(gates, 1)),
            encoding="utf-8")
        return path

    def test_own_or_later_stage_gate_covers_rule(self):
        self.code("s2")
        for gates in (["build", "code:*", "build"],
                      ["build", "build", "code:*"]):
            with self.subTest(gates=gates):
                self.assertEqual(check_forms.check_stage_parts(self.stages(gates))[0], [])

    def test_absent_or_only_former_stage_gate_refuses_rule(self):
        self.code("s2")
        for gates in (["build", "build", "build"],
                      ["code:*", "build", "build"]):
            with self.subTest(gates=gates):
                errors = check_forms.check_stage_parts(self.stages(gates))[0]
                self.assertTrue(any("no code:* gate" in e for e in errors), errors)

    def test_unknown_rule_stage_refuses(self):
        self.code("no_such_stage")
        errors = check_forms.check_stage_parts(self.stages(["code:*"]))[0]
        self.assertTrue(any("is not in stages.tsv" in e for e in errors), errors)

    def test_malformed_stage_rows_refuse_without_gate_key_failure(self):
        self.code("s1")
        path = self.forms / "stages.tsv"
        for text in ("stage\tgate\ns1\n", "stage\ns1\n"):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                self.assertTrue(check_forms.check_stage_parts(path)[0])

    def test_actual_published_source_rules_and_nine_gate_cells(self):
        lesson = Path(__file__).resolve().parents[3] / "Platform" / "01-store"
        errors, rules = check_forms.read(lesson / "forms" / "code-rules.tsv",
                                         ["id", "kind", "name", "args", "stage", "norm"])
        self.assertEqual(errors, [])
        self.assertTrue(rules)
        lines = [line.split("\t") for line in (lesson / "forms" / "stages.tsv").read_text(
            encoding="utf-8").splitlines() if line and not line.startswith("#")]
        stages = [dict(zip(lines[0], line)) for line in lines[1:]]
        self.assertEqual(sum("code:*" in row["gate"].split(";") for row in stages), 9)
        self.assertEqual(check_forms.check_stage_parts(lesson / "forms" / "stages.tsv")[0], [])


class TableDrivenKeyColumns(unittest.TestCase):
    """ADR-0133 доп. (86) п. 1 (F07, OBSH.48): the optional field key_columns of a table_driven row names columns of
    its form; without the field the check is as before."""

    FORM = '"form": "Platform/01-store/forms/refusals.tsv"'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.forms = self.root / "Platform" / "01-store" / "forms"
        self.forms.mkdir(parents=True)
        (self.forms / "refusals.tsv").write_text(
            "# the catalogue\nchapter\trow\tname\tsurface\tcode\tkind\tfields\theaders\tlog\tnorm\n"
            "1.1\t1\tbody_form\thttp\t400\tbadrequest\t-\t-\t-\tN4\n", encoding="utf-8")
        self.path = self.forms / "code-rules.tsv"

    def rules(self, *rows):
        self.path.write_text("# the code checks\nid\tkind\tname\targs\tstage\tnorm\n" + "".join(
            f"C{i:02}\t{kind}\tn{i}\t{args}\ts1\tP/01.1 N4\n" for i, (kind, args) in enumerate(rows, 1)),
            encoding="utf-8")
        return check_forms.check_code_rules(self.path)[0]

    def test_without_field_as_before(self):
        self.assertEqual(self.rules(("table_driven", "{" + self.FORM + ', "min_cell": 9}'),
                                    ("pure_core", '{"forbid": ["os"]}')), [])

    def test_key_columns_of_the_form(self):
        for keys in ('["name"]', '["name", "chapter"]'):
            with self.subTest(keys=keys):
                self.assertEqual(self.rules(
                    ("table_driven", "{" + self.FORM + f', "min_cell": 9, "key_columns": {keys}}}')), [])

    def test_unknown_column_refuses(self):
        errors = self.rules(("table_driven", "{" + self.FORM + ', "min_cell": 9, "key_columns": ["name", "flag"]}'))
        self.assertTrue(any("C01: key_columns: ['flag'] are not columns of Platform/01-store/forms/refusals.tsv" in e
                            for e in errors), errors)

    def test_malformed_key_columns_refuse(self):
        for keys in ('[]', '"name"', '["name", "name"]', '[1]'):
            with self.subTest(keys=keys):
                errors = self.rules(("table_driven", "{" + self.FORM + f', "min_cell": 9, "key_columns": {keys}}}'))
                self.assertTrue(any("not a nonempty list of distinct column names" in e for e in errors), errors)

    def test_missing_form_refuses(self):
        for form in ('"Platform/01-store/forms/none.tsv"', '"../refusals.tsv"', '7'):
            with self.subTest(form=form):
                errors = self.rules(("table_driven", f'{{"form": {form}, "min_cell": 9, "key_columns": ["name"]}}'))
                self.assertTrue(any("is not a form file of the Source" in e for e in errors), errors)

    def test_key_columns_of_another_kind_refuses(self):
        errors = self.rules(("exhaustive", "{" + self.FORM + ', "column": "kind", "key_columns": ["name"]}'))
        self.assertTrue(any("C01: key_columns: a field of table_driven only" in e for e in errors), errors)

    def test_engine_rules_and_published_rules(self):
        engine = self.root / "Platform" / "common" / "acceptance" / "forms" / "engine-code-rules.tsv"
        engine.parent.mkdir(parents=True)
        self.rules(("table_driven", "{" + self.FORM + ', "min_cell": 9, "key_columns": ["name"]}'))
        engine.write_bytes(self.path.read_bytes())
        self.assertEqual(check_forms.code_rule_forms(self.root), [self.path, engine])
        self.assertEqual(check_forms.check_code_rules(engine)[0], [])
        published = Path(__file__).resolve().parents[3]
        self.assertTrue(check_forms.code_rule_forms(published))
        for path in check_forms.code_rule_forms(published):
            with self.subTest(path=path):
                self.assertEqual(check_forms.check_code_rules(path)[0], [])


if __name__ == "__main__":
    unittest.main()
