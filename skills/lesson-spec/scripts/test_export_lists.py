"""ADR-0135 addendum (14): the export filters M and J assembled from the common filters and the lists of the lessons."""
import json
import shutil
import subprocess
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


def cover(root):
    """Fixture helper for the synthetic Platform trees of other tests (OBSH.58): writes the common filters M and J so
    that they classify exactly the roster of the tree (its files under Platform/ and the marker), each file once, except
    the files of a lesson with its own forms/export.json. The forms of a lesson by the common rule, the marker in both,
    every other file judge_only and exclude (a fixture's file never reaches the model). Returns the root."""
    root = Path(root)
    for rel in el.COMMON.values():
        if not (root / rel).is_file():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("{}\n", encoding="utf-8")
    roster, _ = el.platform_roster(root)
    moved = {d for d in el.lesson_dirs(root) if (root / "Platform" / d / el.LIST).is_file()}
    tables = {"model": {el.MARKER: "model_and_judge"}, "judge": {el.MARKER: "include"}}
    for path in roster:
        parts = path.split("/")
        if parts[1] in moved:
            continue
        rule = el.RULES.get("/".join(parts[2:])) if el.LESSON_DIR.match(parts[1]) else None
        for side, default in (("model", "judge_only"), ("judge", "exclude")):
            tables[side][path] = rule[side] if rule else default
    for side, rel in el.COMMON.items():
        files = sorted((rec(k, v) for k, v in tables[side].items()), key=lambda r: r["path"].encode())
        body = {"version": 1, "files": files, **({"own_export_markers": []} if side == "model" else {})}
        (root / rel).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return root


class Tree(unittest.TestCase):
    """A Platform tree without .git (a source archive): the roster is the files on disk."""

    COMMON_M = {el.MARKER: "model_and_judge", "Platform/common/README.md": "model_and_judge",
                el.COMMON["judge"].as_posix(): "judge_only", el.COMMON["model"].as_posix(): "judge_only"}
    COMMON_J = {el.MARKER: "include", "Platform/common/README.md": "include",
                el.COMMON["judge"].as_posix(): "exclude", el.COMMON["model"].as_posix(): "exclude"}

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.write("Platform/common/README.md", "common")
        self.common()
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

    def common(self, model=None, judge=None):
        """The common filters: the records of the common files of the fixture, and `model`, `judge` over them."""
        def records(table):
            return sorted((rec(k, v) for k, v in table.items()), key=lambda r: r["path"].encode())
        self.dump(el.COMMON["model"], {"version": 1, "files": records({**self.COMMON_M, **(model or {})}),
                                       "own_export_markers": []})
        self.dump(el.COMMON["judge"], {"version": 1, "files": records({**self.COMMON_J, **(judge or {})})})


class ExportLists(Tree):
    def test_assembly_of_common_and_lesson_records(self):
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(len(filters["model"]), len(self.COMMON_M) + len(FILES))
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
        self.assertEqual([m for m in errors if "01.1-store.norms.md" in m],
                         [f"model: the file Platform/{LESSON}/spec/01.1-store.norms.md of the lesson has no record"])

    def test_a_record_of_a_foreign_file_and_a_duplicate_are_errors(self):
        self.lesson_list(dict(M, **{"spec/ghost.md": "model_and_judge"}), dict(J, **{"spec/ghost.md": "exclude"}))
        errors = [m for _, m in el.assemble(self.root)[1]]
        self.assertTrue(any("spec/ghost.md is not a file of the lesson" in m for m in errors), errors)
        self.common(model={f"Platform/{LESSON}/README.md": "model_and_judge"})
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

    def test_unmoved_lesson_file_without_a_record_is_an_error(self):
        self.write("Platform/02-installer/README.md", "x")
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(stats["export_unlisted"], 1)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all("Platform/02-installer/README.md of Platform has no record" in m for _, m in errors))
        self.common({"Platform/02-installer/README.md": "judge_only"}, {"Platform/02-installer/README.md": "exclude"})
        self.assertEqual(el.assemble(self.root)[1], [])

    def test_cover_gives_a_fixture_its_full_filters(self):
        self.write("Platform/02-installer/forms/targets.routing.tsv", "x")
        self.write("Platform/ru/README.md", "x")
        self.assertTrue(el.assemble(self.root)[1])
        cover(self.root)
        filters, errors, _ = el.assemble(self.root)
        self.assertEqual(errors, [])
        by = {r["path"]: r["disposition"] for r in filters["model"]}
        self.assertEqual(by["Platform/02-installer/forms/targets.routing.tsv"], "judge_only")
        self.assertEqual(by[el.MARKER], "model_and_judge")

    def test_live_course(self):
        filters, errors, stats = el.assemble(COURSE)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["export_lessons_with_lists"], 2)
        self.assertEqual(len(filters["model"]), len(filters["judge"]))


Q_SOURCE, Q_RU = "qualification/README.md", "ru/qualification/README.md"


class QualificationInput(Tree):
    """The third input Q (ADR-0130 addendum (20) item 1): Q files outside M, their translations outside the exports,
    the filter Platform/common/qualification-input-filter.json by the form of the judge filter, file by file."""

    def with_q(self, model=None, judge=None, files=None, q_in_m="judge_only"):
        """The lesson with a Q file and its translation in its list; the filter of Q with `files` (None — the Q file
        and a common file), classified in the common filters as `q_in_m` in M and exclude in J; returns the errors of
        the assembly."""
        self.write(f"Platform/{LESSON}/{Q_SOURCE}", "procedures")
        self.write(f"Platform/{LESSON}/{Q_RU}", "процедуры")
        self.lesson_list({**M, Q_SOURCE: "judge_only", Q_RU: "judge_only", **(model or {})},
                         {**J, Q_SOURCE: "exclude", Q_RU: "exclude", **(judge or {})})
        if files is None:
            files = [rec(f"Platform/{LESSON}/{Q_SOURCE}", "include"), rec("Platform/common/README.md", "include")]
        if files is False:
            (self.root / el.QUALIFICATION).unlink(missing_ok=True)
            self.common()
        else:
            self.dump(el.QUALIFICATION, {"version": 1, "files": files})
            self.common({el.QUALIFICATION.as_posix(): q_in_m}, {el.QUALIFICATION.as_posix(): "exclude"})
        return [m for _, m in el.assemble(self.root)[1]]

    def assert_one(self, errors, words):
        self.assertTrue(any(words in m for m in errors), errors)

    def test_without_q_files_and_filter_as_before(self):
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["qualification_files"], 0)
        self.assertNotIn("qualification_records", stats)

    def test_accepted_q_passes(self):
        self.assertEqual(self.with_q(), [])
        stats = el.assemble(self.root)[2]
        self.assertEqual((stats["qualification_files"], stats["qualification_records"]), (1, 2))
        self.assertEqual(el.qualification_files(self.root), {f"Platform/{LESSON}/{Q_SOURCE}", f"Platform/{LESSON}/{Q_RU}"})

    def test_q_file_in_m_is_an_error(self):
        errors = self.with_q(model={Q_SOURCE: "model_and_judge"})
        self.assert_one(errors, f"{Q_SOURCE} is model_and_judge — a file of the input Q")
        errors = self.with_q(model={Q_RU: "model_and_judge"})
        self.assert_one(errors, f"{Q_RU} is model_and_judge — a file of the input Q")

    def test_q_filter_in_m_and_translation_of_q_in_j_are_errors(self):
        self.assert_one(self.with_q(q_in_m="model_and_judge"),
                        "qualification-input-filter.json is model_and_judge — the filter of Q is outside M")
        self.assert_one(self.with_q(judge={Q_RU: "include"}), "a Russian mirror of Q is outside the exports")

    def test_filter_with_a_missing_path_a_mask_and_a_mirror(self):
        errors = self.with_q(files=[rec(f"Platform/{LESSON}/{Q_SOURCE}", "include"),
                                    rec("Platform/common/ghost.md", "include")])
        self.assert_one(errors, "files: Platform/common/ghost.md is not a file of the tree")
        errors = self.with_q(files=[rec(f"Platform/{LESSON}/q*/README.md", "include"),
                                    rec(f"Platform/{LESSON}/{Q_SOURCE}", "include")])
        self.assert_one(errors, "q*/README.md is not a file of the tree")
        errors = self.with_q(files=[rec(f"Platform/{LESSON}/{Q_SOURCE}", "include"),
                                    rec(f"Platform/{LESSON}/{Q_RU}", "include")])
        self.assert_one(errors, f"{Q_RU} is a Russian mirror — the input Q is English only")
        errors = self.with_q(files=[rec(f"Platform/{LESSON}/{Q_SOURCE}", "include"),
                                    rec(el.COMMON["judge"].as_posix(), "include")])
        self.assert_one(errors, "judge-input-filter.json is a filter of the export")

    def test_filter_without_a_q_file_and_q_without_filter(self):
        self.assert_one(self.with_q(files=[rec("Platform/common/README.md", "include")]),
                        f"the Q file Platform/{LESSON}/{Q_SOURCE} has no record")
        self.assert_one(self.with_q(files=False), "the filter of the input Q is missing, and the tree has Q files")

    def test_form_of_the_filter(self):
        q = rec(f"Platform/{LESSON}/{Q_SOURCE}", "include")
        self.assert_one(self.with_q(files=[rec("Platform/common/README.md", "include"), q]), "not sorted by path")
        self.assert_one(self.with_q(files=[q, rec("Platform/common/README.md", "exclude")]),
                        "disposition exclude is not one of include")
        self.assert_one(self.with_q(files=[q, q]), f"{Q_SOURCE} is named more than once")
        self.assert_one(self.with_q(files=[{"path": q["path"], "disposition": "include"}]),
                        "exactly the fields path, disposition, basis")
        self.with_q()
        self.dump(el.QUALIFICATION, {"version": 2, "files": [q]})
        self.assert_one([m for _, m in el.assemble(self.root)[1]], "exactly version (1) and files")


class Archive(Tree):
    """OBSH.58: the assembled M and J classify exactly the roster of the export pair operator — every entry under
    Platform/ of the source tree and the marker Platform/COURSE_COMMIT (b7_export_pair._source, _classification).
    Here the tree has no .git (a full source archive, judge OBSH.58 С1): the roster is the files on disk."""

    def add(self, *paths):
        """In a tree without git a file is in the roster once it is on disk."""

    def errors(self):
        self.add("Platform")
        return [m for _, m in el.assemble(self.root)[1]]

    def roster(self):
        return el.platform_roster(self.root)

    def test_full_roster_passes(self):
        filters, errors, stats = el.assemble(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["export_roster_files"], 3 + len(FILES))  # README and the two filters of common, the lesson
        roster, _ = self.roster()
        self.assertEqual({r["path"] for r in filters["model"]}, set(roster) | {el.MARKER})
        self.assertEqual({r["path"] for r in filters["judge"]}, set(roster) | {el.MARKER})

    def test_common_file_without_a_record_in_one_filter(self):
        """aba38d58b: qualification-input-filter.json in neither or one of the filters passed check_spec."""
        q = el.QUALIFICATION.as_posix()
        self.dump(el.QUALIFICATION, {"version": 1, "files": [rec("Platform/common/README.md", "include")]})
        self.common({q: "judge_only"})
        source = self.roster()[1]
        self.assertEqual(self.errors(), [f"judge: the file {q} of Platform has no record in "
                                         f"{el.COMMON['judge'].as_posix()} — the export operator refuses a filter that "
                                         "does not cover the exact roster"])
        self.assertEqual(source, "git index" if isinstance(self, Git) else "files")

    def test_common_file_without_a_record_in_both_filters(self):
        q = el.QUALIFICATION.as_posix()
        self.dump(el.QUALIFICATION, {"version": 1, "files": [rec("Platform/common/README.md", "include")]})
        errors = self.errors()
        self.assertEqual(len(errors), 2, errors)
        for side in ("model", "judge"):
            self.assertTrue(any(m.startswith(f"{side}: the file {q} of Platform has no record in "
                                             f"{el.COMMON[side].as_posix()}") for m in errors), errors)

    def test_record_without_a_file_is_an_error(self):
        self.common({"Platform/common/ghost.md": "model_and_judge"}, {"Platform/common/ghost.md": "include"})
        errors = self.errors()
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all("Platform/common/ghost.md has a record and is no file of Platform" in m for m in errors))

    def test_without_the_marker_record(self):
        self.dump(el.COMMON["model"], {"version": 1, "own_export_markers": [], "files": sorted(
            (rec(k, v) for k, v in self.COMMON_M.items() if k != el.MARKER), key=lambda r: r["path"].encode())})
        self.assertEqual(self.errors(), [f"model: the file {el.MARKER} of Platform has no record in "
                                         f"{el.COMMON['model'].as_posix()} — the export operator refuses a filter "
                                         "that does not cover the exact roster"])

    def test_marker_in_the_tree_and_link_are_errors(self):
        self.write(el.MARKER, "abc\n")
        self.assertTrue(any(f"{el.MARKER} is a file of the tree" in m for m in self.errors()))
        (self.root / el.MARKER).unlink()
        if isinstance(self, Git):
            subprocess.run(["git", "-C", str(self.root), "rm", "-q", "--cached", "--", el.MARKER], check=True)
        (self.root / "Platform/common/link.md").symlink_to("README.md")
        self.common({"Platform/common/link.md": "model_and_judge"}, {"Platform/common/link.md": "include"})
        self.assertEqual([m for m in self.errors() if "link.md" in m],
                         [f"Platform/common/link.md is an entry of mode 120000 ({self.roster()[1]}) — the export "
                          "operator takes only regular files (100644, 100755)"])

    def test_unmoved_lesson_file_is_an_error(self):
        self.write("Platform/02-installer/README.md", "x")
        errors = self.errors()
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all("Platform/02-installer/README.md of Platform has no record" in m for m in errors))

    def test_lesson_with_list_reported_once(self):
        self.write(f"Platform/{LESSON}/spec/extra.md", "x")
        errors = self.errors()
        self.assertTrue(errors)
        self.assertFalse(any("of Platform has no record" in m for m in errors), errors)


class Git(Archive):
    """The same in a git tree: the roster is git's index (the committed tree of C is what is added)."""

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.add("Platform")

    def add(self, *paths):
        subprocess.run(["git", "-C", str(self.root), "add", "--", *paths], check=True, capture_output=True)

    def test_untracked_file_is_outside_the_roster(self):
        self.write("Platform/common/draft.md", "not added")
        self.assertEqual([m for _, m in el.assemble(self.root)[1]], [])
        self.add("Platform/common/draft.md")
        self.assertEqual(len([m for _, m in el.assemble(self.root)[1]]), 2)

    def test_unreadable_index_is_an_error(self):
        (self.root / ".git/index").write_bytes(b"broken")
        self.assertTrue(any("git's index is unreadable" in m for _, m in el.assemble(self.root)[1]))


if __name__ == "__main__":
    unittest.main()
