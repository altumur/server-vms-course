"""«Данные»: a «See also» line inside the list does not drop later kinds; a broken list is an error (P01.200 judge)."""
import unittest
from pathlib import Path

from check_spec import Check

ROOT = Path(__file__).resolve().parents[3]
KEY = "/etc/w2c/configstore-rights.json"


class DataParagraph(unittest.TestCase):
    def check(self):
        check = Check(ROOT, scope="platform")
        check.load_catalog(ROOT / "Platform/common/data/catalog.tsv")
        return check

    def run_text(self, body):
        check = self.check()
        if check.catalog is None:
            self.skipTest("no catalog in this check")
        said = check.data_paragraph(Path("x.md"), "**Данные** (catalog):\n" + body, "P/01.2", "P/01")
        return check, said

    def test_see_also_line_inside_the_list_is_skipped(self):
        check, said = self.run_text(f"- владеет: `{KEY}`;\n  См. также: P/01.2-R006.\n- пишет: строк нет;\n- читает: `{KEY}`.\n")
        self.assertIn(KEY, said["читает"])
        self.assertFalse([e for e in check.errors if "broken" in e], check.errors)

    def test_broken_list_is_an_error(self):
        check, _ = self.run_text(f"- владеет: `{KEY}`;\nsome prose\n- читает: `{KEY}`.\n")
        self.assertTrue([e for e in check.errors if "broken" in e], check.errors)


if __name__ == "__main__":
    unittest.main()
