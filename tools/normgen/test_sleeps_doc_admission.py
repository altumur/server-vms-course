"""Exact judge-document admission without a new executable acceptance format."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/lesson-spec/scripts"
sys.path.insert(0, str(SCRIPTS))
from check_spec import Check


class SleepsDocumentAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.acceptance = self.root / "example/acceptance"
        self.acceptance.mkdir(parents=True)
        (self.acceptance / "README.md").write_text("# Acceptance\n", encoding="utf-8")
        (self.acceptance / "corrections.tsv").write_text(
            "date\tsample\tfix\tlanguages\n", encoding="utf-8")
        # An existing format supplies coverage; the Markdown document must not.
        (self.acceptance / "seams.tsv").write_text("", encoding="utf-8")
        self.doc = self.acceptance / "sleeps.cases.md"

    def check(self):
        check = Check(self.root)
        result = check.acceptance(self.acceptance, "P/03")
        return check, result

    def test_exact_document_uses_read_markdown_and_links_without_scenarios(self):
        target = self.root / "target.md"
        target.write_text("# Target\n", encoding="utf-8")
        self.doc.write_text("# Sleeps\n[Target](../../target.md#target)\n", encoding="utf-8")
        check = Check(self.root)
        with patch.object(check, "read", wraps=check.read) as read, \
                patch.object(check, "markdown", wraps=check.markdown) as markdown, \
                patch.object(check, "scenarios", side_effect=AssertionError("document executed")) as scenarios:
            result = check.acceptance(self.acceptance, "P/03")
        self.assertEqual(check.errors, [])
        read.assert_any_call(self.doc)
        markdown.assert_any_call(self.doc, self.doc.read_text(encoding="utf-8"))
        scenarios.assert_not_called()
        self.assertEqual(check.stats["local_links"], 1)
        self.assertNotIn(self.doc, result[0])
        self.assertEqual(result[1:], (None, None, None, {}))
        self.assertEqual(check.excepted, [])
        self.assertFalse(check.stats["scenarios"])
        self.assertFalse(check.stats["steps"])

    def test_document_alone_is_not_an_acceptance_format(self):
        (self.acceptance / "seams.tsv").unlink()
        self.doc.write_text("# Sleeps\n", encoding="utf-8")
        check, _ = self.check()
        self.assertEqual(len(check.errors), 1, check.errors)
        self.assertIn("no supported acceptance table", check.errors[0])
        self.assertEqual(check.excepted, [])

    def test_existing_markdown_and_link_failures_are_reported(self):
        for text, message in [
            ("# Sleeps\n{{unfilled}}\n", "unfilled template marker"),
            ("# Sleeps\n[Missing](missing.md)\n", "missing link target"),
            ("# Sleeps\n[Missing](#missing)\n", "missing anchor"),
        ]:
            with self.subTest(message=message):
                self.doc.write_text(text, encoding="utf-8")
                check, _ = self.check()
                self.assertTrue(any(message in error for error in check.errors), check.errors)
                self.assertFalse(any("unsupported acceptance entry" in error for error in check.errors))

    def test_nonfile_and_symlink_do_not_bypass_ordinary_file_guard(self):
        target = self.root / "target.md"
        target.write_text("# Target\n", encoding="utf-8")
        for kind in ("directory", "file-symlink", "broken-symlink"):
            with self.subTest(kind=kind):
                if self.doc.is_symlink() or self.doc.is_file():
                    self.doc.unlink()
                elif self.doc.is_dir():
                    self.doc.rmdir()
                if kind == "directory":
                    self.doc.mkdir()
                else:
                    self.doc.symlink_to(target if kind == "file-symlink" else self.root / "absent.md")
                check = Check(self.root)
                with patch.object(check, "read", wraps=check.read) as read:
                    check.acceptance(self.acceptance, "P/03")
                self.assertTrue(any("must be a file" in error for error in check.errors), check.errors)
                self.assertNotIn(self.doc, [call.args[0] for call in read.call_args_list])
                if kind == "directory":
                    self.doc.rmdir()
                else:
                    self.doc.unlink()

    def test_other_markdown_names_remain_unsupported(self):
        for name in ("other.cases.md", "sleeps.md", "sleeps.cases.extra.md"):
            with self.subTest(name=name):
                path = self.acceptance / name
                path.write_text("# Other\n", encoding="utf-8")
                check, _ = self.check()
                self.assertTrue(any("unsupported acceptance entry" in error for error in check.errors), check.errors)
                path.unlink()

    def test_existing_utf8_read_guard_applies(self):
        self.doc.write_bytes(b"\xff")
        check, _ = self.check()
        self.assertTrue(any("utf-8" in error for error in check.errors), check.errors)
        self.assertFalse(any("unsupported acceptance entry" in error for error in check.errors))

    def test_no_tolerance_exception_or_changed_scenario_accounting(self):
        scenarios = self.acceptance / "scenarios.tsv"
        scenarios.write_text("# scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n", encoding="utf-8")
        before = {p.name: p.read_bytes() for p in (self.acceptance / "README.md", scenarios)}
        baseline, expected = self.check()
        self.assertEqual(baseline.errors, [])
        self.doc.write_text("# Sleeps\n", encoding="utf-8")
        check, actual = self.check()
        self.assertEqual(check.errors, [])
        self.assertEqual(actual, expected)
        self.assertEqual(check.stats, baseline.stats)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.acceptance / "README.md", scenarios)})
        check = Check(self.root)
        check.registry[("P/03", "acceptance-entry", "sleeps.cases.md")] = "old exception"
        check.acceptance(self.acceptance, "P/03")
        self.assertTrue(any("stale exception acceptance-entry" in error for error in check.errors), check.errors)
        self.assertEqual(check.excepted, [])


if __name__ == "__main__":
    unittest.main()
