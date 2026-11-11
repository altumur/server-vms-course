"""The six checks of the reading form of M (m_form.py) on the accepted form of P/01 and on spoiled copies of it."""

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
        for path in (ROOT / JOURNAL).glob("history*.tsv"):
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


class AcceptedFormPasses(AcceptedForm):
    def test_accepted_form_passes_every_check_with_counts(self):
        check = self.run_checks()
        self.assertEqual(check.errors, [])
        for name in ("history_phrases", "index_refs", "see_also_refs", "judge_only_refs", "production_scoped",
                     "history_rows"):
            self.assertGreater(check.stats[name], 0, name)

    def test_run_through_check_spec_method_only_for_checked_lessons(self):
        check = Check(self.root, scope="platform")
        check.m_form()                                   # no lesson checked in this run — nothing to judge
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
        check = self.run_checks()
        self.assertFalse([e for e in check.errors if "common/acceptance" in e], "not included yet")
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

    def test_adr_later_keeps_forms_and_a_new_file_is_judged(self):
        self.replace("forms/runtime-constants.tsv", "\n", "\n# the constants of ADR-0129\n")
        self.assertEqual(self.run_checks().errors, [], "forms/*.tsv — after P01.176")
        self.replace("probes/README.md", "\n", "\nThe probes of ADR-0133.\n")
        self.assert_error(self.run_checks(), f"{HOME}/probes/README.md", 2, "an ADR number in M")

    def test_stale_adr_later_entry(self):
        for rel in ("vectors/rights-evaluator/README.md", "ru/vectors/rights-evaluator/README.md"):
            path = self.home / rel
            path.write_text(re.sub(r" ?\(ADR-0[0-9]{3}[^)]*\)|ADR-0[0-9]{3}", "", path.read_text(encoding="utf-8")),
                            encoding="utf-8")
        errors = self.run_checks().errors
        self.assertTrue(any("vectors/rights-evaluator/README.md: stale ADR_LATER" in e for e in errors), errors)

    def test_built_text_is_judged_at_its_builder(self):
        rel = "spec/01.3-store.norms.md"
        self.replace(rel, "<!-- families:end -->", "the Architect's decision of 2026-10-27\n<!-- families:end -->")
        self.replace("data/epoch_floor.schema.json", '"description": "', '"description": "the Architect\'s decision; ')
        self.assertEqual(self.run_checks().errors, [])


class IndexRefs(AcceptedForm):
    REL = "spec/01.1-store.norms.md"

    def test_unknown_removed_and_malformed_requirement(self):
        for bad, words in (("P/01.1-R999", "not a requirement of P/01"), ("P/01.1-R0x7", "not a requirement id"),
                           ("P/02.1-R001", "not a requirement of P/01")):
            with self.subTest(bad=bad):
                self.setUp()
                self.replace(self.REL, "| P/01.1-R019, P/01.1-R020, P/01.1-R073, P/01.1-R118 |",
                             f"| P/01.1-R019, P/01.1-R020, P/01.1-R073, P/01.1-R118, {bad} |")
                self.assert_error(self.run_checks(), f"{HOME}/{self.REL}",
                                  self.line_of(self.REL, "`row_ceiling`"), words)

    def test_order_and_repeat(self):
        self.replace(self.REL, "| P/01.1-R019, P/01.1-R020, P/01.1-R073, P/01.1-R118 |",
                     "| P/01.1-R020, P/01.1-R019, P/01.1-R073, P/01.1-R118 |")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "`row_ceiling`"), "ascending")

    def test_file_addresses_two_roots_no_fallback(self):
        # Both roots of the accepted index pass (the base test); a wrong prefix fails: no search over a second root.
        self.replace(self.REL, "`Platform/common/acceptance/README.md` «Store group stand»",
                     "`common/acceptance/README.md` «Store group stand»")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "`group_stand`"),
                          "no file `common/acceptance/README.md`")

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
        self.replace(rel, "P/01.1-R019, P/01.1-R020, P/01.1-R073, P/01.1-R118", "P/01.1-R019, P/01.1-R073, P/01.1-R118")
        check = self.run_checks()
        self.assertTrue(any(e.startswith(f"{HOME}/{rel}: line ") and "index row differs" in e for e in check.errors),
                        check.errors)


class SeeAlsoRefs(unittest.TestCase):
    """A small chapter: the See also lines against the union of the index topics (P01.214 C5)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m-form-see-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / HOME
        (self.home / "spec").mkdir(parents=True)
        (self.home / "ru/spec").mkdir(parents=True)

    def chapter(self, rows, see, ru_see=None):
        head = "# P/01.1\n\n## Index\n\n| Topic | Requirements | Files |\n|---|---|---|\n" + "".join(
            f"| `t{i}` t | {', '.join(ids)} | `spec/01.1-store.norms.md` |\n" for i, ids in enumerate(rows))
        body = "\n## N0 Vocabulary\n\n" + "".join(
            f"<!-- req: P/01.1-R00{n} -->\nRule {n}.\n\n" + (f"See also: {', '.join(see[n])}.\n\n" if see.get(n) else "")
            for n in range(1, 6))
        (self.home / "spec/01.1-store.norms.md").write_text(head + body, encoding="utf-8")
        ru_see = see if ru_see is None else ru_see
        (self.home / "ru/spec/01.1-store.norms.md").write_text(
            head.replace("## Index", "## Указатель") + "\n## N0 Словарь\n\n" + "".join(
                f"Правило {n}.\n\n" + (f"См. также: {', '.join(ru_see[n])}.\n\n" if ru_see.get(n) else "")
                for n in range(1, 6)), encoding="utf-8")
        check = Check(self.root, scope="platform")
        m_form.see_also_refs(check, m_form.Lesson(check, "P/01", self.home))
        return check

    @staticmethod
    def ids(*numbers):
        return [f"P/01.1-R00{n}" for n in numbers]

    def test_intersecting_topics_give_the_union(self):
        check = self.chapter([self.ids(1, 2, 3), self.ids(3, 4)],
                             {1: self.ids(2, 3), 2: self.ids(1, 3), 3: self.ids(1, 2, 4), 4: self.ids(3)})
        self.assertEqual(check.errors, [])
        self.assertEqual(check.stats["see_also_refs"], 4)

    def test_symmetric_cycle_is_not_the_union(self):
        check = self.chapter([self.ids(1, 2, 3, 4)],
                             {1: self.ids(2, 4), 2: self.ids(1, 3), 3: self.ids(2, 4), 4: self.ids(1, 3)})
        self.assertEqual(len([e for e in check.errors if "not the union" in e]), 4, check.errors)
        text = (self.home / "spec/01.1-store.norms.md").read_text(encoding="utf-8")
        line = text[:text.index("See also: P/01.1-R002, P/01.1-R004")].count("\n") + 1
        self.assertTrue(any(f": line {line}: See also of P/01.1-R001" in e and "missing P/01.1-R003" in e
                            for e in check.errors), check.errors)

    def test_missing_line_extra_line_order_repeat_self(self):
        cases = [
            ({1: self.ids(2)}, "P/01.1-R002 is in an index row and has no"),
            ({1: self.ids(2), 2: self.ids(1), 5: self.ids(1)}, "which is in no index row"),
            ({1: ["P/01.1-R002", "P/01.1-R002"], 2: self.ids(1)}, "ascending, each id once"),
            ({1: self.ids(1, 2), 2: self.ids(1)}, "names itself"),
            ({1: ["P/01.1-R009"], 2: self.ids(1)}, "is not a requirement of P/01"),
        ]
        for see, words in cases:
            with self.subTest(words=words):
                check = self.chapter([self.ids(1, 2)], see)
                self.assertTrue(any(re.search(r": line [0-9]+: ", e) and words in e for e in check.errors), check.errors)

    def test_translation_differs(self):
        check = self.chapter([self.ids(1, 2)], {1: self.ids(2), 2: self.ids(1)}, {1: self.ids(2), 2: self.ids(1, 2)})
        self.assertTrue(any("ru/spec/01.1-store.norms.md: line " in e and "differs" in e for e in check.errors),
                        check.errors)


class JudgeOnlyRefs(AcceptedForm):
    REL = "acceptance/1/README.md"
    ANCHOR = "The table `scenarios.tsv` of the chapter"

    def add(self, sentence):
        self.replace(self.REL, self.ANCHOR, sentence + " " + self.ANCHOR)
        return self.line_of(self.REL, sentence)

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
        self.assertEqual(check.stats["production_scoped"], 6)       # R148, R150, item 32 — source and translation

    def test_acting_label_inside_a_paragraph(self):
        self.replace(self.REL, "Persistence of an ordinary fixed-size write MUST be incremental:",
                     "Persistence of an ordinary fixed-size write **Scope: production.** MUST be incremental:")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}",
                          self.line_of(self.REL, "fixed-size write **Scope"), "inside a paragraph")

    def test_label_opening_a_second_paragraph_of_a_requirement(self):
        self.replace(self.REL, "\nSee also: P/01.1-R149, P/01.1-R150.",
                     "\n**Scope: production.** A second paragraph.\n\nSee also: P/01.1-R149, P/01.1-R150.")
        self.assert_error(self.run_checks(), f"{HOME}/{self.REL}", self.line_of(self.REL, "A second paragraph"),
                          "not the first after a req anchor")

    def test_label_in_the_translation_inside_a_paragraph(self):
        rel = "ru/" + self.REL
        self.replace(rel, "**Охват: боевой.** Сохранение", "Сохранение **Охват: боевой.**")
        self.assert_error(self.run_checks(), f"{HOME}/{rel}", self.line_of(rel, "Сохранение **Охват"),
                          "inside a paragraph")


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

    def test_history_of_a_chapter_the_lesson_has_not(self):
        shutil.copy(self.journal("history-1.tsv"), self.journal("history-9.tsv"))
        errors = self.run_checks().errors
        self.assertTrue(any("history-9.tsv: a history file of chapter 9" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
