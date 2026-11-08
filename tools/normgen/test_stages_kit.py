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

    def test_legacy_public_and_retained_kit_forms_remain_admitted(self):
        gate = "tests:1.1:ordinary;tests:1.1:edge:seams;accept:1.1:ordinary"
        self.assertEqual(self.errors(kit=True, gate=gate), [])
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
        path = self.write(kit=True)
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


if __name__ == "__main__":
    unittest.main()
