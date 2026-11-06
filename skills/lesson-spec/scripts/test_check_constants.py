"""Independent P/08 carrier roster, closed-reference and frozen-witness mutants."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import check_constants

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "decisions/journal/platform/08-domain/2026-11-06-runtime-constants-equality-project.json"


def parent_at(doc, pointer):
    keys = [key.replace("~1", "/").replace("~0", "~") for key in pointer[1:].split("/")]
    for key in keys[:-1]:
        doc = doc[key]
    return doc, keys[-1]


class Constants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Author's supplied scope is an independent witness, never a production
        # checker input. No access to implementation/generator code.
        cls.project = json.loads(PROJECT.read_text())
        cls.roster = [(r["path"], r["pointer"], r["owner"], r["constant"]) for r in cls.project["schema_carriers"]]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths = {row[0] for row in self.roster}
        paths |= {f"Platform/{owner}/forms/runtime-constants.tsv" for owner in ("06-console", "08-domain", "09-agent")}
        paths |= {f"Platform/common/{ru}contracts/{name}.md" for ru in ("", "ru/") for name in ("accept", "password-hash")}
        paths |= {"Platform/common/vectors/password-hash/cases.tsv", "Platform/common/vectors/wire.tsv"}
        for rel in paths:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)

    def check(self):
        return check_constants.check_p08_constants(self.root)

    def errors(self):
        return self.check()[0]

    def change_number(self, rel, pointer, value):
        path = self.root / rel
        doc = yaml.safe_load(path.read_text()) if rel.endswith(".yaml") else json.loads(path.read_text())
        parent, key = parent_at(doc, pointer)
        parent[key] = value
        path.write_text(yaml.safe_dump(doc) if rel.endswith(".yaml") else json.dumps(doc))

    def replace_constant(self, owner, name, value):
        path = self.root / f"Platform/{owner}/forms/runtime-constants.tsv"
        lines = path.read_text().splitlines()
        i = next(i for i, line in enumerate(lines) if line.startswith(name + "\t"))
        cells = lines[i].split("\t")
        cells[1] = str(value)
        lines[i] = "\t".join(cells)
        path.write_text("\n".join(lines) + "\n")

    def test_clean_and_exact_closed_roster(self):
        self.assertEqual(len(self.roster), 141)
        self.assertEqual(len(set(self.roster)), 141)
        self.assertEqual(set(check_constants.schema_bindings()), set(self.roster))
        errors, stats = self.check()
        self.assertEqual(errors, [])
        self.assertEqual(stats, {"p08_schema_equalities": 141, "p08_form_equalities": 5,
                                 "p08_closed_contracts": 4, "p08_password_vectors": 13})

    def test_each_of_141_numeric_carriers_has_its_own_mutant(self):
        for rel, pointer, _, _ in self.roster:
            with self.subTest(path=rel, pointer=pointer):
                path = self.root / rel
                original = path.read_bytes()
                doc = yaml.safe_load(original) if rel.endswith(".yaml") else json.loads(original)
                parent, key = parent_at(doc, pointer)
                try:
                    self.change_number(rel, pointer, parent[key] + 1)
                    self.assertTrue(any(p == path and pointer in message for p, message in self.errors()))
                finally:
                    path.write_bytes(original)

    def test_every_carrier_file_is_required(self):
        for rel in sorted({row[0] for row in self.roster}):
            with self.subTest(path=rel):
                path = self.root / rel
                original = path.read_bytes()
                try:
                    path.unlink()
                    self.assertTrue(any(p == path for p, _ in self.errors()))
                finally:
                    path.write_bytes(original)

    def test_missing_pointer_and_invalid_numeric_types(self):
        rel = "Platform/common/data/common.schema.json"
        pointer = "/$defs/common.book_row/properties//properties/missing/maxItems"
        path = self.root / rel
        original = path.read_bytes()
        for value in ("500", None, [], {}, False):
            with self.subTest(value=value):
                self.change_number(rel, pointer, value)
                self.assertTrue(any(p == path and pointer in message for p, message in self.errors()))
                path.write_bytes(original)
        doc = json.loads(original)
        parent, key = parent_at(doc, pointer)
        del parent[key]
        path.write_text(json.dumps(doc))
        self.assertTrue(any(p == path and "missing numeric carrier" in message for p, message in self.errors()))
        for content in ("null", "[]", "true", '"not a schema"'):
            path.write_text(content)
            self.assertTrue(any(p == path for p, _ in self.errors()))

    def test_boolean_does_not_equal_integer_one(self):
        self.replace_constant("08-domain", "MISSING_SHOWN", 1)
        rel = "Platform/common/data/common.schema.json"
        pointer = "/$defs/common.book_row/properties//properties/stale/maxItems"
        self.change_number(rel, pointer, True)
        self.assertTrue(any(p == self.root / rel and pointer in message for p, message in self.errors()))

    def test_exact_numeric_equality_without_float_rounding(self):
        targets = [("Platform/08-domain/data/users.schema.json", "/properties/title/maxLength"),
                   ("Platform/08-domain/spec/08-domain.api.openapi.yaml",
                    "/components/schemas/PersonView/properties/title/maxLength")]
        for rel, pointer in targets:
            path = self.root / rel
            original = path.read_bytes()
            for number, refused in (("200.0", False), ("200.0000000000000000000001", True)):
                with self.subTest(path=rel, number=number):
                    self.change_number(rel, pointer, "PRECISE_NUMBER")
                    text = path.read_text().replace('"PRECISE_NUMBER"', number).replace("PRECISE_NUMBER", number)
                    path.write_text(text)
                    errors = self.errors()
                    self.assertEqual(any(p == path and pointer in m for p, m in errors), refused, errors)
                    path.write_bytes(original)

    def test_each_referenced_constant_is_required(self):
        names = {(owner, name) for _, _, owner, name in self.roster}
        names |= {(a, left) for a, left, _, _, _, _ in check_constants.FORM_EQUALITIES}
        names |= {(b, right) for _, _, b, right, _, _ in check_constants.FORM_EQUALITIES}
        names |= {("08-domain", "PBKDF2_ITERATIONS"), ("08-domain", "KNOCKS")}
        for owner, name in sorted(names):
            with self.subTest(owner=owner, name=name):
                path = self.root / f"Platform/{owner}/forms/runtime-constants.tsv"
                original = path.read_bytes()
                try:
                    path.write_text("\n".join(line for line in original.decode().splitlines()
                                               if not line.startswith(name + "\t")) + "\n")
                    self.assertTrue(any(p == path and "missing constant " + name in m for p, m in self.errors()))
                finally:
                    path.write_bytes(original)

    def test_each_of_five_form_equalities_is_checked(self):
        expected = [("SERVERS_MAX", 501), ("BATCH_LIMIT", 67108865), ("BOOK_PARTS_PASS", 9),
                    ("REPORT_EVERY", 6), ("BODY_LIMIT", 16777217)]
        path = self.root / "Platform/08-domain/forms/runtime-constants.tsv"
        original = path.read_bytes()
        for name, value in expected:
            with self.subTest(name=name):
                self.replace_constant("08-domain", name, value)
                self.assertTrue(any("form equality 08-domain/" + name in m for _, m in self.errors()))
                path.write_bytes(original)

    def test_missing_constant_file_duplicate_nondecimal_and_wrong_unit(self):
        path = self.root / "Platform/08-domain/forms/runtime-constants.tsv"
        original = path.read_bytes()
        row = next(line for line in original.decode().splitlines() if line.startswith("PBKDF2_ITERATIONS\t"))
        for value in ("0600000", "6e5", "600000.0", "-1", "0", "٦٠٠٠٠٠"):
            with self.subTest(value=value):
                self.replace_constant("08-domain", "PBKDF2_ITERATIONS", value)
                self.assertTrue(self.errors())
                path.write_bytes(original)
        for content in (original + (row + "\n").encode(), original.replace(row.encode(), row.replace("\tcount\t", "\ts\t").encode()),
                        b"bad\theader\n", b""):
            path.write_bytes(content)
            self.assertTrue(self.errors())
        path.unlink()
        self.assertTrue(any(p == path for p, _ in self.errors()))

    def test_actual_fences_no_aliases_duplicate_fields_or_quoted_decoys(self):
        for ru in ("", "ru/"):
            path = self.root / f"Platform/common/{ru}contracts/password-hash.md"
            original = path.read_text()
            block = original.split("```yaml\n", 1)[1].split("```", 1)[0]
            bad = [original.replace("$<PBKDF2_ITERATIONS>$", "$600000$"),
                   original.replace("$<PBKDF2_ITERATIONS>$", "$<PBKDF2_ITERATIONS in decimal>$"),
                   original.replace("form:", "form_alias:", 1),
                   original.replace("hash:", "form: extra\nhash:", 1),
                   original + "\n```yaml\n" + block + "```\n",
                   original.replace("```yaml\n" + block + "```", "> ```yaml\n" + "\n".join("> " + x for x in block.splitlines()) + "\n> ```"),
                   original.replace("PBKDF2_ITERATIONS " + ("итераций" if ru else "iterations"), "600000 iterations")]
            for i, text in enumerate(bad):
                with self.subTest(language=ru, mutant=i):
                    path.write_text(text)
                    self.assertTrue(any(p == path for p, _ in self.errors()))
            path.write_text(original)

    def test_unique_binding_owner_and_strict_decimal_declaration(self):
        for ru in ("", "ru/"):
            for name in ("password-hash", "accept"):
                path = self.root / f"Platform/common/{ru}contracts/{name}.md"
                original = path.read_text()
                bad = [original.replace("08-domain/forms/runtime-constants.tsv", "09-agent/forms/runtime-constants.tsv"),
                       original + "\n[another binding](../../09-agent/forms/runtime-constants.tsv)\n"]
                if name == "password-hash":
                    bad += [original.replace("ASCII", "Unicode"),
                            original.replace("без ведущих нулей" if ru else "unpadded ASCII decimal digits", "padded digits")]
                for i, text in enumerate(bad):
                    with self.subTest(language=ru, contract=name, mutant=i):
                        path.write_text(text)
                        self.assertTrue(any(p == path for p, _ in self.errors()))
                path.write_text(original)

    def test_relay_references_cannot_be_literals_or_different_names(self):
        for ru in ("", "ru/"):
            path = self.root / f"Platform/common/{ru}contracts/accept.md"
            original = path.read_text()
            ref = "значение формы P/08" if ru else "the P/08 form value"
            for text in (original.replace(ref, "64 MiB", 1), original.replace("KNOCKS + 1", "33"),
                         original.replace("BATCH_LIMIT:   ", "BATCH_ALIAS:   ", 1)):
                path.write_text(text)
                self.assertTrue(any(p == path for p, _ in self.errors()))
            path.write_text(original)

    def test_missing_contracts_or_password_witnesses_are_not_skipped(self):
        files = [f"Platform/common/{ru}contracts/{name}.md" for ru in ("", "ru/") for name in ("accept", "password-hash")]
        files += ["Platform/common/vectors/password-hash/cases.tsv", "Platform/common/vectors/wire.tsv"]
        for rel in files:
            with self.subTest(path=rel):
                path = self.root / rel
                original = path.read_bytes()
                path.unlink()
                self.assertTrue(any(p == path for p, _ in self.errors()))
                path.write_bytes(original)

    def test_wire_cost_fixture_bytes_and_binding_strictness(self):
        self.replace_constant("08-domain", "PBKDF2_ITERATIONS", 600001)
        self.assertTrue(any("wire cost/form differs" in m for _, m in self.errors()))
        self.replace_constant("08-domain", "PBKDF2_ITERATIONS", 600000)
        path = self.root / "Platform/common/vectors/password-hash/cases.tsv"
        original = path.read_bytes()
        for content in (original.replace(b"$600000$", b"$600001$"), original.replace(b"$100000$", b"$600000$"), original + b"\n"):
            path.write_bytes(content)
            self.assertTrue(any(p == path and "byte-exact" in m for p, m in self.errors()))
        path.write_bytes(original)
        wire = self.root / "Platform/common/vectors/wire.tsv"
        text = wire.read_text()
        row = next(line for line in text.splitlines() if line.startswith("common/password-hash\t"))
        for bad in (text.replace(row, row.replace("\tvalue\t", "\ttext\t")), text + row + "\n"):
            wire.write_text(bad)
            self.assertTrue(any(p == wire for p, _ in self.errors()))


class StoreConstants(unittest.TestCase):
    """Independent three-pointer scope; actual source values, owned fixture mutations."""
    FORM = "Platform/01-store/forms/runtime-constants.tsv"
    API = "Platform/01-store/spec/01-store.api.openapi.yaml"
    DOORS = "Platform/01-store/data/configstore-doors.schema.json"
    BINDINGS = (
        (API, "/components/schemas/Status/properties/admission_ahead/exclusiveMinimum", "CLOCK_SKEW", "s"),
        (API, "/components/schemas/Key/description", "KEY_BYTES", "bytes"),
        (DOORS, "/properties/seen_at/description", "DOOR_SEEN_EVERY", "s"),
    )

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.original = {rel: (ROOT / rel).read_bytes() for rel in (self.FORM, self.API, self.DOORS)}
        self.restore()
        rows = [line.split("\t") for line in self.original[self.FORM].decode().split("\n")
                if line and not line.startswith("#")][1:]
        self.values = {row[0]: int(row[1]) for row in rows}

    def restore(self):
        for rel, data in self.original.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def check(self):
        return check_constants.check_p01_constants(self.root)

    def document(self, rel):
        text = (self.root / rel).read_text()
        return yaml.safe_load(text) if rel.endswith(".yaml") else json.loads(text)

    def write_document(self, rel, doc):
        (self.root / rel).write_text(yaml.safe_dump(doc) if rel.endswith(".yaml") else json.dumps(doc))

    def carrier(self, binding, value, literal=False):
        rel, pointer, name, _ = binding
        doc = self.document(rel)
        parent, key = parent_at(doc, pointer)
        if literal or name == "CLOCK_SKEW":
            parent[key] = value
        else:
            pattern = r"(?<=limit of )[0-9]+(?= UTF-8 bytes)" if name == "KEY_BYTES" else r"(?<=every )[0-9]+(?= s\))"
            parent[key], count = re.subn(pattern, str(value), parent[key])
            self.assertEqual(count, 1, "the actual description must contain one numeric binding")
        self.write_document(rel, doc)

    def constant(self, name, value=None, unit=None, remove=False, duplicate=False):
        path = self.root / self.FORM
        lines = path.read_text().split("\n")
        places = [i for i, line in enumerate(lines) if line.startswith(name + "\t")]
        self.assertEqual(len(places), 1)
        at = places[0]
        cells = lines[at].split("\t")
        if value is not None:
            cells[1] = str(value)
        if unit is not None:
            cells[2] = unit
        lines[at] = "\t".join(cells)
        if duplicate:
            lines.append(lines[at])
        if remove:
            del lines[at]
        path.write_text("\n".join(lines))

    def assert_carrier_error(self, binding):
        rel, pointer, _, _ = binding
        errors, stats = self.check()
        self.assertTrue(any(path == self.root / rel and pointer in message for path, message in errors), errors)
        self.assertLess(stats.get("p01_constant_equalities", 0), 3)

    def test_actual_closed_three_pointer_roster_and_read_only_clean(self):
        self.assertEqual(tuple(row[:4] for row in check_constants.P01_CONSTANT_BINDINGS), self.BINDINGS)
        self.assertEqual(self.check(), ([], {"p01_constant_equalities": 3}))
        self.assertEqual({rel: (self.root / rel).read_bytes() for rel in self.original}, self.original)

    def test_each_row_only_drift_fails(self):
        for binding in self.BINDINGS:
            with self.subTest(name=binding[2]):
                self.constant(binding[2], self.values[binding[2]] + 7)
                self.assert_carrier_error(binding)
                self.restore()

    def test_each_carrier_only_drift_fails(self):
        for binding in self.BINDINGS:
            with self.subTest(name=binding[2]):
                self.carrier(binding, self.values[binding[2]] + 7)
                self.assert_carrier_error(binding)
                self.restore()

    def test_each_coherent_change_uses_the_actual_form_value(self):
        for binding in self.BINDINGS:
            for value in (1, self.values[binding[2]] + 7, 9007199254740991):
                with self.subTest(name=binding[2], value=value):
                    self.constant(binding[2], value)
                    self.carrier(binding, value)
                    self.assertEqual(self.check(), ([], {"p01_constant_equalities": 3}))
                    self.restore()

    def test_missing_each_file_and_exact_pointer_never_uses_decoys(self):
        for rel in self.original:
            with self.subTest(file=rel):
                (self.root / rel).unlink()
                self.assertTrue(any(path == self.root / rel for path, _ in self.check()[0]))
                self.restore()
        for binding in self.BINDINGS:
            rel, pointer, _, _ = binding
            with self.subTest(pointer=pointer):
                doc = self.document(rel)
                parent, key = parent_at(doc, pointer)
                doc[key] = parent.pop(key)
                self.write_document(rel, doc)
                self.assert_carrier_error(binding)
                self.restore()

    def test_required_single_rows_units_and_unpadded_ascii_integer_types(self):
        for _, _, name, unit in self.BINDINGS:
            mutations = [{"remove": True}, {"duplicate": True}, {"unit": "bytes" if unit == "s" else "s"}]
            mutations += [{"value": value} for value in ("true", "false", "0", "-1", "1.0", "1e2", "01", "١", "", " 1")]
            for mutation in mutations:
                with self.subTest(name=name, mutation=mutation):
                    self.constant(name, **mutation)
                    self.assertTrue(any(path == self.root / self.FORM for path, _ in self.check()[0]))
                    self.restore()
        for text in ("", "bad\theader\n", "name\tvalue\tunit\tnorm\tmeaning\nCLOCK_SKEW\t1\ts\n"):
            (self.root / self.FORM).write_text(text)
            self.assertTrue(self.check()[0])

    def test_numeric_carrier_rejects_boolean_and_wrong_types(self):
        binding = self.BINDINGS[0]
        self.constant("CLOCK_SKEW", 1)
        form = (self.root / self.FORM).read_bytes()
        for value in (True, False, None, "1", [], {}, 1.5):
            with self.subTest(value=value):
                self.carrier(binding, value)
                self.assert_carrier_error(binding)
                self.restore()
                (self.root / self.FORM).write_bytes(form)

    def test_nonfinite_carrier_source_is_an_explicit_parse_failure(self):
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                self.carrier(self.BINDINGS[0], value)
                errors, stats = self.check()
                self.assertTrue(any(path == self.root / self.API and "cannot parse numeric carrier" in message
                                    for path, message in errors), errors)
                self.assertLess(stats.get("p01_constant_equalities", 0), 3)
                self.restore()

    def test_numeric_equality_is_exact_without_binary_float_rounding(self):
        binding = self.BINDINGS[0]
        for suffix, refused in ((".0", False), (".000000000000000000001", True)):
            self.carrier(binding, "PRECISE_NUMBER")
            path = self.root / self.API
            text = path.read_text()
            self.assertEqual(text.count("PRECISE_NUMBER"), 1)
            path.write_text(text.replace("PRECISE_NUMBER", str(self.values["CLOCK_SKEW"]) + suffix))
            if refused:
                self.assert_carrier_error(binding)
            else:
                self.assertEqual(self.check(), ([], {"p01_constant_equalities": 3}))
            self.restore()

    def test_strict_greater_cannot_be_replaced_by_minimum_or_wrong_schema_type(self):
        binding = self.BINDINGS[0]
        for kind in ("inclusive", "additional minimum", "integer", "string", "number list", "missing type"):
            with self.subTest(kind=kind):
                doc = self.document(self.API)
                parent, key = parent_at(doc, binding[1])
                if kind == "inclusive":
                    parent["minimum"] = parent.pop(key)
                elif kind == "additional minimum":
                    parent["minimum"] = self.values["CLOCK_SKEW"] + 1
                elif kind == "missing type":
                    del parent["type"]
                else:
                    parent["type"] = ["number"] if kind == "number list" else kind
                self.write_document(self.API, doc)
                self.assert_carrier_error(binding)
                self.restore()

    def test_key_description_requires_one_utf8_byte_binding_and_preserves_sentence(self):
        binding = self.BINDINGS[1]
        parent, key = parent_at(self.document(self.API), binding[1])
        text = parent[key]
        number = str(self.values["KEY_BYTES"])
        bad = [text.replace("UTF-8 bytes", unit) for unit in ("characters", "UTF-8 characters", "UTF-16 bytes", "bytes")]
        bad += [text.replace(number, value) for value in ("0" + number, number + ".0", "١٠٢٤", "true")]
        bad += [text + " " + text, text + " Another limit is accepted.", text.replace("a smaller file limit", "a larger file limit"),
                text.replace("maxLength does not express", "maxLength expresses"), "UTF-8 bytes " + number]
        for changed in bad:
            with self.subTest(description=changed):
                self.assertNotEqual(changed, text)
                self.carrier(binding, changed, literal=True)
                self.assert_carrier_error(binding)
                self.restore()

    def test_door_description_requires_one_seconds_binding(self):
        binding = self.BINDINGS[2]
        parent, key = parent_at(self.document(self.DOORS), binding[1])
        text = parent[key]
        number = str(self.values["DOOR_SEEN_EVERY"])
        bad = [text.replace(" s)", unit) for unit in (" ms)", " min)", " bytes)")]
        bad += [text.replace(number, value) for value in ("0" + number, number + ".0", "٣٠", "true")]
        bad += [text + " " + text, text.replace("every", "at least every"), "every " + number + " s", text + "; or 1 s"]
        for changed in bad:
            with self.subTest(description=changed):
                self.assertNotEqual(changed, text)
                self.carrier(binding, changed, literal=True)
                self.assert_carrier_error(binding)
                self.restore()

    def test_descriptions_are_strings_and_key_maxlength_is_not_a_byte_limit(self):
        for binding in self.BINDINGS[1:]:
            for value in (None, True, False, 1, [], {}):
                with self.subTest(pointer=binding[1], value=value):
                    self.carrier(binding, value, literal=True)
                    self.assert_carrier_error(binding)
                    self.restore()
        for schema_type in ("string", "number", ["string"]):
            doc = self.document(self.API)
            parent, _ = parent_at(doc, self.BINDINGS[1][1])
            parent["type"] = schema_type
            if schema_type == "string":
                parent["maxLength"] = self.values["KEY_BYTES"]
            self.write_document(self.API, doc)
            self.assert_carrier_error(self.BINDINGS[1])
            self.restore()

    def test_duplicate_document_keys_malformed_files_and_nonutf8_fail(self):
        for rel in (self.API, self.DOORS):
            for raw in (b"null", b"[]", b"true", b'"not an object"', b"\xff", b"{invalid"):
                with self.subTest(file=rel, raw=raw):
                    (self.root / rel).write_bytes(raw)
                    self.assertTrue(any(path == self.root / rel for path, _ in self.check()[0]))
                    self.restore()
        path = self.root / self.API
        text = path.read_text()
        line = "          exclusiveMinimum: " + str(self.values["CLOCK_SKEW"])
        self.assertEqual(text.count(line + "\n"), 1)
        path.write_text(text.replace(line + "\n", line + "\n" + line + "\n"))
        self.assertTrue(any(path == p and "duplicate" in m.lower() for p, m in self.check()[0]))
        self.restore()
        path = self.root / self.DOORS
        text = path.read_text()
        line = next(line for line in text.split("\n") if '"description":' in line)
        self.assertEqual(text.count(line), 1)
        path.write_text(text.replace(line, line + "\n" + line))
        self.assertTrue(any(path == p and "duplicate" in m.lower() for p, m in self.check()[0]))

    def test_actual_mutants_fail_through_check_spec_hook(self):
        from check_spec import Check
        for source in (ROOT / "Platform/01-store/spec").glob("*.norms.md"):
            shutil.copyfile(source, self.root / "Platform/01-store/spec" / source.name)
        clean = Check(self.root)
        clean.check_forms()
        self.assertEqual(clean.errors, [])
        self.assertEqual(clean.stats["p01_constant_equalities"], 3)
        for binding in self.BINDINGS:
            with self.subTest(name=binding[2]):
                self.carrier(binding, self.values[binding[2]] + 7)
                result = Check(self.root)
                result.check_forms()
                self.assertTrue(any(binding[1] in message for message in result.errors), result.errors)
                self.restore()


class FolderConstants(unittest.TestCase):
    BINDINGS = (
        ("Platform/06-console/data/folders.schema.json", "/$defs/writer/properties/members/maxItems", "FOLDERS_MEMBERS_MAX"),
        ("Platform/06-console/data/memberof.schema.json", "/$defs/writer/properties/folders/maxItems", "FOLDERS_PER_UNIT_MAX"),
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.form = self.root / "Platform/06-console/forms/runtime-constants.tsv"
        for rel in [self.form.relative_to(self.root), *(Path(row[0]) for row in self.BINDINGS)]:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)

    def check(self):
        return check_constants.check_p06_folder_constants(self.root)

    def constant(self, name, value):
        lines = self.form.read_text().split("\n")
        at = next(i for i, line in enumerate(lines) if line.startswith(name + "\t"))
        cells = lines[at].split("\t")
        cells[1] = str(value)
        lines[at] = "\t".join(cells)
        self.form.write_text("\n".join(lines))

    def test_actual_two_pointers_match_actual_source_and_are_read_only(self):
        self.assertEqual(check_constants.P06_FOLDER_BINDINGS, self.BINDINGS)
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.check(), ([], {"p06_folder_equalities": 2}))
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_each_missing_file_and_pointer_and_decoy_pointer_fail(self):
        for rel, pointer, _ in self.BINDINGS:
            path = self.root / rel
            original = path.read_bytes()
            with self.subTest(path=rel):
                path.unlink()
                self.assertTrue(any(p == path for p, _ in self.check()[0]))
                path.write_bytes(original)
                doc = json.loads(original)
                parent, key = parent_at(doc, pointer)
                value = parent.pop(key)
                # A same-named root/read carrier is never the assigned writer pointer.
                doc["maxItems"] = value
                path.write_text(json.dumps(doc))
                self.assertTrue(any(p == path and "missing numeric carrier " + pointer in m for p, m in self.check()[0]))
                path.write_bytes(original)

    def test_every_wrong_value_and_noninteger_type_fails(self):
        for rel, pointer, _ in self.BINDINGS:
            path = self.root / rel
            original = path.read_bytes()
            for wrong in (0, 1, "8", None, True, False, [], {}, 8.0, 1000.0):
                with self.subTest(path=rel, value=wrong):
                    doc = json.loads(original)
                    parent, key = parent_at(doc, pointer)
                    parent[key] = wrong
                    path.write_text(json.dumps(doc))
                    self.assertTrue(any(p == path and pointer in m for p, m in self.check()[0]))
            path.write_bytes(original)

    def test_actual_integer_type_does_not_accept_true_or_integral_decimal(self):
        for rel, pointer, name in self.BINDINGS:
            path = self.root / rel
            original, form = path.read_bytes(), self.form.read_bytes()
            self.constant(name, 1)
            for wrong in (True, 1.0):
                with self.subTest(path=rel, alias=wrong):
                    doc = json.loads(original)
                    parent, key = parent_at(doc, pointer)
                    parent[key] = wrong
                    path.write_text(json.dumps(doc))
                    self.assertTrue(any(p == path and pointer in m for p, m in self.check()[0]))
            path.write_bytes(original)
            self.form.write_bytes(form)

    def test_values_are_read_from_the_form_not_frozen_in_the_checker(self):
        for rel, pointer, name in self.BINDINGS:
            path = self.root / rel
            original, form = path.read_bytes(), self.form.read_bytes()
            self.constant(name, 13)
            self.assertTrue(any(p == path and pointer in m for p, m in self.check()[0]))
            doc = json.loads(original)
            parent, key = parent_at(doc, pointer)
            parent[key] = 13
            path.write_text(json.dumps(doc))
            self.assertEqual(self.check(), ([], {"p06_folder_equalities": 2}))
            path.write_bytes(original)
            self.form.write_bytes(form)

    def test_single_required_rows_and_positive_unpadded_values(self):
        original = self.form.read_text()
        for _, _, name in self.BINDINGS:
            row = next(line for line in original.split("\n") if line.startswith(name + "\t"))
            variants = {"missing": original.replace(row + "\n", ""), "duplicate": original + row + "\n",
                        "wrong unit": original.replace(row, row.replace("\tcount\t", "\tbytes\t"))}
            for value in ("0", "-1", "true", "false", "1.0", "01", "١", ""):
                cells = row.split("\t")
                cells[1] = value
                variants[value] = original.replace(row, "\t".join(cells))
            for kind, data in variants.items():
                with self.subTest(name=name, corrupt=kind):
                    self.assertNotEqual(data, original)
                    self.form.write_text(data)
                    self.assertTrue(any(p == self.form for p, _ in self.check()[0]))
            self.form.write_text(original)
        self.form.unlink()
        self.assertTrue(any(p == self.form for p, _ in self.check()[0]))


class Integration(unittest.TestCase):
    def test_p01_subject_errors_and_counts_reach_check_spec(self):
        from check_spec import Check
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Platform/01-store").mkdir(parents=True)
            path = root / StoreConstants.API
            result = Check(root)
            with patch("check_constants.check_p01_constants", return_value=([(path, "store subject mutant")],
                                                                          {"p01_constant_equalities": 2})) as called:
                result.check_forms()
            called.assert_called_once_with(root)
            self.assertTrue(any("store subject mutant" in e for e in result.errors))
            self.assertEqual(result.stats["p01_constant_equalities"], 2)

    def test_p06_only_subject_errors_and_counts_reach_check_spec(self):
        from check_spec import Check
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Platform/06-console").mkdir(parents=True)
            path = root / "Platform/06-console/data/folders.schema.json"
            result = Check(root)
            with patch("check_constants.check_p06_folder_constants", return_value=([(path, "folder subject mutant")],
                                                                                {"p06_folder_equalities": 1})) as called:
                result.check_forms()
            called.assert_called_once_with(root)
            self.assertTrue(any("folder subject mutant" in e for e in result.errors))
            self.assertEqual(result.stats["p06_folder_equalities"], 1)

    def test_subject_failure_and_counts_reach_check_spec(self):
        from check_spec import Check
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Platform/08-domain").mkdir(parents=True)
            path = root / "Platform/common/data/common.schema.json"
            result = Check(root)
            with patch("check_constants.check_p08_constants", return_value=([(path, "subject mutant")],
                                                                          {"p08_schema_equalities": 141})) as called:
                result.check_forms()
            called.assert_called_once_with(root)
            self.assertTrue(any("subject mutant" in e for e in result.errors))
            self.assertEqual(result.stats["p08_schema_equalities"], 141)


if __name__ == "__main__":
    unittest.main()
