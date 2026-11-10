import tempfile
import unittest
from pathlib import Path

import check_forms


class CodeGateAdmissionControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lesson = Path(self.temp.name) / "01-store"
        self.lesson.mkdir()

    def test_exact_code_star_is_admitted_in_gate_list(self):
        self.assertIsNotNone(check_forms.GATE.fullmatch("code:*"))
        self.assertEqual(check_forms.gate_errors(self.lesson, "model", "code:*"), [])
        forms = self.lesson / "forms"
        forms.mkdir()
        stages = forms / "stages.tsv"
        stages.write_text("n\tstage\tgate\tdepends\n"
                          "1\tmodel\tbuild;code:*\t-\n", encoding="utf-8")
        self.assertEqual(check_forms.check_stage_parts(stages)[0], [])

    def test_unknown_kinds_and_nonliteral_code_arguments_refuse(self):
        for bad in ("code", "code:all", "code:model", "code:*:seams",
                    "code: *", "mech:*", "unknown:*"):
            with self.subTest(gate=bad):
                self.assertIsNone(check_forms.GATE.fullmatch(bad))
                self.assertTrue(check_forms.gate_errors(self.lesson, "model", bad))

    def test_existing_gate_capture_groups_and_resolution_are_unchanged(self):
        self.assertEqual(check_forms.GATE.groups, 11)
        self.assertEqual(check_forms.gate_errors(self.lesson, "model", "build"), [])
        (self.lesson / "vectors" / "native").mkdir(parents=True)
        self.assertEqual(check_forms.gate_errors(self.lesson, "model", "vectors:native"), [])
        self.assertTrue(check_forms.gate_errors(self.lesson, "model", "vectors:missing"))
        acceptance = self.lesson / "acceptance" / "1"
        acceptance.mkdir(parents=True)
        (acceptance / "scenarios.tsv").write_text("step\tname\n01-normal\tNormal\n",
                                                 encoding="utf-8")
        self.assertEqual(check_forms.gate_errors(self.lesson, "model", "accept:1.1:01-normal"), [])
        self.assertTrue(check_forms.gate_errors(self.lesson, "model", "accept:1.1:missing"))


if __name__ == "__main__":
    unittest.main()
