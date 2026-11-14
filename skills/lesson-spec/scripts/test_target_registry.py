"""ADR-0135 addendum (14): the target registry assembled from the common header and the rows of the lessons."""
import json
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


class Execution(Registry):
    """The optional execution cell is source data, never an executed stand."""
    ROUTING_COLUMNS = "id engine acceptance scenarios tables parts body role free rights".split()
    COMMAND = {"owner": "04-controller", "section": "stand", "key": "pass_print"}

    def setUp(self):
        super().setUp()
        shutil.copyfile(COURSE / tr.COMMON / tr.EXECUTION_SCHEMA, self.root / tr.COMMON / tr.EXECUTION_SCHEMA)
        self.scenarios = self.root / "Platform/01-store/acceptance/1/scenarios.tsv"
        self.scenarios.parent.mkdir(parents=True)
        self.scenarios.write_text("scenario\tstep\trequest\texpect\n"
                                  "01-create\t1\tPOST /rows {}\t201\n"
                                  "02-read\t1\tGET /rows\t200\n"
                                  "03-clean\t1\tGET /rows\t200\n")

    def action(self, **changes):
        result = {"id": "pass-after-create", "after": "01-create", "before": "02-read",
                  "action": "controller-pass", "command": self.COMMAND.copy(), "sub": "testsub", "timeout_s": 15}
        result.update(changes)
        return result

    def registry(self, execution=None, *, raw=None, omit=False, columns=None, selector="all", engine="run"):
        common_header = self.ROUTING_COLUMNS + ["execution"]
        columns = columns or (self.ROUTING_COLUMNS if omit else common_header)
        self.write(tr.COMMON / tr.TARGETS, "id\towner\tflags\tstand_commands")
        self.write(tr.COMMON / tr.ROUTING, "\t".join(common_header))
        self.write("Platform/01-store/forms/targets.tsv", "id\towner\tflags\tstand_commands",
                   "scope/test\t01-store\t[]\t" + json.dumps([self.COMMAND]))
        row = dict(zip(self.ROUTING_COLUMNS,
                       ["scope/test", engine, '["Platform/01-store/acceptance/1"]', selector,
                        "[]", "[]", "whole", "acc", "[]", "none"]))
        row["execution"] = raw if raw is not None else json.dumps(execution or {}, separators=(",", ":"))
        row["future"] = "ignored"
        self.write("Platform/01-store/forms/targets.routing.tsv", "\t".join(columns),
                   "\t".join(row[name] for name in columns))
        return tr.assemble(self.root)

    def messages(self, *args, **kwargs):
        return [message for _, message in self.registry(*args, **kwargs)[2]]

    def test_omitted_execution_preserves_existing_cells_without_requiring_a_stand(self):
        self.scenarios.unlink()
        targets, routing, errors, stats = self.registry(omit=True)
        self.assertEqual(errors, [])
        self.assertEqual(routing[0][2]["execution"], "{}")
        self.assertEqual(stats["registry_execution_rows"], 0)
        self.assertEqual(routing[0][2]["scenarios"], "all")

    def test_routing_columns_by_name_with_ignored_unknown_column(self):
        columns = ["execution", "future"] + list(reversed(self.ROUTING_COLUMNS))
        self.assertEqual(self.messages({"stand": "shared"}, columns=columns), [])

    def test_existing_course_cells_of_lessons_one_through_five_are_unchanged(self):
        _targets, routing, errors, _stats = tr.assemble(COURSE)
        self.assertEqual(errors, [])
        assembled = {row["id"]: row for _, _, row in routing}
        for lesson in tr.lesson_dirs(COURSE):
            if not "01" <= lesson.name[:2] <= "05":
                continue
            path = lesson / "forms" / tr.ROUTING
            if not path.exists():
                continue
            header, rows = tr.read_table(path)
            for _, cells in rows:
                original = dict(zip(header, cells))
                actual = assembled[original["id"]].copy()
                self.assertEqual(actual.pop("execution"), "{}")
                self.assertEqual(actual, original)

    def test_console_one_partition_with_clean_exceptions_and_no_loss(self):
        path = COURSE / "Platform/06-console/acceptance/1/scenarios.tsv"
        shared = tr.selected_scenarios(path, "range:1-14", ["03-update", "14-if-match"])
        fresh = tr.selected_scenarios(path, "all", shared)
        self.assertEqual(len(shared), 12)
        self.assertEqual(fresh[:2], ["03-update", "14-if-match"])
        self.assertEqual(len(fresh), 34)
        all_ids = tr.selected_scenarios(path, "all")
        self.assertEqual(set(shared) & set(fresh), set())
        self.assertEqual(set(shared) | set(fresh), set(all_ids))

    def test_console_six_partition_and_exact_boundary(self):
        source = COURSE / "Platform/06-console/acceptance/6/scenarios.tsv"
        self.scenarios.write_bytes(source.read_bytes())
        shared = tr.selected_scenarios(self.scenarios, "range:1-7")
        fresh = tr.selected_scenarios(self.scenarios, "range:8-17")
        self.assertEqual((len(shared), len(fresh)), (7, 10))
        self.assertEqual(shared + fresh, tr.selected_scenarios(source, "all"))
        action = self.action(after="01-unplaced", before="02-unplaceable")
        self.assertEqual(self.messages({"stand": "shared", "between": [action]}, selector="range:1-7"), [])

    def test_first_step_selectors_use_decoded_requests_with_either_header_form(self):
        for header in ("scenario\tstep\trequest\texpect", "# scenario\tstep\trequest\texpect"):
            with self.subTest(header=header):
                self.scenarios.write_text('# cell-json: request\n' + header + '\n \t \n'
                                          'a\t1\t"@start resource"\tok\n'
                                          'b\t1\t"GET /rows"\t200\n')
                self.assertEqual(tr.selected_scenarios(self.scenarios, "first-step:@start"), ["a"])
                self.assertEqual(tr.selected_scenarios(self.scenarios, "not-first-step:@start"), ["b"])
        self.scenarios.write_text('scenario\tstep\trequest\texpect\n \t \na\t1\tGET /rows\t200\n')
        self.assertEqual(tr.selected_scenarios(self.scenarios, "all"), ["a"])

    def test_empty_selection_has_no_boundary(self):
        self.assertEqual(self.messages({"stand": "shared", "exclude": ["01-create", "02-read", "03-clean"]}), [])

    def test_bad_json_types_unknown_fields_and_noninteger_tokens_are_rejected(self):
        for raw in ("", "null", "[]", '{"stand":"shared","stand":"scenario"}',
                    '{"exclude":[3]}', '{"exclude":["03-clean","03-clean"]}',
                    '{"stand":"shared","unknown":0}', '{"between":[NaN]}'):
            with self.subTest(raw=raw):
                self.assertTrue(self.messages(raw=raw))
        for value in (True, "15", 0, -1, 15.0):
            with self.subTest(timeout=value):
                self.assertTrue(self.messages({"stand": "shared", "between": [self.action(timeout_s=value)]}))

    def test_bad_selection_boundaries_commands_and_order_are_rejected(self):
        valid = {"stand": "shared", "between": [self.action()]}
        bad = [
            {"exclude": ["absent"]},
            {"stand": "scenario", "between": [self.action()]},
            {"between": [self.action()]},
            {"stand": "shared", "exclude": ["02-read"], "between": [self.action()]},
            {"stand": "shared", "between": [self.action(after="02-read", before="01-create")]},
            {"stand": "shared", "between": [self.action(before="03-clean")]},
            {"stand": "shared", "between": [self.action(before="absent")]},
            {"stand": "shared", "between": [self.action(), self.action(id="duplicate-boundary")]},
            {"stand": "shared", "between": [self.action(), self.action(after="02-read", before="03-clean")]},
            {"stand": "shared", "between": [self.action(id="later", after="02-read", before="03-clean"), self.action()]},
            {"stand": "shared", "between": [self.action(command={**self.COMMAND, "key": "undeclared"})]},
        ]
        self.assertEqual(self.messages(valid), [])
        for execution in bad:
            with self.subTest(execution=execution):
                self.assertTrue(self.messages(execution))
        self.assertTrue(self.messages({"exclude": ["03-clean"]}, selector="range:1-2"))
        self.assertTrue(self.messages({"stand": "shared"}, selector="range:3-1"))
        self.assertTrue(self.messages({"stand": "shared"}, engine="vector"))

    def test_malformed_schema_is_diagnostic_not_a_checker_exception(self):
        (self.root / tr.COMMON / tr.EXECUTION_SCHEMA).write_text('{"type":"not-a-schema-type"}')
        self.assertTrue(any("invalid execution schema" in message for message in self.messages()))


if __name__ == "__main__":
    unittest.main()
