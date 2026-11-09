"""Exact P/AC requirement-marker admission; full lesson registration is separate."""
from pathlib import Path
import re
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


class RegisteredSharedLessonControls(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="registered-pac-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "Platform/common/acceptance/spec/acceptance.norms.md"
        self.instructions = self.source.with_name("acceptance.README.md")
        self.russian = self.root / "Platform/common/ru/acceptance/spec/acceptance.norms.md"
        self.ru_instructions = self.russian.with_name("acceptance.README.md")
        for path in (self.source, self.instructions, self.russian, self.ru_instructions):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.ru_decides = "\u0420\u0435\u0448\u0430\u0435\u0442 \u0440\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f"
        self.ru_readiness = "\u0427\u0435\u043a\u043b\u0438\u0441\u0442 \u0433\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u0438"
        en = "# P/AC\n\n" + "\n\n".join(
            f"## N{i} Section\n\n" + ("<!-- req: P/AC-R001 -->\n\n" if i == 0 else "") + "Norm."
            for i in range(6))
        en += "\n\n## Implementation decides\n\nChoice.\n\n## Readiness checklist\n\n- [ ] **P/AC-01** Check.\n"
        ru = en.replace("<!-- req: P/AC-R001 -->\n\n", "").replace(
            "Implementation decides", self.ru_decides).replace("Readiness checklist", self.ru_readiness)
        self.source.write_text(en, encoding="utf-8")
        self.russian.write_text(ru, encoding="utf-8")
        self.instructions.write_text("# Instructions\n", encoding="utf-8")
        self.ru_instructions.write_text("# Instructions\n", encoding="utf-8")

    def check(self):
        check = Check(self.root, scope="platform")
        check.registered_shared_lessons()
        return check

    def test_explicit_registered_pair_uses_norms_without_process_requirements(self):
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["registered_shared_lessons"], 1)
        self.assertEqual(result.stats["norm_ids"], 1)
        self.assertFalse(result.stats["openapi"])
        self.assertFalse(result.stats["stage_rows"])

    def test_actual_published_registered_pair_and_instruction_documents(self):
        check = Check(ROOT, scope="platform")
        check.registered_shared_lessons()
        self.assertEqual(check.errors, [])
        text = (ROOT / "Platform/common/acceptance/spec/acceptance.norms.md").read_text()
        self.assertEqual(check.stats["norm_ids"], len(re.findall(r"(?m)^- \[ \] \*\*(P/AC-[0-9]+)\*\*", text)))
        self.assertEqual(check.stats["req_anchors"], len(re.findall(r"(?m)^<!-- req: P/AC-R[0-9]{3} -->$", text)))
        self.assertEqual(check.stats["registered_shared_lessons"], 1)

    def test_missing_documents_and_symlink_do_not_authorize_registration(self):
        self.instructions.unlink()
        self.assertTrue(any("regular nonsymlink" in e for e in self.check().errors))
        self.instructions.symlink_to(self.ru_instructions)
        self.assertTrue(any("regular nonsymlink" in e for e in self.check().errors))
        self.instructions.unlink()
        self.instructions.write_text("# Instructions\n")
        self.russian.unlink()
        self.assertTrue(any("regular nonsymlink" in e for e in self.check().errors))

    def test_only_registered_namespace_and_requirement_owner_are_allowed(self):
        original = self.source.read_text()
        for old, new in (("P/AC-R001", "P/ZZ-R001"), ("**P/AC-01**", "**P/ZZ-01**"),
                         ("P/AC-R001", "P/05-R001")):
            with self.subTest(new=new):
                self.source.write_text(original.replace(old, new))
                self.assertTrue(any("registered" in e for e in self.check().errors))
        self.source.write_text(original)
        other = self.source.with_name("other.norms.md")
        other.write_text("<!-- req: P/AC-R099 -->\n")
        self.assertTrue(any("belong to Platform/common/acceptance/spec/acceptance.norms.md" in e
                            for e in self.check().errors))
        other.unlink()
        other = self.source.with_name("other.README.md")
        other.write_text("<!-- req: P/AC-R099 -->\n")
        self.assertTrue(any("belong to Platform/common/acceptance/spec/acceptance.norms.md" in e
                            for e in self.check().errors))
        other.write_text(chr(96) * 3 + "markdown\n<!-- req: P/AC-R099 -->\n" + chr(96) * 3 + "\n")
        self.assertEqual(self.check().errors, [])

    def test_sections_are_unique_ordered_and_decision_readiness_are_required(self):
        original = self.source.read_text()
        for changed in (original.replace("## N1 Section", "## N0 Section"),
                        original.replace("## Implementation decides", "## Other"),
                        original.replace("## Readiness checklist", "## Other"),
                        original + "\n## Readiness checklist\n"):
            with self.subTest(text=changed):
                self.source.write_text(changed)
                self.assertTrue(self.check().errors)
        self.source.write_text(original)

    def test_checklist_differences_duplicates_and_malformed_rows_refuse(self):
        original = self.russian.read_text()
        for changed in (original.replace("P/AC-01", "P/AC-02"),
                        original + "\n- [ ] **P/AC-01** Duplicate.\n",
                        original.replace("**P/AC-01**", "P/AC-01")):
            with self.subTest(text=changed):
                self.russian.write_text(changed)
                self.assertTrue(any("checklist" in e for e in self.check().errors))
        self.russian.write_text(original)

    def test_stable_requirement_ids_are_unique_owned_and_never_reuse_removed(self):
        original = self.source.read_text()
        for extra in ("\n<!-- req: P/AC-R001 -->\n",
                      "\n<!-- removed: P/AC-R001 by ADR-0135 -->\n"):
            self.source.write_text(original + extra)
            self.assertTrue(any("repeats or reuses" in e for e in self.check().errors))
        # Stable ids can be inserted by meaning; physical number ordering is not a rule.
        self.source.write_text(original.replace("P/AC-R001", "P/AC-R003") +
                               "\n<!-- req: P/AC-R001 -->\n<!-- removed: P/AC-R002 by ADR-0135 -->\n")
        self.assertEqual(self.check().errors, [])

    def test_req_markers_belong_only_to_the_english_norms_not_ru_or_instructions(self):
        for path in (self.russian, self.instructions, self.ru_instructions):
            original = path.read_text()
            path.write_text(original + "\n<!-- req: P/AC-R099 -->\n")
            self.assertTrue(any("only to the registered English norms" in e for e in self.check().errors))
            path.write_text(original)

    def test_numeric_norm_parser_defaults_and_foreign_pac_checklist_stay_strict(self):
        check = Check(self.root, scope="platform")
        text = "\n".join(f"## N{i} Section" for i in range(6))
        text += "\n## " + self.ru_decides + "\n## " + self.ru_readiness + "\n- [ ] **P/05-01** Check.\n"
        self.assertEqual(check.norms(self.root / "05.norms.md", text, "P/05"), ["P/05-01"])
        self.assertEqual(check.errors, [])
        check.norms(self.root / "05.norms.md", text.replace("P/05-01", "P/AC-01"), "P/05")
        self.assertTrue(any("foreign checklist" in e for e in check.errors))


    def test_platform_pipeline_calls_the_explicit_shared_registration(self):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from unittest.mock import patch
        import check_spec
        methods = ("lesson", "vector_hashes", "outcome_readers", "family_read", "common_contracts",
                   "stub_text", "library_defects", "layer_words", "english_mirrors", "check_tables",
                   "check_machines", "check_forms", "check_cyrillic")
        args = SimpleNamespace(root=self.root, exceptions=None, strict_coverage=False,
                               cyrillic_debt=self.root / "debt.tsv")
        with ExitStack() as stack:
            stack.enter_context(patch.object(check_spec, "environment", return_value=[]))
            stack.enter_context(patch.object(Check, "lessons_table", return_value=(False, [])))
            for method in methods:
                stack.enter_context(patch.object(Check, method))
            result = check_spec._platform_phase(args, ["Platform/01-store/01-store.md"])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["registered_shared_lessons"], 1)
        self.assertEqual(result.stats["norm_ids"], 1)


if __name__ == "__main__":
    unittest.main()
