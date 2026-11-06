"""Check shared gate.py parsing against check_forms (Codex C4)."""
import sys
import unittest
from pathlib import Path

import gate

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import check_forms  # noqa: E402

STAGES = ROOT / "Platform/01-store/forms/stages.tsv"


class Gate(unittest.TestCase):
    def test_items(self):
        got = gate.parse("tests:1.1:a,b;tests:1.1:s1:seams;accept:1.3:*;vectors:jcs;build")
        self.assertEqual([c.kind for c in got], ["tests", "tests", "accept", "vectors", "build"])
        self.assertEqual((got[0].chapter, got[0].names, got[0].seams), ("1.1", ("a", "b"), False))
        self.assertTrue(got[1].seams)
        self.assertIsNone(got[2].names)
        self.assertEqual(got[3].package, "jcs")

    def test_refusals(self):
        for bad in ("", "build;", ";build", "build;;vectors:jcs", "build; vectors:jcs", " build", "vectors:jcs ",
                    "build;build", "tests:1.1:a,a", "tests:1.1:", "tests:x:a", "frob:1", "tests:store_core",
                    "vectors:", "accept:1.1:a:seams"):
            with self.subTest(bad=bad), self.assertRaises(gate.GateError):
                gate.parse(bad)

    def test_form(self):
        """Parse every P/01 gate cell and require check_forms to accept each element."""
        lines = [x.split("\t") for x in STAGES.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
        head = lines[0]
        for cells in lines[1:]:
            r = dict(zip(head, cells))
            for c in gate.parse(r["gate"], r["stage"]):
                self.assertTrue(check_forms.GATE.fullmatch(c.text), c.text)

    def test_agrees_with_check_forms(self):
        """Reject each invalid element that check_forms rejects: whitespace, empty elements and unknown kinds."""
        for item in ("", " build", "build ", "vectors:jcs x", "frob:1", "tests:1.1", "accept:1.1:a:seams"):
            self.assertIsNone(check_forms.GATE.fullmatch(item), item)
            with self.assertRaises(gate.GateError):
                gate.parse(item)


if __name__ == "__main__":
    unittest.main()
