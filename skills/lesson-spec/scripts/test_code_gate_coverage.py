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

    def test_actual_published_source_rules_and_eleven_gate_cells(self):
        lesson = Path(__file__).resolve().parents[3] / "Platform" / "01-store"
        errors, rules = check_forms.read(lesson / "forms" / "code-rules.tsv",
                                         ["id", "kind", "name", "args", "stage", "norm"])
        self.assertEqual(errors, [])
        self.assertTrue(rules)
        lines = [line.split("\t") for line in (lesson / "forms" / "stages.tsv").read_text(
            encoding="utf-8").splitlines() if line and not line.startswith("#")]
        stages = [dict(zip(lines[0], line)) for line in lines[1:]]
        self.assertEqual(sum("code:*" in row["gate"].split(";") for row in stages), 11)   # OBSH.70: rights, daemon_doors
        self.assertEqual(check_forms.check_stage_parts(lesson / "forms" / "stages.tsv")[0], [])


if __name__ == "__main__":
    unittest.main()
