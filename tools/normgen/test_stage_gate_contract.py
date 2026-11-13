"""ADR-0126(11): independent public/retained stage gate set and grammar controls."""
import csv
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import check_forms

SELECTOR = re.compile(r"(tests|accept|seams):([0-9]+(?:\.[0-9]+)?):([^:;\s]+)(:seams)?")
PUBLIC_KINDS = {"build", "vectors", "accept", "seams", "verdicts", "puts"}


def stage_rows(path):
    return list(csv.DictReader(
        (line for line in path.read_text().splitlines() if line and not line.startswith("#")),
        delimiter="\t"))


def scenario_selection(lesson, gate, *, legacy):
    """Independently expand only named table selections, never scenario request/expect cells."""
    chosen, other = set(), set()
    for token in gate.split(";"):
        match = SELECTOR.fullmatch(token)
        if not match:
            other.add(token)
            continue
        kind, chapter, names, tail = match.groups()
        if kind == "tests":
            if not legacy:
                raise ValueError("tests: in public gate")
            kind = "seams" if tail else "accept"
        elif tail:
            raise ValueError("seams suffix on nonlegacy gate")
        owner = int(lesson.name.split("-")[0])
        if int(chapter.split(".")[0]) != owner:
            raise ValueError("foreign chapter")
        folder = lesson / "acceptance"
        if "." in chapter:
            folder /= chapter.split(".")[1]
        path = folder / ("seams.tsv" if kind == "seams" else "scenarios.tsv")
        known = {line.split("\t")[0] for line in path.read_text().splitlines()
                 if line and not line.startswith("#")}
        requested = known if names == "*" else set(names.split(","))
        if names != "*" and len(names.split(",")) != len(requested):
            raise ValueError("duplicate scenario")
        if not requested <= known:
            raise ValueError(f"unknown names in {path}: {sorted(requested - known)}")
        chosen.update((kind, chapter, name) for name in requested)
    return chosen, other


def compare_stage_sets(public):
    """Retain native accept/seams and all non-scenario gates as well as converted tests."""
    old = stage_rows(public.with_name("stages.kit.tsv"))
    new = stage_rows(public)
    if [(r["n"], r["stage"]) for r in old] != [(r["n"], r["stage"]) for r in new]:
        raise ValueError("stage identity/order changed")
    result = []
    for before, after in zip(old, new):
        if before["depends"] != after["depends"]:
            raise ValueError("stage dependency changed")
        left = scenario_selection(public.parent.parent, before["gate"], legacy=True)
        right = scenario_selection(public.parent.parent, after["gate"], legacy=False)
        if left != right:
            raise ValueError(f"gate set differs at {after['stage']}")
        result.append((after["stage"], len(right[0])))
    return result


class PublishedStageGateSets(unittest.TestCase):
    def test_all_nine_current_public_and_retained_forms_select_valid_gates(self):
        # Public plans evolve independently of retained generator inputs.
        # Exact conversion preservation is checked by StageGateContractControls.
        public = sorted(ROOT.glob("Platform/*/forms/stages.tsv"))
        self.assertEqual(len(public), 9)
        total = 0
        for path in public:
            with self.subTest(path=path):
                total += len(stage_rows(path))
                for form, legacy in ((path, False), (path.with_name("stages.kit.tsv"), True)):
                    self.assertEqual(check_forms.check_stage_parts(form)[0], [])
                    for row in stage_rows(form):
                        scenario_selection(form.parent.parent, row["gate"], legacy=legacy)
        self.assertEqual(total, 91)


class StageGateContractControls(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="stage-contract-")
        self.addCleanup(tmp.cleanup)
        self.lesson = Path(tmp.name) / "Platform/01-store"
        (self.lesson / "forms").mkdir(parents=True)
        chapter = self.lesson / "acceptance/1"
        chapter.mkdir(parents=True)
        (chapter / "scenarios.tsv").write_text("# scenario\tstep\trequest\texpect\nordinary\t1\tx\ty\nsecond\t1\tx\ty\n")
        (chapter / "seams.tsv").write_text("# scenario\tstep\trequest\texpect\nedge\t1\tx\ty\n")
        (self.lesson / "forms/write-checks.probes.tsv").write_text("# declared probe carrier\n")

    def write(self, name, gate, *, goal="ordinary goal", extra=None):
        head = ["n", "stage", "goal", "norms", "gate", "weight", "depends", "when"]
        row = ["1", "core", goal, "P/01.1", gate, "1", "-", ""]
        if name == "stages.kit.tsv":
            head += ["kit", "parts"]
            row += ["-", "-"]
        if extra:
            head += [extra]
            row += ["-"]
        path = self.lesson / "forms" / name
        path.write_text("\t".join(head) + "\n" + "\t".join(row) + "\n")
        return path

    def test_explicit_early_list_matches_frozen_star_and_wrong_list_fails(self):
        self.write("stages.kit.tsv", "tests:1.1:*;tests:1.1:edge:seams")
        public = self.write("stages.tsv", "accept:1.1:ordinary,second;seams:1.1:edge")
        self.assertEqual(compare_stage_sets(public), [("core", 3)])
        self.write("stages.tsv", "accept:1.1:ordinary;seams:1.1:edge")
        with self.assertRaisesRegex(ValueError, "gate set differs"):
            compare_stage_sets(public)

    def test_native_accept_star_is_preserved_not_reclassified_as_converted_tests(self):
        self.write("stages.kit.tsv", "accept:1.1:*;tests:1.1:edge:seams")
        public = self.write("stages.tsv", "accept:1.1:*;seams:1.1:edge")
        self.assertEqual(compare_stage_sets(public), [("core", 3)])

    def test_membership_is_kind_and_chapter_specific(self):
        for gate in ("accept:1.1:edge", "seams:1.1:ordinary", "accept:2.1:ordinary",
                     "seams:1.2:edge", "accept:1.1:missing"):
            with self.subTest(gate=gate):
                path = self.write("stages.tsv", gate)
                self.assertTrue(check_forms.check_stage_parts(path)[0])
        self.assertEqual(check_forms.check_stage_parts(
            self.write("stages.tsv", "accept:1.1:ordinary;seams:1.1:edge"))[0], [])

    def test_closed_public_kind_grammar_and_short_tests_refuse(self):
        for gate in ("tests:core", "checks:core", "own_tests", "shell:ok", "build:extra",
                     "accept:1.1:ordinary:seams", "seams:1.1:edge:seams", "vectors:",
                     "tests:1.1:ordinary", "tests:1.1:edge:seams"):
            with self.subTest(gate=gate):
                self.assertTrue(check_forms.check_stage_parts(self.write("stages.tsv", gate))[0])
        for gate in ("build", "vectors:write-checks", "accept:1.1:ordinary", "seams:1.1:edge"):
            with self.subTest(gate=gate):
                self.assertEqual(check_forms.check_stage_parts(self.write("stages.tsv", gate))[0], [])

    def test_kit_legacy_is_not_subject_to_public_ban(self):
        kit = self.write("stages.kit.tsv", "tests:1.1:ordinary;tests:1.1:edge:seams")
        self.assertEqual(check_forms.check_stage_parts(kit)[0], [])
        for column in ("kit", "parts"):
            with self.subTest(column=column):
                self.assertTrue(check_forms.check_stage_parts(
                    self.write("stages.tsv", "build", extra=column))[0])

    def test_non_scenario_gates_and_stage_identity_cannot_silently_disappear(self):
        self.write("stages.kit.tsv", "vectors:write-checks;tests:1.1:ordinary")
        public = self.write("stages.tsv", "accept:1.1:ordinary")
        with self.assertRaisesRegex(ValueError, "gate set differs"):
            compare_stage_sets(public)
        self.write("stages.tsv", "vectors:write-checks;accept:1.1:ordinary")
        public.write_text(public.read_text().replace("\tcore\t", "\tother\t"))
        with self.assertRaisesRegex(ValueError, "identity/order"):
            compare_stage_sets(public)


if __name__ == "__main__":
    unittest.main()
