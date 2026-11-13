"""ADR-0133 addendum (102), OBSH.56: the references of the cells of the forms (form_refs) on synthetic lessons only."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_forms
import form_refs
from check_spec import Check

NORMS = """# P/01.1 — Store: norms

## N1 Form

### N1.2 Keys

**N1.2a The view.** A paragraph that opens with its section.

**Races.** A paragraph that opens with its title.

## N4 Refusals

## Implementation decides

### Data families (built from the standard files)

## Readiness checklist

- [ ] **P/01.1-01** [test] First item.
- [ ] **P/01.1-02** [test] Second item.

## System checklist

- [ ] **P/01.1-03** [reading] A system item.
"""


class FormRefs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="form-refs-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "Platform/01-store"
        self.write("Platform/lessons.tsv", "# lesson\tdir\ttitle\n01\t01-store\tStore\n02\t02-installer\tInstaller\n")
        self.write("Platform/01-store/spec/01.1-store.norms.md", NORMS)
        self.write("Platform/01-store/spec/01.2-store.norms.md",
                   "# P/01.2\n\n## N2 Doors\n\n## Readiness checklist\n\n- [ ] **P/01.2-01** [test] One.\n")
        self.write("Platform/02-installer/spec/02-installer.norms.md",
                   "# P/02\n\n## N3 Install\n\n## Readiness checklist\n\n- [ ] **P/02-01** [test] One.\n")
        self.write("Platform/01-store/forms/input.tsv", "# a form\nkey\tvalue\na\t1\n")
        self.write("Platform/01-store/forms/judge.tsv", "key\tvalue\nb\t2\n")
        self.write("Platform/01-store/vectors/pkg/expect.tsv", "x\n")
        self.write("Platform/01-store/lifecycle.md", "# Lifecycle\n")
        self.write("Platform/common/contracts/store-client.md", "# Store client\n\n## Calls\n")
        self.write("Platform/common/acceptance/README.md", "# Acceptance\n")
        self.write("Platform/common/acceptance/stand.md", "# Stand\n")
        self.write("Platform/01-store/data/rows.schema.json", '{"$defs": {"row": {"maxItems": 3}}}\n')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def stages(self, *norms):
        return self.write("Platform/01-store/forms/stages.tsv", "n\tstage\tgoal\tnorms\tgate\n" + "".join(
            f"{i}\ts{i}\tgoal\t{cell}\tbuild\n" for i, cell in enumerate(norms, 1)))

    def refusals(self, *cells):
        return self.write("Platform/01-store/forms/refusals.tsv", "# the refusals\nname\tnorm\tcause\n" + "".join(
            f"r{i}\tP/01.1 N4\t{cell}\n" for i, cell in enumerate(cells, 1)))

    def run_check(self, model=None):
        check = Check(self.root, scope="platform")
        if model is None:
            check.form_refs()
        else:
            with patch.object(form_refs.Index, "model", lambda self: model):
                check.form_refs()
        return check

    def assert_dangling(self, check, *parts):
        self.assertTrue(any(all(p in e for p in parts) for e in check.errors), check.errors)

    def test_live_references_pass(self):
        self.stages("P/01.1 N1; P/01.1 N1.2; P/01.1 N1.2a; P/01.1 «Implementation decides»; P/01.1 «Races»; "
                    "P/01.1 «Data families»; forms/input.tsv; vectors/pkg; lifecycle.md; common/contracts/store-client.md; "
                    "P/02 N3; P/01.1-01; P/01.1-02")
        self.refusals("[the form](../spec/01.1-store.norms.md#n12-keys); `Platform/01-store/forms/input.tsv:3`, "
                      "`Platform/01-store/forms/input.tsv:2–3`, forms/input.tsv#row:a; P/01.1-03, P/01.2-01, P/02-01, "
                      "P/01.2 N2; common/contracts/store-client.md#calls; data/rows.schema.json#/$defs/row/maxItems")
        self.write("Platform/common/acceptance/forms/stand-environment.tsv",
                   "key\tnorm\nk\tstand.md; README.md; P/01.1 N4\n")
        check = self.run_check()
        self.assertEqual(check.errors, [])
        self.assertGreaterEqual(check.stats["form_refs"], 20)
        self.assertEqual(check.stats["form_refs_dangling"], 0)

    def test_missing_file_is_dangling_with_form_line_column_and_reason(self):
        self.stages("P/01.1 N1", "P/01.1 N4; forms/group.tsv")
        check = self.run_check()
        self.assert_dangling(check, "Platform/01-store/forms/stages.tsv: line 3, column norms: «forms/group.tsv»",
                             "dangling reference: no file Platform/01-store/forms/group.tsv")
        self.assertEqual(check.stats["form_refs_dangling"], 1)

    def test_markdown_link_resolves_from_the_directory_of_the_form(self):
        self.refusals("[chapter 1.1](01.1-store.norms.md) N4", "[common](../../common/contracts/gone.md)")
        check = self.run_check()
        self.assert_dangling(check, "line 3, column cause: «01.1-store.norms.md»",
                             "no file Platform/01-store/forms/01.1-store.norms.md")
        self.assert_dangling(check, "line 4, column cause", "no file Platform/common/contracts/gone.md")
        self.assertEqual(len(check.errors), 2)

    def test_line_beyond_the_end_of_the_file(self):
        self.refusals("`Platform/01-store/forms/input.tsv:4`", "see Platform/01-store/forms/input.tsv:2-9",
                      "Platform/01-store/forms/input.tsv:3-2")
        check = self.run_check()
        self.assert_dangling(check, "line 3,", "line 4 is beyond the end of Platform/01-store/forms/input.tsv (3 lines)")
        self.assert_dangling(check, "line 4,", "line 9 is beyond the end")
        self.assert_dangling(check, "line 5,", "lines 3–2 of Platform/01-store/forms/input.tsv: an empty range")

    def test_missing_anchor_pointer_and_row(self):
        self.refusals("common/contracts/store-client.md#no-such-heading", "data/rows.schema.json#/$defs/none",
                      "forms/input.tsv#row:zz")
        check = self.run_check()
        self.assert_dangling(check, "line 3,", "no heading anchor #no-such-heading")
        self.assert_dangling(check, "line 4,", "no JSON Pointer")
        self.assert_dangling(check, "line 5,", "#row:zz: no row")

    def test_missing_section_title_chapter_and_lesson(self):
        self.refusals("P/01.1 N7", "P/01.1 «No such title»", "P/01.4 N1", "P/42 N1", "P/01.1 N1.3")
        check = self.run_check()
        self.assert_dangling(check, "line 3, column cause: «P/01.1 N7»", "no section «N7» in the norms of P/01.1")
        self.assert_dangling(check, "line 4,", "no section «No such title»")
        self.assert_dangling(check, "line 5,", "no norms file of P/01.4")
        self.assert_dangling(check, "line 6,", "no lesson 42")
        self.assert_dangling(check, "line 7,", "no section «N1.3»")
        self.assertEqual(len(check.errors), 5)

    def test_missing_checklist_item(self):
        self.refusals("P/01.1-09", "P/01.2-07", "P/02-05")
        self.write("Platform/01-store/forms/stages.kit.tsv", "n\tstage\tnorms\tgate\n1\ts\tP/01.1-08\tbuild\n")
        check = self.run_check()
        for line, item, form in ((3, "P/01.1-09", "refusals"), (4, "P/01.2-07", "refusals"), (5, "P/02-05", "refusals"),
                                 (2, "P/01.1-08", "stages.kit")):
            self.assert_dangling(check, f"forms/{form}.tsv: line {line},", f"{item} is no item of the readiness")
        self.assertEqual(len(check.errors), 4)

    def test_own_items_of_stages_are_left_to_stage_norms(self):
        self.stages("P/01.1 N1; P/01.1-99")
        self.assertEqual(self.run_check().errors, [])

    def test_file_of_m_naming_a_judge_only_file_dangles_in_m(self):
        stages = self.stages("P/01.1 N1; forms/judge.tsv", "P/01.1 N4; forms/input.tsv",
                             "P/01.1 N4; forms/judge.tsv (judge-only: the stand)")
        model = {"Platform/01-store/forms/stages.tsv": "model_and_judge",
                 "Platform/01-store/forms/input.tsv": "model_and_judge",
                 "Platform/01-store/forms/judge.tsv": "judge_only"}
        check = self.run_check(model)
        self.assert_dangling(check, "line 2, column norms: «forms/judge.tsv»",
                             "Platform/01-store/forms/judge.tsv is not in M")
        self.assertEqual(len(check.errors), 1)
        model[stages.relative_to(self.root).as_posix()] = "judge_only"     # a judge-only form may name judge files
        self.assertEqual(self.run_check(model).errors, [])

    def test_prose_and_other_grammars_are_no_references(self):
        self.refusals("`configstore-rights.json.new` of the platform; go.yaml.in/yaml/v3",
                      "$data/forms/x.json and /etc/w2c/data/x.json; vectors:common/sealing",
                      '[{"owner":"01-store","section":"vectors","key":"common/crl"}]',
                      "forms/<name>.tsv, spec/*.norms.md, acceptance/{K}/README.md, data/… of a lesson",
                      "P/01.1-R123 and P/01.1 R12; https://example.org/forms/x.md; [a](#local)")
        self.assertEqual(self.run_check().errors, [])

    def test_gate_targets_are_judged_by_check_forms(self):
        self.write("Platform/01-store/acceptance/1/scenarios.tsv", "01-absent\t1\tGET /x\t200\n")
        self.write("Platform/01-store/acceptance/1/seams.tsv", "s1-id\t1\tRUN x\texit 0\n")
        path = self.write("Platform/01-store/forms/stages.tsv", "n\tstage\tnorms\tgate\n"
                          "1\ta\tP/01.1 N1\taccept:1.1:01-absent;seams:1.1:s1-id\n"
                          "2\tb\tP/01.1 N1\taccept:1.1:02-gone\n3\tc\tP/01.1 N1\tseams:1.1:s9-gone\n")
        errors, _ = check_forms.check_stage_parts(path)
        self.assertTrue(any("b: scenarios ['02-gone']" in e for e in errors), errors)
        self.assertTrue(any("c: scenarios ['s9-gone']" in e for e in errors), errors)
        self.assertEqual(len(errors), 2, errors)
        self.assertEqual(self.run_check().errors, [])      # gates are not judged twice

    def test_forms_of_common_resolve_from_their_home_and_translations_are_left_out(self):
        self.write("Platform/common/acceptance/forms/stand-environment.tsv", "key\tnorm\nk\tstand.md; gone.md\n")
        self.write("Platform/01-store/ru/forms/input.tsv", "key\tnorm\nk\tforms/gone.tsv\n")
        check = self.run_check()
        self.assert_dangling(check, "Platform/common/acceptance/forms/stand-environment.tsv: line 2, column norm: «gone.md»",
                             "no file Platform/common/acceptance/gone.md or Platform/gone.md")
        self.assertEqual(len(check.errors), 1)


if __name__ == "__main__":
    unittest.main()
