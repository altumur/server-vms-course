"""The rows of code-rules.tsv of a lesson by the dictionary of kinds, and the shared code modules of
Platform/common/modules.md (ADR-0133 addendum (115); OBSH.69): check_forms.check_code_rules,
check_forms.module_consumer_errors, the lessons of the narrow M (m_form.M_NARROW)."""
import json
import re
import tempfile
import unittest
from pathlib import Path

import check_forms
import form_refs
import m_form

COURSE = Path(__file__).resolve().parents[3]
HEAD = "id\tkind\tname\targs\tstage\tnorm\n"
GO_MOD = "Platform/common/versions/go.mod"
MODULES_TEXT = """# Shared code modules

## Module inventory

| Name | Go module | Contract | Consumers in lessons 1–7 |
|---|---|---|---|
| `json` | `example.local/common/json` | c | `01-store`, `02-installer`; JCS only where the contract calls it |
| `mask` | `example.local/common/mask` | c | `02-installer`: masking only |

## Pins and use

A consuming Go lesson has a `requires_module` row with the inventory's exact module path and `from` equal to
`Platform/common/versions/go.mod`.

The lesson's `forbid_imports` row excludes direct `encoding/json` imports in its main module, so parsing and JSON
encoding go through the shared `json` module.
"""


def row(rid, kind, args, name="core", stage="model", norm="P/01.1 N1"):
    return f"{rid}\t{kind}\t{name}\t{args if isinstance(args, str) else json.dumps(args)}\t{stage}\t{norm}\n"


def requires(rid, module, origin=GO_MOD):
    return row(rid, "requires_module", {"module": module, "from": origin})


def forbids(rid, forbid=("encoding/json",)):
    return row(rid, "forbid_imports", {"forbid": list(forbid)})


class Tree:
    """A synthetic course root: the real dictionary of kinds, a go.mod, modules.md and lesson forms."""

    def __init__(self, case):
        self.temp = tempfile.TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        dictionary = self.root / check_forms.CODE_DICTIONARY
        dictionary.parent.mkdir(parents=True)
        dictionary.write_bytes((COURSE / check_forms.CODE_DICTIONARY).read_bytes())
        (self.root / GO_MOD).parent.mkdir(parents=True)
        (self.root / GO_MOD).write_text("module versions\n", encoding="utf-8")
        self.modules(MODULES_TEXT)

    def modules(self, text):
        (self.root / check_forms.MODULES).write_text(text, encoding="utf-8")

    def lesson(self, name, *rows):
        forms = self.root / "Platform" / name / "forms"
        forms.mkdir(parents=True, exist_ok=True)
        path = forms / "code-rules.tsv"
        path.write_text(HEAD + "".join(rows), encoding="utf-8")
        return path

    def green(self):
        self.lesson("01-store", requires("C01", "example.local/common/json"), forbids("C02"))
        self.lesson("02-installer", requires("C01", "example.local/common/json"),
                    requires("C02", "example.local/common/mask"), forbids("C03"))


class DictionaryKinds(unittest.TestCase):
    def test_template_alternatives_and_outer_fields(self):
        self.assertEqual(check_forms.template_fields('{} or {"core": <name>}'), [frozenset(), frozenset({"core"})])
        self.assertEqual(check_forms.template_fields(
            '{"forbid": [<import path>, ...]} or {"forbid": [<import path>, ...], "allow": [{"name": <package name of '
            'the profile code mapping>, "imports": [<import path>, ...], "norm": <norm reference>}, ...]}'),
            [frozenset({"forbid"}), frozenset({"forbid", "allow"})])

    def test_dictionary_defines_forbid_imports(self):
        errors, kinds = check_forms.code_kinds(COURSE)
        self.assertEqual(errors, [])
        self.assertEqual(kinds["forbid_imports"], [frozenset({"forbid"}), frozenset({"forbid", "allow"})])
        self.assertEqual(kinds["requires_module"], [frozenset({"module", "from"})])

    def test_published_lesson_rows_hold(self):
        forms = check_forms.code_rule_forms(COURSE)
        self.assertTrue(forms)
        for path in forms:
            with self.subTest(path=path.parent.parent.name):
                self.assertEqual(check_forms.check_code_rules(path)[0], [])


class LessonRows(unittest.TestCase):
    def setUp(self):
        self.tree = Tree(self)

    def errors(self, *rows):
        return check_forms.check_code_rules(self.tree.lesson("01-store", *rows))[0]

    def test_forbid_imports_with_and_without_allow_holds(self):
        allow = {"forbid": ["encoding/json", "net/http"],
                 "allow": [{"name": "launch", "imports": ["net/http/httptest"], "norm": "P/01.3 N1.3"}]}
        self.assertEqual(self.errors(forbids("C01"), row("C02", "forbid_imports", allow),
                                     requires("C03", "example.local/common/json")), [])

    def test_forbid_imports_args_refuse(self):
        cases = {
            "nonempty list": {"forbid": []},
            "not an import path": {"forbid": ["encoding json"]},
            "repeats": {"forbid": ["encoding/json", "encoding/json"]},
            "objects name, imports, norm": {"forbid": ["encoding/json"], "allow": []},
            "exactly name, imports, norm": {"forbid": ["encoding/json"],
                                            "allow": [{"name": "x", "imports": ["encoding/json"]}]},
            "match no entry of forbid": {"forbid": ["encoding/json"],
                                         "allow": [{"name": "x", "imports": ["encoding/jsonx"], "norm": "P/01.1 N1"}]},
            "norm is empty": {"forbid": ["encoding/json"],
                              "allow": [{"name": "x", "imports": ["encoding/json"], "norm": " "}]},
            "names no reference": {"forbid": ["encoding/json"],
                                   "allow": [{"name": "x", "imports": ["encoding/json"], "norm": "because it is faster"}]},
            "are not the fields of forbid_imports": {"forbid": ["encoding/json"], "except": []},
        }
        for message, args in cases.items():
            with self.subTest(message=message):
                errors = self.errors(row("C01", "forbid_imports", args))
                self.assertTrue(any(message in e and "C01" in e for e in errors), errors)

    def test_kind_and_json_shape_refuse(self):
        cases = {
            "is not in the dictionary": row("C01", "no_such_kind", {}),
            "duplicate key": row("C01", "forbid_imports", '{"forbid": ["a"], "forbid": ["b"]}'),
            "not one JSON object": row("C01", "property_tests", "[]"),
            "are not the fields of property_tests": row("C01", "property_tests", {"x": 1}),
        }
        for message, line in cases.items():
            with self.subTest(message=message):
                errors = self.errors(line)
                self.assertTrue(any(message in e for e in errors), errors)

    def test_requires_module_args_refuse(self):
        for message, args in {"is not a module path": {"module": "a b", "from": GO_MOD},
                              "is not a go.mod file": {"module": "a/b", "from": "Platform/common/versions/none/go.mod"},
                              "is not a go.mod file of": {"module": "a/b", "from": "Platform/common/modules.md"}}.items():
            with self.subTest(message=message):
                errors = self.errors(row("C01", "requires_module", args))
                self.assertTrue(any(message in e for e in errors), errors)

    def test_missing_dictionary_refuses(self):
        (self.tree.root / check_forms.CODE_DICTIONARY).unlink()
        errors = self.errors(forbids("C01"))
        self.assertTrue(any("no dictionary of the kinds of code checks" in e for e in errors), errors)

    def test_allow_norm_is_a_reference_form_refs_judges(self):
        cell = json.dumps({"forbid": ["encoding/json"],
                           "allow": [{"name": "x", "imports": ["encoding/json"], "norm": "P/01.3 N1.3"}]})
        self.assertIn("section", [r[0] for r in form_refs.cell_refs(cell, "args")])


class SharedModules(unittest.TestCase):
    def setUp(self):
        self.tree = Tree(self)

    def messages(self):
        return [m for _, m in check_forms.module_consumer_errors(self.tree.root)]

    def test_consumers_with_their_rows_hold(self):
        self.tree.green()
        self.assertEqual(self.messages(), [])

    def test_published_course_holds(self):
        self.assertEqual(check_forms.module_consumer_errors(COURSE), [])

    def test_consumer_without_requires_module_refuses(self):
        self.tree.green()
        self.tree.lesson("02-installer", requires("C01", "example.local/common/json"), forbids("C03"))
        self.assertTrue(any("02-installer is a consumer of the shared module mask" in m for m in self.messages()))

    def test_consumer_without_code_rules_refuses(self):
        self.tree.green()
        (self.tree.root / "Platform/02-installer/forms/code-rules.tsv").unlink()
        self.assertTrue(any("02-installer is a consumer of the shared module json" in m for m in self.messages()))

    def test_other_pin_location_refuses(self):
        self.tree.green()
        self.tree.lesson("01-store", requires("C01", "example.local/common/json", "Platform/01-store/go.mod"),
                         forbids("C02"))
        messages = self.messages()
        self.assertTrue(any("C01: requires_module example.local/common/json from 'Platform/01-store/go.mod'" in m
                            for m in messages), messages)
        self.assertTrue(any("01-store is a consumer of the shared module json" in m for m in messages), messages)

    def test_non_consumer_row_refuses(self):
        self.tree.green()
        self.tree.lesson("01-store", requires("C01", "example.local/common/json"),
                         requires("C03", "example.local/common/mask"), forbids("C02"))
        self.assertTrue(any("C03: requires_module example.local/common/mask, and 01-store is not a consumer" in m
                            for m in self.messages()))

    def test_unknown_shared_module_refuses(self):
        self.tree.green()
        self.tree.lesson("03-worker", requires("C01", "example.local/common/other"))
        self.assertTrue(any("example.local/common/other — a shared module path that the inventory" in m
                            for m in self.messages()))

    def test_json_consumer_without_forbid_imports_refuses(self):
        self.tree.green()
        self.tree.lesson("01-store", requires("C01", "example.local/common/json"), forbids("C02", ["net/http"]))
        self.assertTrue(any("01-store is a consumer of the shared module json in" in m and "forbids encoding/json" in m
                            for m in self.messages()))

    def test_unreadable_text_refuses(self):
        self.tree.green()
        for message, text in {
                "no section «## Module inventory»": MODULES_TEXT.replace("## Module inventory", "## Modules"),
                "pin location of a requires_module row is not readable":
                    MODULES_TEXT.replace("`from` equal to", "`from` at"),
                "rule of the forbid_imports row is not readable":
                    MODULES_TEXT.replace("excludes direct", "names"),
                "consumer 09-none is no lesson": MODULES_TEXT.replace("`02-installer`: masking", "`09-none`: masking"),
        }.items():
            with self.subTest(message=message):
                self.tree.modules(text)
                self.assertTrue(any(message in m for m in self.messages()), self.messages())

    def test_no_modules_text_reads_nothing(self):
        (self.tree.root / check_forms.MODULES).unlink()
        self.tree.lesson("01-store", requires("C01", "example.local/common/json"))
        self.assertEqual(self.messages(), [])


class ContractInput(unittest.TestCase):
    def test_every_consumer_lesson_has_the_narrow_m(self):
        text = (COURSE / check_forms.MODULES).read_text(encoding="utf-8")
        errors, inventory = check_forms.module_inventory(text, COURSE / "Platform")
        self.assertEqual(errors, [])
        for lesson in sorted({c for m in inventory for c in m["consumers"]}):
            with self.subTest(lesson=lesson):
                self.assertIn(f"P/{re.match(r'([0-9]{2})-', lesson)[1]}", m_form.M_NARROW)


if __name__ == "__main__":
    unittest.main()
