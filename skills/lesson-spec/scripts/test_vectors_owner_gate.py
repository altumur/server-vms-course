"""Gate vectors:<owner>/<package> (Architect's decision on question 5 of the P/03 audit, 2026-11-11)."""
import tempfile, unittest
from pathlib import Path
import check_forms


class VectorsOwnerGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "Platform"
        (root / "common" / "vectors" / "door-token").mkdir(parents=True)
        (root / "common" / "vectors" / "consumers.tsv").write_text(
            "# consumers\npackage\ttable\tlesson\tsource\ncommon/door-token\tplace.tsv\t03-worker\tx\n", encoding="utf-8")
        self.worker = root / "03-worker"; (self.worker / "vectors" / "own").mkdir(parents=True)
        self.store = root / "01-store"; (self.store / "vectors").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_consumer_lesson_accepts_owned_package(self):
        self.assertEqual(check_forms.gate_errors(self.worker, "s", "vectors:common/door-token"), [])

    def test_lesson_without_consumers_row_is_refused(self):
        self.assertTrue(check_forms.gate_errors(self.store, "s", "vectors:common/door-token"))

    def test_missing_package_is_refused(self):
        self.assertTrue(check_forms.gate_errors(self.worker, "s", "vectors:common/nosuch"))

    def test_own_package_as_before(self):
        self.assertEqual(check_forms.gate_errors(self.worker, "s", "vectors:own"), [])
        self.assertTrue(check_forms.gate_errors(self.worker, "s", "vectors:missing"))


if __name__ == "__main__":
    unittest.main()
