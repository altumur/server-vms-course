import re
import tempfile
import unittest
from pathlib import Path

from check_spec import Check

ROOT = Path(__file__).resolve().parents[3]


class StageNormCoverageControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stage-norm-coverage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "Platform/01-store"
        self.spec = self.home / "spec"
        self.forms = self.home / "forms"
        self.spec.mkdir(parents=True)
        self.forms.mkdir()
        self.source = self.spec / "01.1-store.norms.md"
        self.source.write_text("## Readiness checklist\n\n- [ ] **P/01.1-01** First item.\n"
                               "- [ ] **P/01.1-02** Second item.\n", encoding="utf-8")

    def stages(self, norms):
        path = self.forms / "stages.tsv"
        path.write_text("n\tstage\tnorms\tgate\n" + "".join(
            f"{i}\ts{i}\t{cell}\tbuild\n" for i, cell in enumerate(norms, 1)), encoding="utf-8")
        return path

    def check(self):
        result = Check(self.root, scope="platform")
        result.stage_norms(self.home, "P/01")
        return result

    def test_each_item_once_with_semicolon_and_nonitem_references_passes(self):
        self.stages(["P/01.1 N1; forms/input.tsv;  P/01.1-02 ; P/01.1-01"])
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["stage_norm_items"], 2)
        self.assertEqual(result.stats["stage_norm_placements"], 2)

    def test_missing_item_and_removal_of_all_item_elements_refuse(self):
        for cells in (["P/01.1-01"], ["P/01.1 N1; forms/input.tsv"], [""]):
            with self.subTest(cells=cells):
                self.stages(cells)
                errors = self.check().errors
                self.assertTrue(any("P/01.1-02 is at no stage" in error for error in errors), errors)

    def test_duplicate_in_one_cell_or_across_stages_refuses(self):
        for cells in (["P/01.1-01; P/01.1-02; P/01.1-01"],
                      ["P/01.1-01; P/01.1-02", "P/01.1-01"]):
            with self.subTest(cells=cells):
                self.stages(cells)
                self.assertTrue(any("P/01.1-01 repeats" in error for error in self.check().errors))

    def test_extra_unknown_or_foreign_exact_item_refuses(self):
        for extra in ("P/01.9-99", "P/02.1-01"):
            with self.subTest(extra=extra):
                self.stages(["P/01.1-01; P/01.1-02; " + extra])
                self.assertTrue(any(extra + " is no checklist item" in error for error in self.check().errors))

    def test_item_grammar_does_not_expand_ranges_commas_or_backticks(self):
        for wrong in ("P/01.1-01,P/01.1-02", "P/01.1-01–02",
                      chr(96) + "P/01.1-01" + chr(96) + "; P/01.1-02",
                      "P/01.1-01 note; P/01.1-02"):
            with self.subTest(cell=wrong):
                self.stages([wrong])
                self.assertTrue(any("P/01.1-01 is at no stage" in error for error in self.check().errors))

    def test_only_active_canonical_checklist_items_count_not_examples_or_ru(self):
        self.source.write_text(self.source.read_text() +
                               "\n~~~\n- [ ] **P/01.1-98** Fenced example.\n~~~\n"
                               "\n<!--\n- [ ] **P/01.1-97** Comment example.\n-->\n"
                               "\nThe prose says **P/01.1-96**.\n", encoding="utf-8")
        translated = self.home / "ru/spec/01.1-store.norms.md"
        translated.parent.mkdir(parents=True)
        translated.write_text("## Readiness checklist\n\n- [ ] **P/01.1-99** Translation only.\n",
                              encoding="utf-8")
        self.stages(["P/01.1-01; P/01.1-02"])
        self.assertEqual(self.check().errors, [])

    def test_withdrawn_item_needs_no_stage_and_may_still_be_named_once(self):
        # A withdrawn item (m_form.WITHDRAWN) keeps its id, not a requirement (P01.176 item 4, P01.228).
        self.source.write_text(self.source.read_text() + "- [ ] **P/01.1-03** removed: `ADR-0133`; moved to P/08.0\n",
                               encoding="utf-8")
        for cells in (["P/01.1-01; P/01.1-02"], ["P/01.1-01; P/01.1-02; P/01.1-03"]):
            with self.subTest(cells=cells):
                self.stages(cells)
                result = self.check()
                self.assertEqual(result.errors, [])
                self.assertEqual(result.stats["stage_norm_items"], 3)
                self.assertEqual(result.stats["stage_norm_withdrawn"], 1)
        self.stages(["P/01.1-01; P/01.1-02; P/01.1-03", "P/01.1-03"])
        self.assertTrue(any("P/01.1-03 repeats" in error for error in self.check().errors))

    def test_an_item_without_the_withdrawal_form_still_needs_a_stage(self):
        for line in ("- [ ] **P/01.1-03** [reading] removed: `ADR-0133`\n", "- [ ] **P/01.1-03** removed: later\n",
                     "~~~\n- [ ] **P/01.1-04** removed: `ADR-0133`\n~~~\n- [ ] **P/01.1-03** live\n"):
            with self.subTest(line=line):
                self.source.write_text("## Readiness checklist\n\n- [ ] **P/01.1-01** First item.\n"
                                       "- [ ] **P/01.1-02** Second item.\n" + line, encoding="utf-8")
                self.stages(["P/01.1-01; P/01.1-02"])
                self.assertTrue(any("P/01.1-03 is at no stage" in error for error in self.check().errors))

    def test_canonical_foreign_item_is_not_authorized_by_stage_copy(self):
        self.source.write_text(self.source.read_text() + "- [ ] **P/02.1-01** Wrong owner.\n",
                               encoding="utf-8")
        self.stages(["P/01.1-01; P/01.1-02; P/02.1-01"])
        errors = self.check().errors
        self.assertTrue(any("foreign checklist item 'P/02.1-01'" in error for error in errors), errors)
        self.assertTrue(any("P/02.1-01 is no checklist item" in error for error in errors), errors)

    def test_malformed_table_and_missing_public_file_cannot_use_kit(self):
        path = self.stages(["P/01.1-01; P/01.1-02"])
        for text in ("stage\tgate\ns1\tbuild\n",
                     "stage\tnorms\tnorms\ns1\tP/01.1-01\tP/01.1-02\n",
                     "stage\tnorms\ns1\n"):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                self.assertTrue(self.check().errors)
        path.unlink()
        (self.forms / "stages.kit.tsv").write_text("stage\tnorms\ns1\tP/01.1-01; P/01.1-02\n")
        self.assertTrue(any("ordinary stages.tsv" in error for error in self.check().errors))

    def test_canonical_inputs_must_be_ordinary_and_nonempty(self):
        self.stages(["P/01.1-01; P/01.1-02"])
        saved = self.spec / "saved.md"
        self.source.rename(saved)
        self.source.symlink_to(saved)
        self.assertTrue(any("ordinary canonical norms" in error for error in self.check().errors))
        self.source.unlink()
        self.source.write_text("## Readiness checklist\n", encoding="utf-8")
        self.stages([""])
        self.assertTrue(any("no canonical checklist items" in error for error in self.check().errors))

    def optional(self, cells):
        # A lesson outside STAGE_NORM_REQUIRED (P/02 joined it after part 2a, P02.23); P/05 has not.
        home = self.root / "Platform/05-resource"
        (home / "forms").mkdir(parents=True)
        (home / "spec").mkdir()
        (home / "spec/05.1-resource.norms.md").write_text(
            "## Readiness checklist\n\n- [ ] **P/05.1-01** First.\n"
            "- [ ] **P/05.1-02** Second.\n", encoding="utf-8")
        (home / "forms/stages.tsv").write_text(
            "stage\tnorms\n" + "".join(f"s{i}\t{cell}\n" for i, cell in enumerate(cells, 1)),
            encoding="utf-8")
        result = Check(self.root, scope="platform")
        result.stage_norms(home, "P/05")
        return result

    def test_nonadopted_lesson_without_item_elements_keeps_old_prose(self):
        result = self.optional(["P/05.1 N1; forms/example.tsv"])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["stage_norm_items"], 0)

    def test_nonadopted_lesson_valid_partial_items_do_not_require_full_coverage(self):
        result = self.optional(["P/05.1-01"])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["stage_norm_items"], 2)
        self.assertEqual(result.stats["stage_norm_placements"], 1)

    def test_nonadopted_lesson_unknown_or_repeated_elements_still_refuse(self):
        result = self.optional(["P/05.1-01; P/05.1-01; P/05.9-99"])
        self.assertTrue(any("P/05.1-01 repeats" in error for error in result.errors), result.errors)
        self.assertTrue(any("P/05.9-99 is no checklist item" in error for error in result.errors), result.errors)
        self.assertFalse(any("P/05.1-02 is at no stage" in error for error in result.errors), result.errors)

    def test_actual_published_p01_source_items_are_all_placed_once(self):
        home = ROOT / "Platform/01-store"
        result = Check(ROOT, scope="platform")
        result.stage_norms(home, "P/01")
        texts = [path.read_text(encoding="utf-8") for path in sorted((home / "spec").glob("*.norms.md"))]
        expected = [value for text in texts
                    for value in re.findall(r"(?m)^- \[ \] \*\*(P/01\.[0-9]+-[0-9]{2})\*\*", text)]
        # A withdrawn item («removed: `ADR-…`») keeps its id and needs no stage (P01.228, 408deb448); P01.257
        # (af760f774) withdrew P/01.1-21 and the stage table dropped it. Every other item is placed exactly once.
        withdrawn = [value for text in texts
                     for value in re.findall(r"(?m)^- \[ \] \*\*(P/01\.[0-9]+-[0-9]{2})\*\* removed: `ADR-[0-9]{4}`", text)]
        self.assertTrue(expected)
        self.assertTrue(set(withdrawn) < set(expected))
        placed = [value.strip() for line in (home / "forms/stages.tsv").read_text(encoding="utf-8").split("\n")
                  if line and not line.startswith("#") for value in line.split("\t")[3].split(";")
                  if re.fullmatch(r"P/01\.[0-9]+-[0-9]{2}", value.strip())]
        self.assertEqual(sorted(placed), sorted(value for value in expected if value not in withdrawn))
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["stage_norm_items"], len(set(expected)))
        self.assertEqual(result.stats["stage_norm_withdrawn"], len(set(withdrawn)))
        self.assertEqual(result.stats["stage_norm_placements"], len(expected) - len(withdrawn))


if __name__ == "__main__":
    unittest.main()


class ItemFormByChapters(unittest.TestCase):
    """Audit P/04, defect 1: a lesson without chapters names items P/NN-MM, a lesson with chapters P/NN.K-MM."""

    def lesson(self, source_name, items, cell):
        temp = tempfile.TemporaryDirectory(prefix="stage-norm-form-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        home = root / "Platform/04-controller"
        (home / "spec").mkdir(parents=True)
        (home / "forms").mkdir()
        (home / "spec" / source_name).write_text(
            "## Readiness checklist\n\n" + "".join(f"- [ ] **{i}** Item.\n" for i in items), encoding="utf-8")
        (home / "forms/stages.tsv").write_text(f"n\tstage\tnorms\tgate\n1\ts1\t{cell}\tbuild\n", encoding="utf-8")
        result = Check(root, scope="platform")
        result.stage_norms(home, "P/04")
        return result

    def test_lesson_without_chapters_accepts_plain_items(self):
        result = self.lesson("04-controller.norms.md", ["P/04-01"], "P/04-01")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["stage_norm_placements"], 1)

    def test_lesson_without_chapters_refuses_chapter_item(self):
        result = self.lesson("04-controller.norms.md", ["P/04-01"], "P/04.1-01")
        self.assertTrue(any("item form of a lesson with chapters" in e for e in result.errors), result.errors)

    def test_lesson_with_chapters_refuses_plain_item(self):
        result = self.lesson("04.1-controller.norms.md", ["P/04.1-01"], "P/04-01")
        self.assertTrue(any("item form of a lesson without chapters" in e for e in result.errors), result.errors)

    def test_lesson_without_chapters_refuses_chapter_item_in_source(self):
        result = self.lesson("04-controller.norms.md", ["P/04.1-01"], "P/04-01")
        self.assertTrue(any("malformed or foreign checklist item" in e for e in result.errors), result.errors)
