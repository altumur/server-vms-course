import tempfile
import unittest
from pathlib import Path

import check_forms


class CodeGateStageControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lesson = Path(self.temp.name) / "Platform" / "01-store"
        self.forms = self.lesson / "forms"
        self.forms.mkdir(parents=True)

    def stages(self, gates, *, kit=False):
        head = ["n", "stage", "gate", "depends"]
        if kit:
            head += ["kit", "parts"]
        rows = [head]
        for number, gate in enumerate(gates, 1):
            row = [str(number), f"s{number}", gate, "-"]
            if kit:
                row += ["-", "-"]
            rows.append(row)
        path = self.forms / ("stages.kit.tsv" if kit else "stages.tsv")
        path.write_text("\n".join("\t".join(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def code(self, stage):
        path = self.forms / "code-rules.tsv"
        path.write_text("id\tkind\tname\targs\tstage\tnorm\n"
                        f"core_pure\tpure_core\tcore\t{{}}\t{stage}\tP/01.1 N1\n",
                        encoding="utf-8")
        return path

    def errors(self, gates, *, kit=False):
        return check_forms.check_stage_parts(self.stages(gates, kit=kit))[0]

    def test_exact_code_star_gate_and_closed_kinds(self):
        self.assertEqual(check_forms.gate_errors(self.lesson, "s1", "code:*"), [])
        for bad in ("code", "code:all", "code:*:seams", "mech:*", "unknown:*", "code: *"):
            with self.subTest(gate=bad):
                self.assertTrue(check_forms.gate_errors(self.lesson, "s1", bad))

    def test_code_row_is_covered_at_own_stage(self):
        self.code("s2")
        self.assertEqual(self.errors(["build", "build;code:*", "build"]), [])

    def test_code_row_is_selected_by_later_stage_gate(self):
        self.code("s1")
        self.assertEqual(self.errors(["build", "build", "code:*"]), [])

    def test_missing_and_only_former_code_gate_refuse(self):
        self.code("s2")
        for gates in (["build", "build", "build"], ["code:*", "build", "build"]):
            with self.subTest(gates=gates):
                self.assertTrue(any("no code:* gate" in e for e in self.errors(gates)))

    def test_unknown_code_stage_and_malformed_form_refuse(self):
        path = self.code("absent")
        self.assertTrue(any("not in stages.tsv" in e for e in self.errors(["code:*"])))
        path.write_text("id\tstage\ncore_pure\ts1\n", encoding="utf-8")
        self.assertTrue(any("columns must be" in e for e in self.errors(["code:*"])))

    def test_code_form_must_be_an_ordinary_file(self):
        path = self.forms / "code-rules.tsv"
        path.symlink_to(self.forms / "missing")
        self.assertTrue(any("ordinary file" in e for e in self.errors(["code:*"])))

    def test_legacy_kit_snapshot_does_not_bind_new_code_rows(self):
        self.code("s2")
        self.assertEqual(self.errors(["build"], kit=True), [])

    def test_lessons_without_code_rows_and_existing_vector_gate_unchanged(self):
        (self.lesson / "vectors" / "native").mkdir(parents=True)
        self.assertEqual(self.errors(["vectors:native", "build"]), [])
        self.assertTrue(check_forms.gate_errors(self.lesson, "s1", "vectors:absent"))


if __name__ == "__main__":
    unittest.main()
