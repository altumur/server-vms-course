"""ADR-0135 addendum (14): the target registry assembled from the common header and the rows of the lessons."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_registry as tr  # noqa: E402

COURSE = Path(__file__).resolve().parents[3]
HEADER_T = "id\towner\tflags"
HEADER_R = "id\tengine\tacceptance"


class Registry(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / tr.COMMON).mkdir(parents=True)
        for lesson in ("01-store", "02-installer"):
            (self.root / "Platform" / lesson / "forms").mkdir(parents=True)

    def write(self, rel, *lines):
        path = self.root / rel
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def common(self, targets=(), routing=()):
        self.write(tr.COMMON / tr.TARGETS, "# registry", HEADER_T, *targets)
        self.write(tr.COMMON / tr.ROUTING, "# routing", HEADER_R, *routing)

    def lesson(self, name, targets=(), routing=()):
        self.write(Path("Platform") / name / "forms" / tr.TARGETS, HEADER_T, *targets)
        self.write(Path("Platform") / name / "forms" / tr.ROUTING, HEADER_R, *routing)

    def test_rows_only_in_common_are_green(self):
        self.common(["P/01.1/door\t01-store\t[]", "P/02/vectors\t02-installer\t[]"],
                    ["P/01.1/door\trun\t[]", "P/02/vectors\tvector\t[]"])
        targets, routing, errors, stats = tr.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual([r["id"] for _, _, r in targets], ["P/01.1/door", "P/02/vectors"])
        self.assertEqual(stats["registry_lessons_with_rows"], 0)

    def test_rows_moved_into_lessons_assemble_the_same_registry(self):
        self.common(["P/01.1/door\t01-store\t[]", "P/02/vectors\t02-installer\t[]"],
                    ["P/01.1/door\trun\t[]", "P/02/vectors\tvector\t[]"])
        before = tr.assemble(self.root)
        self.common()
        self.lesson("01-store", ["P/01.1/door\t01-store\t[]"], ["P/01.1/door\trun\t[]"])
        self.lesson("02-installer", ["P/02/vectors\t02-installer\t[]"], ["P/02/vectors\tvector\t[]"])
        after = tr.assemble(self.root)
        self.assertEqual(after[2], [])
        self.assertEqual([r for _, _, r in after[0]], [r for _, _, r in before[0]])
        self.assertEqual([r for _, _, r in after[1]], [r for _, _, r in before[1]])
        self.assertEqual(after[3]["registry_lessons_with_rows"], 2)

    def test_both_layouts_at_once_during_the_transition(self):
        self.common(["P/02/vectors\t02-installer\t[]"], ["P/02/vectors\tvector\t[]"])
        self.lesson("01-store", ["P/01.1/door\t01-store\t[]"], ["P/01.1/door\trun\t[]"])
        self.assertEqual(tr.assemble(self.root)[2], [])

    def test_one_id_in_two_places_is_an_error(self):
        self.common(["P/01.1/door\t01-store\t[]"], ["P/01.1/door\trun\t[]"])
        self.lesson("01-store", ["P/01.1/door\t01-store\t[]"], ["P/01.1/door\trun\t[]"])
        messages = [m for _, m in tr.assemble(self.root)[2]]
        self.assertTrue(any("already at" in m and tr.TARGETS in m for m in messages), messages)
        self.assertTrue(any("already at" in m and tr.ROUTING in m for m in messages), messages)

    def test_a_lessons_row_owned_by_another_lesson_is_an_error(self):
        self.common()
        self.lesson("01-store", ["P/02/vectors\t02-installer\t[]"], ["P/02/vectors\tvector\t[]"])
        self.assertTrue(any("belong to 01-store" in m for _, m in tr.assemble(self.root)[2]))

    def test_a_lesson_file_with_another_header_is_an_error(self):
        self.common()
        self.write(Path("Platform/01-store/forms") / tr.TARGETS, "owner\tid\tflags", "01-store\tP/01.1/door\t[]")
        self.write(Path("Platform/01-store/forms") / tr.ROUTING, HEADER_R, "P/01.1/door\trun\t[]")
        self.assertTrue(any("header differs" in m for _, m in tr.assemble(self.root)[2]))

    def test_target_and_routing_in_different_places_is_an_error(self):
        self.common(["P/01.1/door\t01-store\t[]"], [])
        self.write(Path("Platform/01-store/forms") / tr.ROUTING, HEADER_R, "P/01.1/door\trun\t[]")
        self.assertTrue(any("both belong to one place" in m for _, m in tr.assemble(self.root)[2]))

    def test_a_target_without_routing_and_routing_without_target(self):
        self.common(["P/01.1/door\t01-store\t[]"], ["P/01.1/extra\trun\t[]"])
        messages = [m for _, m in tr.assemble(self.root)[2]]
        self.assertTrue(any("has no row in" in m for m in messages), messages)
        self.assertTrue(any("has no target in" in m for m in messages), messages)

    def test_the_course_registry_is_green(self):
        _targets, _routing, errors, stats = tr.assemble(COURSE)
        self.assertEqual(errors, [])
        self.assertGreater(stats["registry_targets"], 0)


if __name__ == "__main__":
    unittest.main()
