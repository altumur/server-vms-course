"""Exact P/AC requirement-marker admission; full lesson registration is separate."""
from pathlib import Path
import unittest

from check_spec import Check, REQ_ANCHOR

ROOT = Path(__file__).resolve().parents[3]


class PacRequirementMarkerControls(unittest.TestCase):
    def test_actual_published_pac_norms_pass_existing_markdown_checks(self):
        path = ROOT / "Platform/common/acceptance/spec/acceptance.norms.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("<!-- req: P/AC-R001 -->", text)
        check = Check(ROOT, scope="platform")
        check.markdown(path, text)
        self.assertEqual(check.errors, [])

    def test_exact_pac_requirement_and_removed_markers(self):
        for text in ("<!-- req: P/AC-R001 -->",
                     "<!-- removed: P/AC-R001 by ADR-0135 -->"):
            with self.subTest(text=text):
                self.assertIsNotNone(REQ_ANCHOR.fullmatch(text))

    def test_unknown_namespace_malformed_marker_and_other_html_still_refuse(self):
        for text in ("<!-- req: P/ZZ-R001 -->",
                     "<!-- req: P/AC.1-R001 -->",
                     "<!-- req: P/AC-R01 -->",
                     "<!-- req: P/AC-R0001 -->",
                     "<!-- unrelated comment -->", "<script>bad()</script>"):
            with self.subTest(text=text):
                self.assertIsNone(REQ_ANCHOR.fullmatch(text))
                check = Check(ROOT, scope="platform")
                check.markdown(ROOT / "Platform/common/acceptance/spec/acceptance.norms.md", text)
                self.assertTrue(any("unsupported raw HTML" in error for error in check.errors),
                                check.errors)

    def test_numeric_requirement_markers_keep_their_original_admission(self):
        for text in ("<!-- req: P/05-R001 -->", "<!-- req: P/05.1-R001 -->",
                     "<!-- removed: P/05.1-R001 by ADR-0122 -->"):
            with self.subTest(text=text):
                self.assertIsNotNone(REQ_ANCHOR.fullmatch(text))
                check = Check(ROOT, scope="platform")
                check.markdown(ROOT / "Platform/05-resource/spec/05-resource.norms.md", text)
                self.assertEqual(check.errors, [])


if __name__ == "__main__":
    unittest.main()
