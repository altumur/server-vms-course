"""ADR-0126(9) transitional stage validation and frozen generator inputs."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import check_forms
import gen_tests


class StageMigrationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stage-grammar-control-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lesson = self.root / "Platform/01-store"
        (self.lesson / "forms").mkdir(parents=True)
        chapter = self.lesson / "acceptance/1"
        chapter.mkdir(parents=True)
        (chapter / "scenarios.tsv").write_text("ordinary\t1\trequest\tresponse\n")
        (chapter / "seams.tsv").write_text("edge\t1\trequest\tresponse\n")

    def write(self, name="stages.tsv", *, kit=False, gate="build", depends="-", extra=None):
        head = ["n", "stage", "goal", "norms", "gate", "weight", "depends", "when"]
        row = ["1", "foundation", "goal", "norm", gate, "1", depends, "true"]
        if kit:
            head += ["kit", "parts"]
            row += ["-", "door,refusals"]
        if extra:
            head += [extra[0]]
            row += [extra[1]]
        text = io.StringIO(newline="")
        writer = csv.writer(text, delimiter="\t", lineterminator="\n")
        writer.writerow(head)
        writer.writerow(row)
        path = self.lesson / "forms" / name
        path.write_text(text.getvalue())
        return path

    def errors(self, **kwargs):
        return check_forms.check_stage_parts(self.write(**kwargs))[0]

    def test_legacy_public_refuses_but_retained_kit_form_remains_admitted(self):
        gate = "tests:1.1:ordinary;tests:1.1:edge:seams;accept:1.1:ordinary"
        self.assertTrue(self.errors(kit=True, gate=gate))
        self.assertEqual(self.errors(name="stages.kit.tsv", kit=True, gate=gate), [])

    def test_package_free_accept_and_seams_with_same_case_scope_pass(self):
        self.assertEqual(self.errors(gate="accept:1.1:ordinary;seams:1.1:edge"), [])
        self.assertEqual(self.errors(gate="accept:1.1:*;seams:1.1:*"), [])

    def test_retained_kit_requires_both_package_columns(self):
        self.assertTrue(self.errors(name="stages.kit.tsv", kit=False))
        self.assertTrue(self.errors(extra=("kit", "-")))
        self.assertTrue(self.errors(extra=("parts", "door")))

    def test_accept_and_seams_do_not_borrow_each_others_case_names(self):
        for gate in ("accept:1.1:edge", "seams:1.1:ordinary", "seams:1.1:missing"):
            with self.subTest(gate=gate):
                self.assertTrue(self.errors(gate=gate))

    def test_same_folder_number_in_another_lesson_is_not_a_chapter_match(self):
        for gate in ("accept:2.1:ordinary", "seams:2.1:edge", "tests:2.1:edge:seams"):
            with self.subTest(gate=gate):
                self.assertTrue(any("not in lesson" in error for error in self.errors(gate=gate)))

    def test_single_chapter_lesson_resolves_its_root_acceptance_tables(self):
        lesson = self.root / "Platform/04-controller"
        (lesson / "forms").mkdir(parents=True)
        (lesson / "acceptance").mkdir()
        (lesson / "acceptance/scenarios.tsv").write_text("ordinary\t1\tx\ty\n")
        (lesson / "acceptance/seams.tsv").write_text("edge\t1\tx\ty\n")
        self.assertEqual(check_forms.gate_errors(lesson, "row", "accept:4:ordinary"), [])
        self.assertEqual(check_forms.gate_errors(lesson, "row", "seams:4:edge"), [])
        self.assertTrue(check_forms.gate_errors(lesson, "row", "seams:4.1:edge"))

    def test_missing_case_table_refuses_even_a_wildcard(self):
        (self.lesson / "acceptance/1/seams.tsv").unlink()
        self.assertTrue(self.errors(gate="seams:1.1:*"))
        self.assertEqual(self.errors(gate="accept:1.1:*"), [])

    def test_invalid_shape_gate_duplicates_and_package_names_stay_red(self):
        for gate in ("seams:1.1:", "seams:1.1:edge:seams", "seams:1.1:edge,edge",
                     "accept:1.1:ordinary;", "build;build", "seams:1.1:edge; seams:1.1:edge"):
            with self.subTest(gate=gate):
                self.assertTrue(self.errors(gate=gate))
        self.assertTrue(self.errors(depends="1"))
        path = self.write(name="stages.kit.tsv", kit=True)
        path.write_text(path.read_text().replace("door,refusals", "door,unknown"))
        self.assertTrue(check_forms.check_stage_parts(path)[0])
        path = self.write()
        path.write_text(path.read_text().replace("\ttrue\n", "\ttrue\textra\n"))
        self.assertTrue(check_forms.check_stage_parts(path)[0])
        path = self.write(extra=("stage", "duplicate"))
        self.assertTrue(check_forms.check_stage_parts(path)[0])

    def test_discovery_includes_public_and_kit_forms_without_vms(self):
        first = self.write()
        second = self.write(name="stages.kit.tsv", kit=True)
        foreign = self.root / "VMS/11-backend/forms"
        foreign.mkdir(parents=True)
        (foreign / "stages.tsv").write_text("not a Platform form")
        self.assertEqual(check_forms.stage_forms(self.root), sorted((first, second)))


class KitStageConsumerControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kit-stage-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.forms = self.root / "Platform/01-store/forms"
        self.forms.mkdir(parents=True)
        self.kit = self.forms / "stages.kit.tsv"
        self.public = self.forms / "stages.tsv"
        self.kit.write_text("stage\tgate\nkept\tvectors:jcs\n")

    def test_generator_reads_retained_kit_not_new_public_stage_grammar(self):
        self.public.write_text("stage\tgate\nchanged\tseams:1.1:*\n")
        stages, source = gen_tests.read_stages(self.root)
        self.assertEqual(stages, {"jcs": "kept"})
        self.assertEqual(source.rel, "Platform/01-store/forms/stages.kit.tsv")
        self.assertEqual(source.data, self.kit.read_bytes())
        self.assertIn(source.rel, gen_tests.go_head([source]))

    def test_no_silent_fallback_to_public_stages_when_kit_is_missing(self):
        self.public.write_text(self.kit.read_text())
        self.kit.unlink()
        with self.assertRaises(FileNotFoundError):
            gen_tests.read_stages(self.root)

    def test_changed_kit_is_an_actual_generator_input_and_header_hash(self):
        before, old_source = gen_tests.read_stages(self.root)
        self.kit.write_text("stage\tgate\nnew_kept\tvectors:jcs\n")
        after, new_source = gen_tests.read_stages(self.root)
        self.assertNotEqual(before, after)
        self.assertNotEqual(old_source.sha256, new_source.sha256)
        self.assertIn(new_source.sha256, gen_tests.go_head([new_source]))


class Phase3PublicStageControls(unittest.TestCase):
    setUp = StageMigrationControls.setUp
    write = StageMigrationControls.write
    errors = StageMigrationControls.errors

    def test_public_tests_gate_tokens_refuse_even_without_package_columns(self):
        for gate in ("tests:1.1:ordinary", "tests:1.1:edge:seams",
                     "build;tests:1.1:edge:seams;accept:1.1:ordinary"):
            with self.subTest(gate=gate):
                self.assertTrue(any("legacy tests:" in error for error in self.errors(gate=gate)))

    def test_reserved_package_column_heads_refuse_in_any_position(self):
        for head in ("kit", "parts"):
            for position in (0, 3, 8):
                with self.subTest(head=head, position=position):
                    path = self.write(extra=(head, "-"))
                    rows = list(csv.reader(io.StringIO(path.read_text()), delimiter="\t"))
                    for row in rows:
                        value = row.pop()
                        row.insert(position, value)
                    text = io.StringIO(newline="")
                    csv.writer(text, delimiter="\t", lineterminator="\n").writerows(rows)
                    path.write_text(text.getvalue())
                    self.assertTrue(any("package columns" in error
                                        for error in check_forms.check_stage_parts(path)[0]))
        self.assertTrue(any("package columns" in error for error in self.errors(kit=True)))

    def test_kit_legacy_columns_and_tests_are_still_accepted(self):
        gate = "tests:1.1:ordinary;tests:1.1:edge:seams;accept:1.1:ordinary"
        self.assertEqual(self.errors(name="stages.kit.tsv", kit=True, gate=gate), [])
        self.assertEqual(check_forms.gate_errors(self.lesson, "legacy", "tests:1.1:edge:seams"), [])

    def test_literal_stage_case_and_business_prose_no_kit_are_not_banned(self):
        chapter = self.lesson / "acceptance/1/scenarios.tsv"
        chapter.write_text(chapter.read_text() + "s18-accept-no-kit\t1\trequest\tresponse\n")
        path = self.write(gate="accept:1.1:s18-accept-no-kit;seams:1.1:edge")
        text = path.read_text().replace(
            "\tfoundation\tgoal\t",
            "\ts18-accept-no-kit\tbusiness no-kit; tests: are a prose word; parts of policy\t")
        path.write_text("# no-kit and tests: are lawful explanatory words\n" + text)
        self.assertEqual(check_forms.check_stage_parts(path)[0], [])

    def test_new_gates_keep_case_table_and_chapter_guards(self):
        self.assertEqual(self.errors(gate="accept:1.1:ordinary;seams:1.1:edge"), [])
        for gate in ("accept:1.1:edge", "seams:1.1:ordinary", "seams:2.1:edge",
                     "accept:1.1:absent", "seams:1.1:edge,edge"):
            with self.subTest(gate=gate):
                self.assertTrue(self.errors(gate=gate))
        (self.lesson / "acceptance/1/seams.tsv").unlink()
        self.assertTrue(self.errors(gate="seams:1.1:*"))

    def test_public_dependency_shape_and_kit_allowlist_guards_remain(self):
        self.assertTrue(self.errors(gate="build", depends="1"))
        self.assertTrue(self.errors(gate="build;build"))
        path = self.write(name="stages.kit.tsv", kit=True)
        path.write_text(path.read_text().replace("door,refusals", "door,unknown"))
        self.assertTrue(check_forms.check_stage_parts(path)[0])
        path = self.write(gate="build")
        path.write_text(path.read_text() + "2\tshort\n")
        self.assertTrue(check_forms.check_stage_parts(path)[0])

    def test_retained_kit_reader_ignores_public_form_legacy_rejection(self):
        self.write(name="stages.kit.tsv", kit=True, gate="vectors:jcs")
        public = self.write(gate="tests:1.1:ordinary")
        self.assertTrue(check_forms.check_stage_parts(public)[0])
        stages, source = gen_tests.read_stages(self.root)
        self.assertEqual(stages, {"jcs": "foundation"})
        self.assertEqual(source.data, (self.lesson / "forms/stages.kit.tsv").read_bytes())


class Phase3ActualSourceControls(unittest.TestCase):
    def test_all_nine_public_forms_are_package_free_and_kit_forms_remain_valid(self):
        public = sorted(ROOT.glob("Platform/*/forms/stages.tsv"))
        self.assertEqual(len(public), 9)
        for path in public:
            with self.subTest(path=path):
                rows = [line.split("\t") for line in path.read_text().splitlines()
                        if line and not line.startswith("#")]
                self.assertFalse({"kit", "parts"} & set(rows[0]))
                for row in rows[1:]:
                    for gate in row[rows[0].index("gate")].split(";"):
                        self.assertFalse(gate.startswith("tests:"), gate)
                        self.assertEqual(check_forms.gate_errors(path.parent.parent, row[1], gate), [], gate)
                self.assertEqual(check_forms.check_stage_parts(path)[0], [])
                kit = path.with_name("stages.kit.tsv")
                self.assertTrue(kit.is_file())
                self.assertEqual(check_forms.check_stage_parts(kit)[0], [])


if __name__ == "__main__":
    unittest.main()
