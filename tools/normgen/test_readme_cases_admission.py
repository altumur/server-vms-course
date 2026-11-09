"""Judge-only README case documents keep ordinary Markdown and input guards."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
from check_spec import Check
from v7 import spec


class ReadmeCasesAdmissionControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.acceptance = self.root / "example/acceptance"
        self.family = self.root / spec.FAMILY_READ
        for directory in (self.acceptance, self.family):
            directory.mkdir(parents=True)
            (directory / "README.md").write_text("# Format\n", encoding="utf-8")
        (self.acceptance / "corrections.tsv").write_text(
            "date\tsample\tfix\tlanguages\n", encoding="utf-8")
        (self.acceptance / "seams.tsv").write_text("", encoding="utf-8")
        (self.family / "01.tsv").write_text("\t".join(spec.FR_HEADER) + "\n", encoding="utf-8")

    def check(self, kind):
        check = Check(self.root)
        if kind == "acceptance":
            result = check.acceptance(self.acceptance, "P/03")
        else:
            check.v7, check.catalog = True, {}
            with patch.object(spec, "read_catalog", return_value=[]), \
                    patch.object(spec, "key_templates", return_value=({}, [])):
                result = check.family_read()
        return check, result

    def directory(self, kind):
        return self.acceptance if kind == "acceptance" else self.family

    def test_acceptance_document_is_read_and_markdown_checked_without_execution(self):
        doc = self.acceptance / "README.cases.md"
        # A linked resource need not itself be an admitted acceptance entry.
        target = self.root / "target.md"
        target.write_text("# Target\n", encoding="utf-8")
        doc.write_text("# Cases\n[Target](../../target.md#target)\n", encoding="utf-8")
        check = Check(self.root)
        with patch.object(check, "read", wraps=check.read) as read, \
                patch.object(check, "markdown", wraps=check.markdown) as markdown, \
                patch.object(check, "scenarios", side_effect=AssertionError("document executed")) as scenarios:
            result = check.acceptance(self.acceptance, "P/03")
        self.assertEqual(check.errors, [])
        read.assert_any_call(doc)
        markdown.assert_any_call(doc, doc.read_text())
        scenarios.assert_not_called()
        self.assertNotIn(doc, result[0])
        self.assertEqual(result[1:], (None, None, None, {}))
        self.assertEqual(check.stats["local_links"], 1)
        self.assertFalse(check.stats["scenarios"])
        self.assertEqual(check.excepted, [])

    def test_family_document_uses_markdown_without_becoming_a_vector_table(self):
        baseline, _ = self.check("family")
        doc = self.family / "README.cases.md"
        doc.write_text("# Cases\n[Format](README.md#format)\n", encoding="utf-8")
        check, _ = self.check("family")
        self.assertEqual(check.errors, [])
        self.assertEqual(check.stats["family_read_tables"], baseline.stats["family_read_tables"])
        self.assertEqual(check.stats["family_read_rows"], baseline.stats["family_read_rows"])
        self.assertEqual(check.stats["local_links"], 1)
        self.assertEqual(check.excepted, [])

    def test_document_is_not_a_substitute_for_executable_acceptance(self):
        (self.acceptance / "seams.tsv").unlink()
        (self.acceptance / "README.cases.md").write_text("# Cases\n", encoding="utf-8")
        check, _ = self.check("acceptance")
        self.assertEqual(len(check.errors), 1, check.errors)
        self.assertIn("no supported acceptance table", check.errors[0])

    def test_existing_markdown_link_template_and_raw_html_refusals_apply(self):
        for kind in ("acceptance", "family"):
            doc = self.directory(kind) / "README.cases.md"
            for text, message in (
                ("# Cases\n{{unfilled}}\n", "unfilled template marker"),
                ("# Cases\n[Missing](absent.md)\n", "missing link target"),
                ("# Cases\n[Missing](#absent)\n", "missing anchor"),
                ("# Cases\n<a href='absent.md'>bad</a>\n", "unsupported raw HTML"),
            ):
                with self.subTest(kind=kind, message=message):
                    doc.write_text(text, encoding="utf-8")
                    check, _ = self.check(kind)
                    self.assertTrue(any(message in error for error in check.errors), check.errors)
                    self.assertFalse(any("unsupported acceptance entry" in error for error in check.errors))

    def test_nonregular_documents_and_symlinks_are_refused_before_read(self):
        target = self.root / "target.md"
        target.write_text("# Target\n", encoding="utf-8")
        for kind in ("acceptance", "family"):
            doc = self.directory(kind) / "README.cases.md"
            for shape in ("directory", "file-symlink", "broken-symlink"):
                with self.subTest(kind=kind, shape=shape):
                    if shape == "directory":
                        doc.mkdir()
                    else:
                        doc.symlink_to(target if shape == "file-symlink" else self.root / "absent.md")
                    original = Check.read
                    def guarded_read(check, path):
                        self.assertNotEqual(path, doc, "nonregular document was read")
                        return original(check, path)
                    with patch.object(Check, "read", guarded_read):
                        check, _ = self.check(kind)
                    self.assertTrue(any("must be a file" in error for error in check.errors), check.errors)
                    if shape == "directory":
                        doc.rmdir()
                    else:
                        doc.unlink()

    def test_other_markdown_filenames_remain_unsupported(self):
        for kind in ("acceptance", "family"):
            for name in ("other.cases.md", "README.extra.md", "README.cases.md.extra"):
                with self.subTest(kind=kind, name=name):
                    path = self.directory(kind) / name
                    path.write_text("# Other\n", encoding="utf-8")
                    check, _ = self.check(kind)
                    self.assertTrue(any("unsupported acceptance entry" in error or "family-read: only" in error
                                        for error in check.errors), check.errors)
                    path.unlink()

    def test_document_read_requires_utf8_in_both_locations(self):
        for kind in ("acceptance", "family"):
            with self.subTest(kind=kind):
                (self.directory(kind) / "README.cases.md").write_bytes(b"\xff")
                check, _ = self.check(kind)
                self.assertTrue(any("utf-8" in error for error in check.errors), check.errors)

    def test_family_format_readme_and_table_header_stay_required(self):
        (self.family / "README.cases.md").write_text("# Cases\n", encoding="utf-8")
        (self.family / "README.md").unlink()
        check, _ = self.check("family")
        self.assertTrue(any("package needs README.md" in error for error in check.errors), check.errors)
        (self.family / "README.md").write_text("# Format\n", encoding="utf-8")
        (self.family / "01.tsv").write_text("wrong\theader\n", encoding="utf-8")
        check, _ = self.check("family")
        self.assertTrue(any("header must be" in error for error in check.errors), check.errors)

    def test_existing_scenario_accounting_and_stale_exception_rule_are_preserved(self):
        table = self.acceptance / "scenarios.tsv"
        table.write_text("# scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n")
        baseline, before = self.check("acceptance")
        self.assertEqual(baseline.errors, [])
        doc = self.acceptance / "README.cases.md"
        doc.write_text("# Cases\n", encoding="utf-8")
        check, after = self.check("acceptance")
        self.assertEqual(check.errors, [])
        self.assertEqual(before, after)
        self.assertEqual(baseline.stats, check.stats)
        stale = Check(self.root)
        stale.registry[("P/03", "acceptance-entry", "README.cases.md")] = "old exception"
        stale.acceptance(self.acceptance, "P/03")
        self.assertTrue(any("stale exception acceptance-entry" in error for error in stale.errors), stale.errors)
        self.assertEqual(stale.excepted, [])

    def test_actual_five_published_documents_pass_existing_markdown_checks(self):
        paths = [ROOT / f"Platform/02-installer/acceptance/{n}/README.cases.md" for n in range(2, 6)]
        paths.append(ROOT / "Platform/common/vectors/family-read/README.cases.md")
        check = Check(ROOT)
        for doc in paths:
            text = check.read(doc)
            self.assertIsNotNone(text)
            check.markdown(doc, text)
        self.assertEqual(check.errors, [])


if __name__ == "__main__":
    unittest.main()
