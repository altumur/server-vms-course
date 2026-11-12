"""The nine checks of the reading form of M (m_form.py), its stage A and the lesson without a list on the accepted form
of P/01 and on spoiled copies of it; the paragraph layout of the rollback (ADR-0133 addenda (93), (94)) on the copy
with a synthetic paragraph and a merged id, so that the cases do not depend on the text the rollback rewrites."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import m_form
from check_spec import Check

ROOT = Path(__file__).resolve().parents[3]
HOME = "Platform/01-store"
JOURNAL = "decisions/journal/platform/01-store"
COMMON_FILES = ("Platform/common/export-model-filter.json", "Platform/common/acceptance/judge-input-filter.json")

# Defects of the form on main 2026-11-11 (P01.203 report) mended in the copy, so that the copy is the accepted form
# by the rules of the skill. A replacement that is no longer needed (main mended it) is skipped.
MAIN_MENDS = [
    ("lifecycle.md", "in the acceptances moved from M10/4–11 —", "in the acceptances of the other lessons —"),
    ("ru/lifecycle.md", "в приёмках, перенесённых из M10/4–11, —", "в приёмках других уроков —"),
    ("README.md", "`Platform/module-design.md` (for people, not in the export)",
     "`Platform/module-design.md` (judge-only: for people)"),
    ("ru/README.md", "`Platform/module-design.md` (для человека, в выгрузку не входит)",
     "`Platform/module-design.md` (только для судьи: для человека)"),
    ("spec/01.3-store.norms.md", "[judge-only N5 coverage](01.3-store.n5.cases.md).",
     "[judge-only N5 coverage](01.3-store.n5.cases.md) (judge-only: the N5 cases of the chapter)."),
    ("ru/spec/01.3-store.norms.md", "[покрытии N5 только для судьи](01.3-store.n5.cases.md).",
     "[покрытии N5 только для судьи](01.3-store.n5.cases.md) (только для судьи: случаи N5 главы)."),
    ("vectors/rights-evaluator/README.md", "with `rights.json` as `{rights}`",
     "with `rights.json` (judge-only: the file itself) as `{rights}`"),
    ("ru/vectors/rights-evaluator/README.md", "с `rights.json` как `{rights}`",
     "с `rights.json` (только для судьи: сам файл) как `{rights}`"),
    # the families block of 01.3 built before OBSH.42 (rebuilt after P01.233: python -m v7.sections …01.3-store.norms.md)
    ("spec/01.3-store.norms.md", "JSON Schema 2020-12 of the family (ADR-0092). An instance",
     "JSON Schema 2020-12 of the family. An instance"),
    ("ru/spec/01.3-store.norms.md", "JSON Schema 2020-12 семьи (ADR-0092). Экземпляр", "JSON Schema 2020-12 семьи. Экземпляр"),
]


def mend(home):
    for rel, before, after in MAIN_MENDS:
        path = home / rel
        text = path.read_text(encoding="utf-8")
        if before in text:
            path.write_text(text.replace(before, after), encoding="utf-8")
    for rel in ("spec/01.2-store.norms.md", "ru/spec/01.2-store.norms.md"):   # the index ascending (§2.1 of templates)
        path = home / rel
        path.write_text(re.sub(r"^(\|[^|]*\| )((?:P/[0-9.]+-R[0-9]{3}(?:, )?)+)( \|)", lambda m: m[1] + ", ".join(
            sorted(re.findall(m_form.REQ, m[2]), key=m_form.req_key)) + m[3], path.read_text(encoding="utf-8"),
            flags=re.M), encoding="utf-8")
    ru = home / "ru/spec/01.3-store.norms.md"                 # the translation keeps the fence the source dropped
    lines = ru.read_text(encoding="utf-8").split("\n")
    at = next((i for i, line in enumerate(lines) if line.startswith("### восстановить хранилище")), None)
    if at is not None and lines[at + 2] == "```":
        end = next(i for i in range(at + 3, len(lines)) if lines[i] == "```")
        del lines[end], lines[at + 2]
        ru.write_text("\n".join(lines), encoding="utf-8")


class AcceptedForm(unittest.TestCase):
    """A copy of P/01 (lesson, history journal, the files its indexes name) with the main defects mended."""

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix="m-form-")
        root = Path(cls.base.name).resolve()
        shutil.copytree(ROOT / HOME, root / HOME)
        (root / JOURNAL).mkdir(parents=True)
        for path in (ROOT / JOURNAL).glob("*.tsv"):     # history files and the id map req-id-map.tsv (P01.283)
            shutil.copy(path, root / JOURNAL / path.name)
        names = list(COMMON_FILES) + ["Platform/lessons.tsv", "Platform/module-design.md"]
        check = Check(ROOT, scope="platform")
        lesson = m_form.Lesson(check, "P/01", ROOT / HOME)
        for norms in lesson.chapters:
            for _, _, _, addresses in m_form.index_rows(norms, "en"):
                for address in addresses:
                    target = m_form.resolve_address(check, lesson, address)
                    if target and target.is_file() and HOME not in target.as_posix():
                        names.append(target.relative_to(ROOT).as_posix())
        for name in names:
            if (ROOT / name).is_file():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / name, root / name)
        mend(root / HOME)
        cls.pristine = root

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m-form-case-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "course"
        shutil.copytree(self.pristine, self.root)
        self.home = self.root / HOME

    def run_checks(self):
        check = Check(self.root, scope="platform")
        m_form.run(check, {"01"})
        return check

    def replace(self, rel, before, after, count=1, root=None):
        path = (root or self.home) / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text, rel)
        path.write_text(text.replace(before, after, count), encoding="utf-8")

    def line_of(self, rel, needle, root=None):
        text = ((root or self.home) / rel).read_text(encoding="utf-8")
        return text[:text.index(needle)].count("\n") + 1

    def assert_error(self, check, rel, line, words):
        wanted = f"{rel}: line {line}: "
        hits = [e for e in check.errors if e.startswith(wanted) and words in e]
        self.assertTrue(hits, f"no error {wanted}…{words} in {check.errors}")

    def edit_index_row(self, rel, language, change):
        """Rewrites by change(ids) the requirements cell of the first index row of `rel` naming two or more
        requirements (the row is taken from the copy, not written here, so a new text of the index needs no edit of
        the test); returns its line."""
        path = self.home / rel
        n, _, cell, _ = next(row for row in m_form.index_rows(path, language) if len(row[2].split(",")) > 1)
        lines = path.read_text(encoding="utf-8").split("\n")
        self.assertIn(cell, lines[n - 1])
        lines[n - 1] = lines[n - 1].replace(cell, change([x.strip() for x in cell.split(",")]), 1)
        path.write_text("\n".join(lines), encoding="utf-8")
        return n

    def add_sentence(self, rel, sentence):
        """Puts the sentence before the first prose paragraph after the first section heading of `rel` (taken from the
        copy); returns its line."""
        lines = (self.home / rel).read_text(encoding="utf-8").split("\n")
        start = next(i for i, line in enumerate(lines) if line.startswith("## "))
        anchor = next(line for i, line in enumerate(lines) if i > start and line[:1].isupper() and not lines[i - 1])
        self.replace(rel, anchor, sentence + " " + anchor)
        return self.line_of(rel, sentence)


class AcceptedFormPasses(AcceptedForm):
    def test_accepted_form_passes_every_check_with_counts(self):
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        for name in ("history_phrases", "index_refs", "judge_only_refs", "production_scoped",
                     "history_rows", "checklist_marks", "req_refs"):
            self.assertGreater(check.stats[name], 0, name)

    def test_run_through_check_spec_method_only_for_checked_lessons(self):
        check = Check(self.root, scope="platform")
        with patch.object(m_form, "M_FORM_COMMON", ()):
            check.m_form()                               # no lesson checked in this run, no common input — nothing to judge
        self.assertEqual(check.stats["history_phrases"], 0)
        check.lessons_seen.add("01")
        check.m_form()
        self.assertEqual(check.errors, [])
        self.assertGreater(check.stats["history_rows"], 0)

    def test_main_defects_are_found_on_the_unmended_lesson(self):
        shutil.rmtree(self.home)
        shutil.copytree(ROOT / HOME, self.home)
        errors = "\n".join(self.run_checks().errors)
        for rel, before, _ in MAIN_MENDS:
            if before in (ROOT / HOME / rel).read_text(encoding="utf-8"):
                self.assertIn(f"{HOME}/{rel}: line ", errors)


class HistoryPhrases(AcceptedForm):
    def test_history_only_in_the_source(self):
        self.replace("spec/01.1-store.norms.md", "Normative keywords follow RFC 2119",
                     "Normative keywords (the Architect's decision of 2026-10-18) follow RFC 2119")
        check = self.run_checks()
        self.assert_error(check, f"{HOME}/spec/01.1-store.norms.md",
                          self.line_of("spec/01.1-store.norms.md", "the Architect's decision"), "history in M")
        self.assertFalse([e for e in check.errors if "/ru/" in e], check.errors)

    def test_history_only_in_the_translation(self):
        rel = "ru/spec/01.2-store.norms.md"
        text = (self.home / rel).read_text(encoding="utf-8")
        line = text.split("\n").index("## Указатель")
        self.replace(rel, "## Указатель\n", "## Указатель\n\nПравило перенесено из M10/6 (сверка python и go).\n")
        check = self.run_checks()
        self.assert_error(check, f"{HOME}/{rel}", line + 3, "перенесено из")
        self.assert_error(check, f"{HOME}/{rel}", line + 3, "сверка python и go")

    def test_history_in_json_and_tsv_files_of_m(self):
        self.replace("forms/runtime-constants.tsv", "\n", "\n# reconciliation of python and go M10/6–11\n")
        self.assert_error(self.run_checks(), f"{HOME}/forms/runtime-constants.tsv", 2, "reconciliation of python and go")

    def test_history_in_the_common_acceptance_when_it_is_included(self):
        common = self.root / "Platform/common/acceptance/README.md"
        common.write_text("# Common acceptance\n\nA stand (analysis of the review of stage B 3–5, № 33).\n",
                          encoding="utf-8")
        with patch.object(m_form, "M_FORM_COMMON", ()):
            check = self.run_checks()
        self.assertFalse([e for e in check.errors if "common/acceptance" in e], "not included")
        with patch.object(m_form, "M_FORM_COMMON", ("Platform/common/acceptance/",)):
            check = self.run_checks()
        self.assert_error(check, "Platform/common/acceptance/README.md", 3, "analysis of the review")

    def test_adr_number_outside_tombstones(self):
        rel = "spec/01.1-store.norms.md"
        self.replace(rel, "Normative keywords follow RFC 2119", "Normative keywords follow RFC 2119 (ADR-0080)")
        check = self.run_checks()
        self.assert_error(check, f"{HOME}/{rel}", self.line_of(rel, "(ADR-0080)"), "an ADR number in M")

    def test_tombstone_withdrawn_item_and_row_owner_are_not_history(self):
        rel = "spec/01.1-store.norms.md"
        self.replace(rel, "<!-- req: P/01.1-R002 -->", "<!-- removed: P/01.1-R999 by ADR-0133 -->\n\n<!-- req: P/01.1-R002 -->")
        self.replace(rel, "- [ ] **P/01.1-31**", "- [ ] **P/01.1-99** снята: `ADR-0133`\n- [ ] **P/01.1-31**")
        self.replace(rel, "A closed list. The text", "A closed list (the row `door` — P/03). The text")
        self.assertEqual(self.run_checks().errors, [])

    def test_removed_from_is_not_moved_from(self):
        self.replace("spec/01.1-store.norms.md", "Normative keywords follow", "A row removed from the store; keywords follow")
        self.assertEqual(self.run_checks().errors, [])

    def test_adr_later_judges_forms_outcomes_and_a_new_file(self):
        # P01.176 removed the numbers from forms/*.tsv, OBSH.42 from the headers of data/*.outcomes.tsv: both are judged.
        self.assertFalse([g for g in m_form.ADR_LATER["P/01"] if g.startswith(("forms/", "data/"))])
        self.replace("data/epoch_floor.outcomes.tsv", "\n", "\n# the outcomes of ADR-0129\n")
        self.assert_error(self.run_checks(), f"{HOME}/data/epoch_floor.outcomes.tsv", 2, "an ADR number in M")
        self.replace("data/epoch_floor.outcomes.tsv", "\n# the outcomes of ADR-0129\n", "\n")
        self.replace("forms/runtime-constants.tsv", "\n", "\n# the constants of ADR-0129\n")
        self.assert_error(self.run_checks(), f"{HOME}/forms/runtime-constants.tsv", 2, "an ADR number in M")
        self.replace("probes/README.md", "\n", "\nThe probes of ADR-0133.\n")
        self.assert_error(self.run_checks(), f"{HOME}/probes/README.md", 2, "an ADR number in M")

    def test_stale_adr_later_entry(self):
        for rel in ("vectors/rights-evaluator/README.md", "ru/vectors/rights-evaluator/README.md"):
            path = self.home / rel
            path.write_text(re.sub(r" ?\(ADR-0[0-9]{3}[^)]*\)|ADR-0[0-9]{3}", "", path.read_text(encoding="utf-8")),
                            encoding="utf-8")
        errors = self.run_checks().errors
        self.assertTrue(any("vectors/rights-evaluator/README.md: stale ADR_LATER" in e for e in errors), errors)

    def test_built_block_is_text_of_m(self):
        # OBSH.42: the block between its markers is read as any text of M, in the source and in the translation.
        for rel in ("spec/01.3-store.norms.md", "ru/spec/01.3-store.norms.md"):
            self.replace(rel, "<!-- families:end -->", "the Architect's decision of 2026-10-27\n<!-- families:end -->")
        check = self.run_checks()
        for rel in ("spec/01.3-store.norms.md", "ru/spec/01.3-store.norms.md"):
            self.assert_error(check, f"{HOME}/{rel}", self.line_of(rel, "the Architect's decision of 2026-10-27"),
                              "in the built block «families»")

    def test_built_schema_is_not_read(self):
        self.replace("data/epoch_floor.schema.json", '"description": "', '"description": "the Architect\'s decision; ')
        self.assertFalse([e for e in self.run_checks().errors if "epoch_floor.schema.json" in e])

    def test_builders_write_no_origin(self):
        # The words of the builders of the blocks (v7/section.py, v7/view.py): the rule in words, no ADR, no history.
        import v7.sections
        out = []
        for rel in ("Platform/02-installer/spec/02.1-installer.norms.md", "Platform/02-installer/spec/02.2-installer.norms.md"):
            for at in (ROOT / rel, ROOT / rel.replace("/spec/", "/ru/spec/")):
                kinds = ("form",) if "02.1" in rel else ("canonical",)
                out += [v7.sections.built(kind, ROOT / rel, ROOT, at=at) for kind in kinds]
        for text in out:
            self.assertFalse(m_form.ADR_NUMBER.search(text), text[:200])
            self.assertFalse(m_form.HISTORY_PHRASES.search(text), text[:200])


class IndexRefs(AcceptedForm):
    REL = "spec/01.1-store.norms.md"

    def test_unknown_removed_and_malformed_requirement(self):
        for bad, words in (("P/01.1-R999", "not a requirement of P/01"), ("P/01.1-R0x7", "not a requirement id"),
                           ("P/02.1-R001", "not a requirement of P/01")):
            with self.subTest(bad=bad):
                self.setUp()
                line = self.edit_index_row(self.REL, "en", lambda ids: ", ".join(ids + [bad]))
                self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, words)

    def test_order_and_repeat(self):
        line = self.edit_index_row(self.REL, "en", lambda ids: ", ".join([ids[1], ids[0]] + ids[2:]))
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, "ascending")

    def test_file_addresses_two_roots_no_fallback(self):
        # Both roots of the accepted index pass (the base test); a wrong prefix fails: no search over a second root.
        # after P01.229 the group stand lives in the lesson; the course-root address left in the index is the seam protocol
        self.replace(self.REL, "`Platform/common/acceptance/seams.md` «Seam adapter protocol»",
                     "`common/acceptance/seams.md` «Seam adapter protocol»")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "`seam_bridge`"),
                          "no file `common/acceptance/seams.md`")

    def test_lesson_root_address_is_not_resolved_from_the_course_root(self):
        self.replace(self.REL, "`forms/daemon-flags.tsv` (`-max-value`)", "`forms/nothing.tsv` (`-max-value`)")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "`row_ceiling`"),
                          "no file `forms/nothing.tsv`")

    def test_names_in_parentheses_and_quotes_are_not_addresses(self):
        self.replace(self.REL, "(`SEAM_BRIDGE.json`)", "(`NO_SUCH_FILE.json`)")
        self.replace(self.REL, "«`seams.tsv` — scenarios", "«`no-such.tsv` — scenarios", count=-1)
        self.assertEqual(self.run_checks().errors, [])

    def test_translation_row_differs(self):
        rel = "ru/" + self.REL
        self.edit_index_row(rel, "ru", lambda ids: ", ".join(ids[:1] + ids[2:]))
        check = self.run_checks()
        self.assertTrue(any(e.startswith(f"{HOME}/{rel}: line ") and "index row differs" in e for e in check.errors),
                        check.errors)


class SeeAlsoRefs(AcceptedForm):
    """Form M navigates by the index alone: a «See also» line is an error (the Architect 2026-11-12, by P08.25)."""
    REL = "spec/01.1-store.norms.md"

    def test_no_see_also_lines_pass(self):
        self.assertEqual([e for e in self.run_checks().errors if "See also" in e or "См. также" in e], [])

    def test_a_see_also_line_is_an_error_in_source_and_translation(self):
        self.replace(self.REL, "<!-- req: P/01.1-R149 -->", "See also: P/01.1-R150.\n\n<!-- req: P/01.1-R149 -->")
        self.replace("ru/" + self.REL, "**Охват: боевой.** Сохранение", "См. также: P/01.1-R150.\n\n**Охват: боевой.** Сохранение")
        errors = self.run_checks().errors
        self.assertTrue(any(f"{HOME}/{self.REL}: line " in e and "navigates by the index alone" in e for e in errors), errors)
        self.assertTrue(any(f"{HOME}/ru/{self.REL}: line " in e and "navigates by the index alone" in e for e in errors), errors)


class JudgeOnlyRefs(AcceptedForm):
    REL = "acceptance/1/README.md"

    def add(self, sentence):
        return self.add_sentence(self.REL, sentence)

    def test_path_in_backquotes_without_marker(self):
        line = self.add("The steps are in `scenarios.tsv` of this chapter.")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, "judge-only file")

    def test_link_without_marker_and_marker_in_another_sentence(self):
        line = self.add("See the [seams](seams.tsv) of the chapter. They are judge-only (judge-only: seams).")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, "acceptance/1/seams.tsv")

    def test_marker_in_the_same_sentence_heading_and_quoted_name_pass(self):
        self.add("The steps are in `scenarios.tsv` (judge-only: the scenario table) of this chapter. "
                 "The section «`seams.tsv` — scenarios over the seams of the process» explains them.")
        self.replace(self.REL, "\n## ", "\n## `seams.tsv` again\n\n## ")
        self.assertEqual(self.run_checks().errors, [])

    def test_bare_name_of_a_platform_file_is_not_the_judge_only_file(self):
        # OBSH.42 (P08.26): `ca.pem` of the norms is the platform file /etc/w2c/tls/ca.pem, not an input of acceptance.
        line = self.add("The group of the socket is in `group.json` of the daemon.")   # acceptance/3/inputs/group.json
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, "judge-only file")
        catalog = self.root / m_form.CATALOG
        catalog.parent.mkdir(parents=True, exist_ok=True)
        rows = catalog.read_text(encoding="utf-8") if catalog.is_file() else "key\tkind\towner\n"
        catalog.write_text(rows + "/etc/w2c/group.json\tfile\tP/01\n<events root>/<sub>.tsv\tfile\tP/01\n",
                           encoding="utf-8")
        self.assertEqual(m_form.platform_files(Check(self.root, scope="platform")) & {"<sub>.tsv"}, set())
        self.assertFalse([e for e in self.run_checks().errors if "judge-only file" in e])

    def test_translation_reference_is_judged_by_its_source(self):
        rel = "ru/" + self.REL
        text = (self.home / rel).read_text(encoding="utf-8")
        at = text.index("\n\n") + 2
        (self.home / rel).write_text(text[:at] + "Шаги — в `scenarios.tsv` главы.\n\n" + text[at:], encoding="utf-8")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", text[:at].count("\n") + 1, "judge-only file")


class ProductionScoped(AcceptedForm):
    REL = "spec/01.1-store.norms.md"

    def test_definition_in_n0_and_acting_labels_pass(self):
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        # every acting label opens a paragraph or follows the id of a checklist item, in the source and in the
        # translation; the definitions of N0 quote the label in «…» and are not counted
        opening = r"^(?:- \[[ x]\] \*\*P/[0-9.]+-[0-9]+\*\* )?"
        counts = []
        for label, files in ((m_form.LABELS[0], [p for p in self.home.rglob("*.md") if "ru" not in p.relative_to(
                self.home).parts]), (m_form.LABELS[1], list((self.home / "ru").rglob("*.md")))):
            counts.append(sum(len(re.findall(opening + re.escape(label), p.read_text(encoding="utf-8"), flags=re.M))
                              for p in files))
        self.assertGreater(counts[0], 0)
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(check.stats["production_scoped"], sum(counts))

    def test_acting_label_inside_a_paragraph(self):
        self.replace(self.REL, "Persistence of an ordinary fixed-size write MUST be incremental:",
                     "Persistence of an ordinary fixed-size write **Scope: production.** MUST be incremental:")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}",
                          self.line_of(self.REL, "fixed-size write **Scope"), "inside a paragraph")

    def test_label_opening_a_second_paragraph_of_a_requirement(self):
        self.replace(self.REL, "<!-- req: P/01.1-R149 -->",
                     "**Scope: production.** A second paragraph.\n\n<!-- req: P/01.1-R149 -->")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "A second paragraph"),
                          "not the first after a req anchor")

    def test_label_in_the_translation_inside_a_paragraph(self):
        rel = "ru/" + self.REL
        self.replace(rel, "**Охват: боевой.** Сохранение", "Сохранение **Охват: боевой.**")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", self.line_of(rel, "Сохранение **Охват"),
                          "inside a paragraph")


class ChecklistMarks(AcceptedForm):
    REL = "spec/01.1-store.norms.md"

    def test_accepted_marks_pass_with_count(self):
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        items = sum(len(m_form.checklist_items((self.home / rel).read_text(encoding="utf-8")))
                    for rel in ("spec/01.1-store.norms.md", "spec/01.2-store.norms.md", "spec/01.3-store.norms.md"))
        self.assertEqual(check.stats["checklist_marks"], 2 * items)       # the source and the translation
        self.assertGreater(items, 50)

    def test_grammar_of_the_mark_fails(self):
        item = "- [ ] **P/01.1-15** [reading] a read"
        cases = [
            ("- [ ] **P/01.1-15** a read", "no mark"),
            ("- [ ] **P/01.1-15** [read] a read", "a closed list"),
            ("- [ ] **P/01.1-15** [test,reading] a read", "a closed list"),
            ("- [ ] **P/01.1-15** [reading, reading] a read", "repeats a word"),
            ("- [ ] **P/01.1-15** [test] [reading] a read", "a second mark"),
            ("- [ ] **P/01.1-15** [reading]a read", "not followed by a space"),
            ("- [ ] **P/01.1-15**  [reading] a read", "no mark"),
            ("- [ ] **P/01.1-15** a read [reading]", "no mark"),
        ]
        for bad, words in cases:
            with self.subTest(bad=bad):
                self.setUp()
                self.replace(self.REL, item, bad)
                self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, bad), words)

    def add_withdrawn(self):
        """A withdrawn checklist item in source and translation, before item 32 (P/01 has none since P01.176)."""
        self.replace(self.REL, "- [ ] **P/01.1-32** ", "- [ ] **P/01.1-90** removed: `ADR-0133`\n- [ ] **P/01.1-32** ")
        self.replace("ru/" + self.REL, "- [ ] **P/01.1-32** ", "- [ ] **P/01.1-90** снята: `ADR-0133`\n- [ ] **P/01.1-32** ")

    def test_production_label_before_the_mark_and_withdrawn_item(self):
        self.assertIn("- [ ] **P/01.1-32** **Scope: production.** [stand]",
                      (self.home / self.REL).read_text(encoding="utf-8"))
        rel = self.REL
        self.replace(rel, "**P/01.1-32** **Scope: production.** [stand]", "**P/01.1-32** [stand] **Scope: production.**")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", self.line_of(rel, "**P/01.1-32** [stand]"),
                          "goes between the id and the mark")
        self.setUp()
        self.add_withdrawn()
        self.replace(rel, "- [ ] **P/01.1-90** removed:", "- [ ] **P/01.1-90** [reading] removed:")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", self.line_of(rel, "**P/01.1-90** [reading]"),
                          "a withdrawn item has no mark")
        self.setUp()
        self.add_withdrawn()
        self.replace(rel, "- [ ] **P/01.1-90** removed: `ADR-0133`", "- [ ] **P/01.1-90** removed: `ADR-0133` [reading]")
        self.assertEqual(self.run_checks().errors, [])     # the words after a withdrawal are no mark

    def test_translation_has_the_same_english_words(self):
        rel = "ru/" + self.REL
        for before, after, words in (
                ("- [ ] **P/01.1-15** [reading]", "- [ ] **P/01.1-15** [test]", "differs from the source [reading]"),
                ("- [ ] **P/01.1-15** [reading]", "- [ ] **P/01.1-15** [чтение]", "a closed list"),
                ("- [ ] **P/01.1-03** [test, reading]", "- [ ] **P/01.1-03** [reading, test]", "differs from the source"),
                ("**P/01.1-32** **Охват: боевой.** [stand]", "**P/01.1-32** **Охват: боевой.** [test]", "differs"),
                ("- [ ] **P/01.1-90** снята:", "- [ ] **P/01.1-90** [test] снята:", "a withdrawn item has no mark")):
            with self.subTest(after=after):
                self.setUp()
                self.add_withdrawn()
                self.replace(rel, before, after)
                self.assert_error(self.run_checks(), f"{HOME}/{rel}", self.line_of(rel, after), words)

    def test_items_in_code_are_not_judged(self):
        self.replace(self.REL, "## Readiness checklist\n", "## Readiness checklist\n\n```\n- [ ] **P/01.1-99** an example\n```\n")
        self.assertEqual(self.run_checks().errors, [])


class StageA(AcceptedForm):
    """A lesson of M_FORM_STAGE_A: only history_phrases (without forms/*.tsv and data/*.tsv), judge_only_refs and
    history_rows (P01.228)."""

    def run_stage_a(self):
        with patch.object(m_form, "M_FORM_LESSONS", set()), patch.object(m_form, "M_FORM_STAGE_A", {"P/01"}):
            return self.run_checks()

    def test_stage_a_judges_only_its_three_checks(self):
        self.replace("spec/01.1-store.norms.md", "- [ ] **P/01.1-15** [reading]", "- [ ] **P/01.1-15**")
        self.edit_index_row("spec/01.1-store.norms.md", "en", lambda ids: ", ".join([ids[1], ids[0]] + ids[2:]))
        self.replace("forms/runtime-constants.tsv", "\n", "\n# the constants of ADR-0129\n")
        self.replace("data/epoch_floor.outcomes.tsv", "\n", "\n# reconciliation of python and go\n")
        check = self.run_stage_a()
        self.assertEqual(check.errors, [])
        for name in ("history_phrases", "judge_only_refs", "history_rows"):
            self.assertGreater(check.stats[name], 0, name)
        for name in ("index_refs", "see_also_refs", "production_scoped", "checklist_marks"):
            self.assertEqual(check.stats[name], 0, name)

    def test_stage_a_finds_history_judge_only_and_rows(self):
        self.replace("README.md", "\n", "\nThe store (the Architect's decision of 2026-10-18).\n")
        self.add_sentence("acceptance/1/README.md", "The steps are in `seams.tsv` here.")
        path = self.root / JOURNAL / "history.tsv"
        path.write_text(path.read_text(encoding="utf-8") + "-\tforms/write-checks.tsv#row:999\tx\t2026-11-11\ty\n",
                        encoding="utf-8")
        errors = "\n".join(self.run_stage_a().errors)
        self.assertIn(f"{HOME}/README.md: line 2: history in M", errors)
        self.assertIn("judge-only file", errors)
        self.assertIn("#row:999: no row", errors)

    def test_stage_a_block_finding_carried_by_a_data_file_is_that_file(self):
        # OBSH.42: at stage A the text a data file carries into the block is judged with the file at stage B; the words
        # of the builder are judged now.
        rel, outcomes = "spec/01.3-store.norms.md", "data/epoch_floor.outcomes.tsv"
        said = "the whole row is unreadable: epoch issue — the issue is refused"
        carried = "the whole row is unreadable (the Architect's decision of 2026-10-27): epoch issue — the issue is refused"
        self.replace(outcomes, said, carried)
        for norms in (rel, "ru/" + rel):
            self.replace(norms, said, carried)
        self.replace(rel, "JSON Schema 2020-12 of the family. An instance", "JSON Schema 2020-12 of the family "
                                                                          "(ADR-0092). An instance")
        check = self.run_stage_a()
        self.assertEqual([e for e in check.errors if "built block" not in e], [])
        self.assert_error(check, f"{HOME}/{rel}", self.line_of(rel, "(ADR-0092)"), "in the built block «families»")
        self.assertEqual(len(check.errors), 1, check.errors)
        self.assertEqual(check.stats["history_block_carried"], 2)
        with patch.object(m_form, "M_FORM_LESSONS", {"P/01"}):
            errors = self.run_checks().errors              # stage B: the carried text is an error too
        self.assert_error_in(errors, f"{HOME}/{rel}", self.line_of(rel, "the Architect's decision of 2026-10-27"))

    def assert_error_in(self, errors, rel, line):
        self.assertTrue([e for e in errors if e.startswith(f"{rel}: line {line}: history in M")], errors)

    def test_a_lesson_in_both_sets_is_an_error(self):
        with patch.object(m_form, "M_FORM_STAGE_A", {"P/01"}):
            errors = self.run_checks().errors
        self.assertTrue(any("in M_FORM_LESSONS and in M_FORM_STAGE_A" in e for e in errors), errors)

    def test_stage_a_set_names_lessons_outside_the_full_form(self):
        self.assertFalse(m_form.M_FORM_STAGE_A & m_form.M_FORM_LESSONS)
        self.assertTrue(all(re.fullmatch(r"P/(0[2-9]|10)", x) for x in m_form.M_FORM_STAGE_A), m_form.M_FORM_STAGE_A)


class LessonWithoutList(AcceptedForm):
    """A lesson without forms/export.json takes its files of M from the common filter M (export_lists)."""

    def move_list_to_common(self):
        listed = self.home / "forms/export.json"
        data = json.loads(listed.read_text(encoding="utf-8"))
        listed.unlink()
        for side, rel in (("model", COMMON_FILES[0]), ("judge", COMMON_FILES[1])):
            path = self.root / rel
            common = json.loads(path.read_text(encoding="utf-8"))
            common["files"] = sorted(common["files"] + [r for r in data[side] if r["path"] != f"{HOME}/forms/export.json"],
                                     key=lambda r: r["path"].encode("utf-8"))
            path.write_text(json.dumps(common, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # A lesson without its own list has no history of that list: the rows addressing forms/export.json
        # (cece6f6ea P01.257, 4ae6c4271 P01.259) go with the file, every other row of the journal stays.
        for path in (self.root / JOURNAL).glob("history*.tsv"):
            lines = path.read_text(encoding="utf-8").split("\n")
            kept = [line for line in lines if not line.split("\t")[1:2] or
                    not line.split("\t")[1].startswith("forms/export.json")]
            if kept != lines:
                path.write_text("\n".join(kept), encoding="utf-8")

    def test_judged_by_the_common_filter(self):
        self.move_list_to_common()
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        self.assertGreater(check.stats["history_phrases"], 0)
        self.replace("README.md", "\n", "\nThe store (the Architect's decision of 2026-10-18).\n")
        self.assert_error(self.run_checks(), f"{HOME}/README.md", 2, "history in M")

    def test_no_file_of_m_is_an_error(self):
        (self.home / "forms/export.json").unlink()
        errors = self.run_checks().errors
        self.assertTrue(any(e.startswith(f"{HOME}: ") and "names no file model_and_judge" in e for e in errors), errors)


class HistoryRows(AcceptedForm):
    def journal(self, name):
        return self.root / JOURNAL / name

    def add_row(self, name, row):
        path = self.journal(name)
        lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
        path.write_text("\n".join(lines + [row]) + "\n", encoding="utf-8")
        return len(lines) + 1

    def test_accepted_addresses_of_every_kind_pass(self):
        rows = "".join(self.journal(n).read_text(encoding="utf-8") for n in ("history.tsv", "history-1.tsv", "history-3.tsv"))
        for kind in ("#intro\t", "#N0\t", "#N1.3\t", "#/components/schemas/Cmd\t", "#readiness-checklist\t"):
            self.assertIn(kind, rows)
        self.assertEqual(self.run_checks().errors, [])

    def test_neighbouring_addresses_fail(self):
        cases = [
            ("spec/01.1-store.norms.md#N9", "no section N9"),
            ("spec/01.3-store.norms.md#N1.9", "no section N1.9"),
            ("spec/01-store.api.openapi.yaml#/components/schemas/Nope", "no JSON Pointer"),
            ("spec/01-store.api.openapi.yaml#intro", "Markdown"),
            ("spec/01.1-store.norms.md#n0-vocabulary-x", "no heading anchor"),
            ("spec/01.1-store.norms.md#/components", "YAML or JSON"),
            ("spec/no-such.norms.md#N0", "no file"),
            ("ru/spec/01.1-store.norms.md#N0", "not ru/"),
            ("spec/01.1-store.norms.md", "expected <path"),
        ]
        for address, words in cases:
            with self.subTest(address=address):
                self.setUp()
                line = self.add_row("history-1.tsv", f"-\t{address}\tx\t2026-10-18\ty")
                self.assert_error(self.run_checks(), f"{JOURNAL}/history-1.tsv", line, words)

    def test_header_fields_id_date_and_texts(self):
        cases = [
            ("P/01.1-R999\tspec/01.1-store.norms.md#N0\tx\t2026-10-18\ty", "not a requirement of P/01"),
            ("R002\tspec/01.1-store.norms.md#N0\tx\t2026-10-18\ty", "neither - nor"),
            ("-\tspec/01.1-store.norms.md#N0\tx\t2026-13-01\ty", "not an ISO date"),
            ("-\tspec/01.1-store.norms.md#N0\tx\t18.10.2026\ty", "not an ISO date"),
            ("-\tspec/01.1-store.norms.md#N0\t\t2026-10-18\ty", "empty source"),
            ("-\tspec/01.1-store.norms.md#N0\tx\t2026-10-18\t", "empty removed"),
            ("-\tspec/01.1-store.norms.md#N0\tx\t2026-10-18", "4 fields"),
        ]
        for row, words in cases:
            with self.subTest(row=row):
                self.setUp()
                line = self.add_row("history-1.tsv", row)
                self.assert_error(self.run_checks(), f"{JOURNAL}/history-1.tsv", line, words)
        self.setUp()
        path = self.journal("history.tsv")
        path.write_text(path.read_text(encoding="utf-8").replace("req_id\tfile", "req\tfile", 1), encoding="utf-8")
        self.assert_error(self.run_checks(), f"{JOURNAL}/history.tsv", 1, "the header")

    def test_tsv_addresses_header_and_row_by_key(self):
        # A row of a form by the value of its first column, the comment of its header — not by a line number.
        for address in ("forms/write-checks.tsv#header", "forms/write-checks.tsv#row:3",
                        "forms/runtime-constants.tsv#row:JSON_DEPTH", "forms/group.tsv#row:stand_size",
                        "forms/write-checks.tsv.schema.json#/description"):
            with self.subTest(address=address):
                self.setUp()
                self.add_row("history.tsv", f"-\t{address}\tx\t2026-11-11\ty")
                self.assertEqual(self.run_checks().errors, [])

    def test_tsv_addresses_fail(self):
        cases = [
            ("forms/write-checks.tsv#row:999", "no row with the first column «999»"),
            ("forms/write-checks.tsv#row:", "#header or #row:"),
            ("forms/write-checks.tsv#L20", "#header or #row:"),
            ("forms/write-checks.tsv#/fields/1", "#header or #row:"),
            ("forms/write-checks.probes.tsv#row:0", "repeats at lines"),
            ("forms/targets.tsv#header", "no comment lines"),
            ("spec/01.1-store.norms.md#row:1", "addresses a TSV form"),
            ("spec/01-store.api.openapi.yaml#header", "addresses a TSV form"),
        ]
        for address, words in cases:
            with self.subTest(address=address):
                self.setUp()
                if address.startswith("forms/targets.tsv"):
                    path = self.home / "forms/targets.tsv"
                    path.write_text("".join(line for line in path.read_text(encoding="utf-8").splitlines(True)
                                            if not line.startswith("#")), encoding="utf-8")
                line = self.add_row("history.tsv", f"-\t{address}\tx\t2026-11-11\ty")
                self.assert_error(self.run_checks(), f"{JOURNAL}/history.tsv", line, words)

    def test_history_of_a_chapter_the_lesson_has_not(self):
        shutil.copy(self.journal("history-1.tsv"), self.journal("history-9.tsv"))
        errors = self.run_checks().errors
        self.assertTrue(any("history-9.tsv: a history file of chapter 9" in e for e in errors), errors)


class ParagraphLayout(AcceptedForm):
    """ADR-0133 addendum (93): a paragraph of several rules keeps one R-id; a merged id leaves M for the id map of the
    journal (req-id-map.tsv) and its history row, stays reserved, and a reference to it is an error (req_map, req_refs,
    index_refs, history_rows; check_forms.check_req_anchors for the reuse)."""
    NORMS = "spec/01.3-store.norms.md"
    MAP = f"{JOURNAL}/{m_form.REQ_MAP}"

    def lesson(self):
        return m_form.Lesson(Check(self.root, scope="platform"), "P/01", self.home)

    def free(self, chapter, count):
        lesson = self.lesson()
        live, removed = lesson.requirements()
        taken = set(live) | removed | set(lesson.merged()) | m_form.history_ids(lesson)
        out = [f"P/01.{chapter}-R{n:03d}" for n in range(999, 0, -1) if f"P/01.{chapter}-R{n:03d}" not in taken]
        return out[:count]

    def merge(self):
        """A paragraph of several rules under a new live id at the first anchor of 01.3, an id merged into it: the row of
        the map and the row of the history."""
        self.new, self.old, self.spare = self.free(3, 3)
        path = self.home / self.NORMS
        text = path.read_text(encoding="utf-8")
        at = text.index("<!-- req: P/01.3-")
        self.section = re.findall(r"^#{2,6} (N[0-9](?:\.[0-9]+[a-z]?)*)\s", text[:at], flags=re.M)[-1]
        block = (f"<!-- req: {self.new} -->\n- `paragraph` — The daemon MUST keep the row A. It MUST NOT drop the row B; "
                 "if the row C is absent, then the request MUST get 400 `bad_request`. The limit of the rows is 3.\n\n")
        path.write_text(text[:at] + block + text[at:], encoding="utf-8")
        self.address = f"{self.NORMS}#{self.section}"
        self.map_rows(f"{self.old}\t{self.new}\t{self.address}\tP01.283: one paragraph")   # after the rows of the journal
        self.history(self.old)

    def history(self, value):
        path = self.root / JOURNAL / "history-3.tsv"
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") +
                        f"\n{value}\t{self.address}\tP01.283\t2026-11-12\tThe daemon MUST NOT drop the row B.\n",
                        encoding="utf-8")

    def map_rows(self, *rows):
        path = self.root / self.MAP
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + "".join(row + "\n" for row in rows),
                        encoding="utf-8")
        return path.read_text(encoding="utf-8").count("\n")

    def test_paragraph_with_one_id_and_a_merged_id_pass(self):
        import check_forms
        self.merge()
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        self.assertEqual(check.stats["req_map"], len(m_form.req_map_lines(ROOT / self.MAP)) + 1)   # the journal and ours
        self.assertGreater(check.stats["req_refs"], 0)
        self.assertEqual(check_forms.check_req_anchors(self.home)[0], [])

    def test_reference_to_a_merged_a_removed_or_an_unknown_id_fails(self):
        self.merge()
        readme = "acceptance/1/README.md"
        line = self.add_sentence(readme, f"The rule {self.old} holds. The rule P/01.1-R014 holds. "
                                         f"The rule {self.spare} holds.")
        self.replace("forms/runtime-constants.tsv", "\n", f"\n# the constant of {self.old}\n")
        check = self.run_checks()
        self.assert_error(check, f"{HOME}/{readme}", line, f"a reference to {self.old}, merged into {self.new}")
        self.assert_error(check, f"{HOME}/{readme}", line, "P/01.1-R014, a removed requirement")
        self.assert_error(check, f"{HOME}/{readme}", line, f"{self.spare}, not a requirement of P/01")
        self.assert_error(check, f"{HOME}/forms/runtime-constants.tsv", 2, f"merged into {self.new}")
        self.assertEqual(len(check.errors), 4, check.errors)

    def test_short_reference_in_the_norms_by_its_chapter(self):
        self.merge()
        short = self.old.split("-")[-1]
        self.replace(self.NORMS, "The limit of the rows is 3.", f"The limit of the rows is 3 ({short}).")
        check = self.run_checks()
        self.assert_error(check, f"{HOME}/{self.NORMS}", self.line_of(self.NORMS, f"({short})"),
                          f"a short reference {short} to {self.old}, merged into {self.new}")
        self.setUp()
        self.merge()
        self.replace(self.NORMS, "The limit of the rows is 3.", f"The limit of the rows is 3 (chapter 1.1 {short}).")
        self.assertEqual(self.run_checks().errors, [])     # P/01.1 of that number is not merged

    def test_reuse_of_a_merged_id_fails(self):
        import check_forms
        self.merge()
        self.replace(self.NORMS, f"<!-- req: {self.new} -->", f"<!-- req: {self.old} -->\n- `again` — The daemon MUST "
                                                             f"do D.\n\n<!-- req: {self.new} -->")
        errors = self.run_checks().errors
        self.assertTrue(any(f"old {self.old} is a live anchor" in e for e in errors), errors)
        errors = check_forms.check_req_anchors(self.home)[0]
        self.assertTrue(any(f"anchor {self.old} reuses a number merged into {self.new}" in e for e in errors), errors)

    def test_index_row_naming_a_merged_id_fails(self):
        self.merge()
        rel = "spec/01.1-store.norms.md"
        n, _, cell, _ = m_form.index_rows(self.home / rel, "en")[0]
        lines = (self.home / rel).read_text(encoding="utf-8").split("\n")
        lines[n - 1] = lines[n - 1].replace(cell, f"{cell}, {self.old}", 1)
        (self.home / rel).write_text("\n".join(lines), encoding="utf-8")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", n, f"index: {self.old} is merged into {self.new}")

    def test_rows_of_the_map_fail(self):
        def cases():
            unused = self.free(3, 2)[1]                      # neither live, merged nor in the history
            return [
                (f"{self.spare}\t{unused}\t{self.address}\tx", "is not a live requirement"),
                (f"{self.spare}\t{self.old}\t{self.address}\tx", "a merged id: no chains"),
                (f"{self.spare}\tP/01.1-R014\t{self.address}\tx", "a removed id"),
                (f"{self.spare}\t{self.new}\tspec/01.1-store.norms.md#N1\tx", f"the paragraph of {self.new} is in"),
                (f"{self.spare}\t{self.new}\t{self.NORMS}#N9\tx", "no section N9"),
                (f"{self.spare}\t{self.new}\t{self.address}\tx", "has no row of the history files"),
                (f"P/01.1-R014\t{self.new}\t{self.address}\tx", "has a tombstone in the norms"),
                (f"{self.old}\t{self.new}\t{self.address}\tx", f"old {self.old} repeats"),
                (f"P/02.1-R001\t{self.new}\t{self.address}\tx", "is not a requirement id of P/01"),
                (f"{self.spare}\t{self.new}\t{self.address}\t ", "an empty source"),
                (f"{self.spare}\t{self.new}\t{self.address}", "3 fields"),
            ]
        for i in range(11):
            self.setUp()
            self.merge()
            row, words = cases()[i]
            with self.subTest(words=words):
                line = self.map_rows(row)
                self.assert_error(self.run_checks(), self.MAP, line, words)
        self.setUp()
        self.merge()
        path = self.root / self.MAP
        path.write_text(path.read_text(encoding="utf-8").replace("old\tnew", "old\tlive", 1), encoding="utf-8")
        self.assert_error(self.run_checks(), self.MAP, 1, "the header")

    def test_history_row_of_a_merged_id_passes_and_of_an_unmapped_one_fails(self):
        self.merge()
        self.history(self.old)                               # a second row of the same merged id
        self.assertEqual(self.run_checks().errors, [])
        self.history(self.spare)
        errors = self.run_checks().errors
        self.assertTrue(any(f"req_id {self.spare} is not a requirement of P/01" in e for e in errors), errors)


class ShortIndex(AcceptedForm):
    """An index names only the topics whose rules stand in more than one place: a short index and none at all pass."""

    def keep_rows(self, rel, language, count):
        path = self.home / rel
        drop = {n for n, *_ in m_form.index_rows(path, language)[count:]}
        lines = path.read_text(encoding="utf-8").split("\n")
        path.write_text("\n".join(line for n, line in enumerate(lines, 1) if n not in drop), encoding="utf-8")

    def drop_index(self, rel, heading):
        path = self.home / rel
        text = path.read_text(encoding="utf-8")
        start = text.index(heading + "\n")
        end = text.index("\n## ", start + len(heading))
        path.write_text(text[:start] + text[end + 1:], encoding="utf-8")

    def test_short_index_and_no_index_pass(self):
        rel = "spec/01.1-store.norms.md"
        self.assertGreater(len(m_form.index_rows(self.home / rel, "en")), 1)
        self.keep_rows(rel, "en", 1)
        self.keep_rows("ru/" + rel, "ru", 1)
        rel2 = "spec/01.2-store.norms.md"
        self.drop_index(rel2, "## Index")
        self.drop_index("ru/" + rel2, "## Указатель")
        self.assertIsNone(m_form.index_rows(self.home / rel2, "en"))
        # the history rows of the index go to the place that stays (an address resolves: history_rows)
        path = self.root / JOURNAL / "history-2.tsv"
        path.write_text(path.read_text(encoding="utf-8").replace(f"{rel2}#index\t", f"{rel2}#intro\t"),
                        encoding="utf-8")
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        self.assertGreater(check.stats["index_refs"], 0)


class JudgeOnlyByReference(AcceptedForm):
    """A marker «(judge-only: …)» is needed only where M names a file outside M; for a lesson of M_NARROW a file of
    another lesson that its dependency table does not name is outside M of the pair (the filters cut whole files)."""
    REL = "acceptance/1/README.md"

    def add(self, sentence):
        return self.add_sentence(self.REL, sentence)

    def outside_file(self):
        check = Check(self.root, scope="platform")
        model = m_form.export_model(check)
        pair = m_form.pair_m(check, m_form.Lesson(check, "P/01", self.home), model)
        return next(p for p, d in sorted(model.items()) if d == "model_and_judge" and p not in pair and
                    "/ru/" not in p and p.endswith(".md"))

    def test_common_files_of_another_lesson_are_outside_the_pair(self):
        check = Check(self.root, scope="platform")
        model = m_form.export_model(check)
        pair = m_form.pair_m(check, m_form.Lesson(check, "P/01", self.home), model)
        for path in m_form.PAIR_COMMON_EXCLUDE["P/01"]:
            self.assertIn(path, model)
            self.assertNotIn(path, pair)
        self.assertTrue(any(p.startswith("Platform/common/") for p in pair))
        excluded = m_form.PAIR_COMMON_EXCLUDE["P/01"][0]
        line = self.add(f"The stand is in `{excluded}`.")
        errors = self.run_checks().errors
        self.assertTrue(any(excluded in e and f"{HOME}/{self.REL}" in e for e in errors), errors)

    def test_marker_without_a_reference_is_not_an_error(self):
        self.add("The order of the refusals is fixed (judge-only: a scenario of the chapter checks it).")
        self.assertEqual(self.run_checks().errors, [])

    def test_reference_outside_the_pair_without_marker_fails(self):
        other = self.outside_file()
        line = self.add(f"The other side is in `{other}`.")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", line, f"{other}, a file of another lesson outside M "
                                                                         "of the pair P/01")
        with patch.object(m_form, "M_NARROW", set()):
            self.assertEqual(self.run_checks().errors, [])  # the global M has the file: the lesson is not narrowed

    def test_link_outside_the_pair_from_the_readme_fails(self):
        other = self.outside_file()
        self.replace("README.md", "\n", f"\nThe other side is [there](../{other[len('Platform/'):]}).\n")
        self.assert_error(self.run_checks(), f"{HOME}/README.md", 2, "outside M of the pair P/01")

    def test_reference_outside_the_pair_marked_or_in_the_dependency_table_passes(self):
        other = self.outside_file()
        self.add(f"The other side is in `{other}` (judge-only: the other lesson).")
        self.assertEqual(self.run_checks().errors, [])
        self.setUp()
        self.add(f"The other side is in `{other}`.")
        text = (self.home / "README.md").read_text(encoding="utf-8")
        head = text.index(m_form.DEPENDENCIES["en"])
        rule = text.index("|---|", head)
        end = text.index("\n", rule) + 1
        row = f"| [`{other}`](../{other[len('Platform/'):]}) | the whole file | a test dependency |\n"
        (self.home / "README.md").write_text(text[:end] + row + text[end:], encoding="utf-8")
        self.assertEqual(self.run_checks().errors, [])

    def test_narrow_lesson_without_the_dependency_table_fails(self):
        self.replace("README.md", m_form.DEPENDENCIES["en"], "## What this lesson borrows")
        errors = self.run_checks().errors
        self.assertTrue(any("is in m_form.M_NARROW, and its README.md has no" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()


class CommonAcceptanceInScope(unittest.TestCase):
    """P01.230: the common acceptance is judged by the checks of form M since P01.229 put it into the form."""

    def test_common_acceptance_is_in_scope(self):
        self.assertIn("Platform/common/acceptance/", m_form.M_FORM_COMMON)
