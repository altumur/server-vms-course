"""#row:<column>=<value>&… — a TSV row addressed by named columns when the first column repeats (the Architect on P03.29)."""
import tempfile
import unittest
from pathlib import Path

import m_form


class CompositeKey(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "f.tsv"
        self.path.write_text("# comment\nchapter\tname\tpath\treader\n3\ta\t\tx\n3\tb\t\ty\n3\tb\tp\ty\n", encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def problem(self, fragment):
        return m_form._tsv_problem(self.path, fragment, {})

    def test_first_column_repeats_is_not_an_address(self):
        self.assertIn("repeats", self.problem("row:3"))

    def test_composite_key_finds_one_row(self):
        self.assertIsNone(self.problem("row:chapter=3&name=a"))
        self.assertIsNone(self.problem("row:name=b&path=p"))
        self.assertIsNone(self.problem("row:name=b&path="))          # an empty cell is a value

    def test_composite_key_errors(self):
        self.assertIn("match", self.problem("row:chapter=3&name=b&reader=y"))
        self.assertIn("no row", self.problem("row:name=z"))
        self.assertIn("no column", self.problem("row:nope=1"))
        self.assertIn("twice", self.problem("row:name=a&name=a"))


if __name__ == "__main__":
    unittest.main()
