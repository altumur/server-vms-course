"""ADR-0135 addendum (14): the export filters M and J assembled from the common filters and the lists of the lessons."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_lists as el  # noqa: E402

COURSE = Path(__file__).resolve().parents[3]
LESSON = "01-store"
FILES = ["README.md", "forms/targets.tsv", "forms/targets.routing.tsv", "forms/export.json", "spec/01.1-store.norms.md"]
M = {"README.md": "model_and_judge", "forms/targets.tsv": "model_and_judge", "forms/targets.routing.tsv": "judge_only",
     "forms/export.json": "judge_only", "spec/01.1-store.norms.md": "model_and_judge"}
J = {"README.md": "exclude", "forms/targets.tsv": "include", "forms/targets.routing.tsv": "include",
     "forms/export.json": "exclude", "spec/01.1-store.norms.md": "exclude"}


def rec(path, disposition):
    return {"path": path, "disposition": disposition, "basis": "test"}


class ExportLists(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        common = [rec("Platform/common/README.md", "model_and_judge")]
        self.write("Platform/common/README.md", "common")
        self.dump(el.COMMON["model"], {"version": 1, "files": common, "own_export_markers": []})
        self.dump(el.COMMON["judge"], {"version": 1, "files": [rec("Platform/common/README.md", "include")]})
        for name in FILES:
            if name != "forms/export.json":
                self.write(f"Platform/{LESSON}/{name}", "x")
        self.lesson_list(M, J)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def dump(self, rel, obj):
        self.write(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    def lesson_list(self, model, judge, extra=None):
        def records(table):
            return sorted((rec(f"Platform/{LESSON}/{k}", v) for k, v in table.items()), key=lambda r: r["path"].encode())
        obj = {"version": 1, "model": records(model), "judge": records(judge)}
        if extra:
            obj.update(extra)
        self.dump(f"Platform/{LESSON}/forms/export.json", obj)

    def test_assembly_of_common_and_lesson_records(self):
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(len(filters["model"]), 1 + len(FILES))
        self.assertEqual({r["path"] for r in filters["model"]}, {r["path"] for r in filters["judge"]})
        self.assertEqual(stats["export_lessons_with_lists"], 1)

    def test_routing_of_the_judge_in_m_is_an_error(self):
        self.lesson_list(dict(M, **{"forms/targets.routing.tsv": "model_and_judge"}), J)
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("targets.routing.tsv is model_and_judge" in m and "reach the model" in m for m in errors), errors)

    def test_registry_table_kept_from_m_is_an_error(self):
        self.lesson_list(dict(M, **{"forms/targets.tsv": "judge_only"}), J)
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("forms/targets.tsv is judge_only, the rule gives model_and_judge" in m for m in errors), errors)

    def test_a_lesson_file_without_a_record_is_an_error(self):
        model = dict(M)
        del model["spec/01.1-store.norms.md"]
        self.lesson_list(model, J)
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("spec/01.1-store.norms.md of the lesson has no record" in m for m in errors), errors)
        self.assertTrue(any("has a record in J and none in M" in m for m in errors), errors)

    def test_a_record_of_a_foreign_file_and_a_duplicate_are_errors(self):
        self.lesson_list(dict(M, **{"spec/ghost.md": "model_and_judge"}), dict(J, **{"spec/ghost.md": "exclude"}))
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("spec/ghost.md is not a file of the lesson" in m for m in errors), errors)
        self.dump(el.COMMON["model"], {"version": 1, "files": [rec("Platform/common/README.md", "model_and_judge"),
                                                               rec(f"Platform/{LESSON}/README.md", "model_and_judge")]})
        self.lesson_list(M, J)
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("README.md has a record here and in" in m for m in errors), errors)

    def test_form_of_a_list(self):
        self.lesson_list(M, J, extra={"version": 2})
        self.assertTrue(any("exactly version (1)" in m for _, m in el.assemble(self.root)[1]))
        self.lesson_list(M, J)
        path = self.root / f"Platform/{LESSON}/forms/export.json"
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj["model"].reverse()
        self.dump(f"Platform/{LESSON}/forms/export.json", obj)
        self.assertTrue(any("not sorted by path" in m for _, m in el.assemble(self.root)[1]))

    def test_unmoved_lesson_files_are_counted_not_errors(self):
        self.write("Platform/02-installer/README.md", "x")
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["export_unlisted"], 1)

    def test_live_course(self):
        filters, errors, stats = el.assemble(COURSE)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["export_lessons_with_lists"], 2)
        self.assertEqual(len(filters["model"]), len(filters["judge"]))


if __name__ == "__main__":
    unittest.main()
