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
        paths |= {path for path, pointer in check_constants.P08_RELAY_BINDINGS}
        paths.add("Platform/10-domain-console/forms/runtime-constants.tsv")
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
        # ca38a0818 put Judge.relay_members into check_p08_constants: the P08 owner carrier and the P10 reader copy.
        self.assertEqual(stats, {"p08_schema_equalities": 141, "p08_form_equalities": 5,
                                 "p08_closed_contracts": 4, "p08_password_vectors": 13,
                                 "p08_relay_member_equalities": 2})

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
        # P01.257 (af760f774) withdrew R021: the sentence no longer allows a smaller file limit; the withdrawn
        # wording and a narrowing of "every implementation" are both refused.
        withdrawn = text.replace("applies to every implementation and is checked separately",
                                 "and a smaller file limit are checked separately")
        bad += [text + " " + text, text + " Another limit is accepted.", withdrawn,
                text.replace("every implementation", "a file implementation"),
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
        import frictionless_forms
        # Since c4b8f32c2 (OBSH.39) Check.check_forms first validates the whole selected form package once
        # Platform/01-store exists, and then judges every P01 form; the hook fixture therefore holds the actual
        # lesson and the package with its common resources, not only the three carriers and the norms.
        shutil.copytree(ROOT / "Platform/01-store", self.root / "Platform/01-store", dirs_exist_ok=True)
        for name in ("jcs", "rights-evaluator"):
            rel = f"Platform/common/vectors/{name}"
            shutil.copytree(ROOT / rel, self.root / rel)
        rel = "Platform/common/vectors/consumers.tsv"
        shutil.copyfile(ROOT / rel, self.root / rel)
        for rel in (frictionless_forms.PACKAGE,
                    *(f"Platform/{name}{suffix}" for name in frictionless_forms.RESOURCES.values()
                      for suffix in ("", ".schema.json"))):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, self.root / rel)
        self.restore()
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


class RelayMemberConstants(unittest.TestCase):
    FORM = "Platform/08-domain/forms/runtime-constants.tsv"
    FOLLOWER = "Platform/10-domain-console/forms/runtime-constants.tsv"
    # Independent explicit Source addresses: writer owner and the existing reader limit.
    BINDINGS = (
        ("Platform/08-domain/data/relay-members.schema.json", "/properties/members/maxProperties"),
        ("Platform/10-domain-console/spec/10-domain-console.api.openapi.yaml",
         "/paths/~1domain~1relays~1{relay}/get/responses/200/content/application~1json/schema/properties/members/maxItems"),
    )

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.original = {path: (ROOT / path).read_bytes()
                         for path in (self.FORM, self.FOLLOWER, *(p for p, _ in self.BINDINGS))}
        self.restore()
        lines = [l for l in self.original[self.FORM].decode().splitlines() if l and not l.startswith("#")]
        rows = [dict(zip(lines[0].split("\t"), l.split("\t"))) for l in lines[1:]]
        owner = [r for r in rows if r["name"] == "RELAY_MEMBERS_MAX"]
        self.assertEqual(len(owner), 1)
        self.value = int(owner[0]["value"])

    def restore(self):
        for relative, raw in self.original.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def form_value(self, value):
        path = self.root / self.FORM
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith("RELAY_MEMBERS_MAX\t"):
                cells = line.split("\t")
                cells[1] = str(value)
                lines[i] = "\t".join(cells)
                path.write_text("\n".join(lines) + "\n")
                return
        self.fail("owner row absent in fixture")

    def carrier(self, path, pointer, value=...):
        target = self.root / path
        doc = json.loads(target.read_text()) if path.endswith(".json") else yaml.safe_load(target.read_text())
        parent, key = parent_at(doc, pointer)
        if value is ...:
            del parent[key]
        else:
            parent[key] = value
        # JSON is valid YAML too; only this owned fixture is serialized.
        target.write_text(json.dumps(doc, ensure_ascii=False) + "\n")

    def check(self):
        return check_constants.check_p08_relay_constants(self.root)

    def test_actual_source_owner_and_both_carriers_are_read_only(self):
        self.assertEqual(tuple(check_constants.P08_RELAY_BINDINGS), self.BINDINGS)
        self.assertEqual(self.check(), ([], {"p08_relay_member_equalities": 2}))
        self.assertEqual({p: (self.root / p).read_bytes() for p in self.original}, self.original)

    def test_coherent_change_passes_and_owner_only_change_fails(self):
        self.form_value(self.value + 1)
        self.assertTrue(self.check()[0])
        for path, pointer in self.BINDINGS:
            self.carrier(path, pointer, self.value + 1)
        self.assertEqual(self.check(), ([], {"p08_relay_member_equalities": 2}))

    def test_each_carrier_missing_drift_or_type_mutation_fails(self):
        for path, pointer in self.BINDINGS:
            for value in (self.value + 1, True, str(self.value), float(self.value), None, ...):
                with self.subTest(path=path, value=value):
                    self.restore()
                    self.carrier(path, pointer, value)
                    self.assertTrue(self.check()[0])
            self.restore()
            (self.root / path).unlink()
            self.assertTrue(self.check()[0])

    def test_required_owner_row_unit_and_positive_int64_grammar(self):
        path = self.root / self.FORM
        original = self.original[self.FORM].decode()
        line = next(l for l in original.splitlines() if l.startswith("RELAY_MEMBERS_MAX\t"))
        for value in ("0", "0" + str(self.value), "true", "1.5"):
            with self.subTest(value=value):
                self.restore()
                self.form_value(value)
                self.assertTrue(self.check()[0])
        for text in (original.replace(line + "\n", ""), original + line + "\n",
                     original.replace(line, line.replace("\tcount\t", "\tbytes\t"))):
            self.restore()
            path.write_text(text)
            self.assertTrue(self.check()[0])
        self.restore()
        path.unlink()
        self.assertTrue(self.check()[0])

    def test_bool_is_not_integer_and_coherent_overflow_is_not_accepted(self):
        self.form_value(1)
        for path, pointer in self.BINDINGS:
            self.carrier(path, pointer, 1)
        self.assertFalse(self.check()[0])
        for path, pointer in self.BINDINGS:
            self.carrier(path, pointer, True)
            self.assertTrue(self.check()[0])
            self.carrier(path, pointer, 1)
        self.restore()
        value = 9223372036854775808
        self.form_value(value)
        for path, pointer in self.BINDINGS:
            self.carrier(path, pointer, value)
        self.assertTrue(any("int64" in str(e) for e in self.check()[0]))

    def test_follower_cannot_shadow_writer_owner_even_at_the_same_value(self):
        path = self.root / self.FOLLOWER
        path.write_text(path.read_text() + f"RELAY_MEMBERS_MAX\t{self.value}\tcount\tP/10-R004\tduplicate owner\n")
        self.assertTrue(self.check()[0])
        self.restore()
        path.unlink()
        self.assertTrue(self.check()[0])


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



class DeclaredNumericControls(unittest.TestCase):
    """New closed coordinates; changing both carriers coherently must remain valid."""
    BINDINGS = (check_constants.P06_API_BINDINGS + check_constants.P06_SWEEP_BINDINGS +
                check_constants.P06_READER_BINDINGS + check_constants.P09_WRITER_BINDINGS +
                check_constants.P09_READER_BINDINGS + check_constants.P08_NEW_BINDINGS)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.docs, self.owners = {}, {}
        for i, (path, pointer, owner, name, unit) in enumerate(self.BINDINGS):
            value = self.owners.setdefault((owner, name), (i + 17, unit))[0]
            self.put(path, pointer, value)
        self.restore()

    def put(self, path, pointer, value):
        doc = self.docs.setdefault(path, {})
        keys = [x.replace("~1", "/").replace("~0", "~") for x in pointer[1:].split("/")]
        for key in keys[:-1]:
            doc = doc.setdefault(key, {})
        doc[keys[-1]] = value

    def write(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def restore(self):
        for path, doc in self.docs.items():
            self.write(path, json.dumps(doc))
        for owner in {o for o, _ in self.owners}:
            rows = ["name\tvalue\tunit\tnorm\tmeaning"]
            rows += [f"{name}\t{value}\t{unit}\tP/test\tindependent fixture"
                     for (o, name), (value, unit) in self.owners.items() if o == owner]
            self.write(f"Platform/{owner}/forms/runtime-constants.tsv", "\n".join(rows) + "\n")

    def check(self, binding, effective=False):
        judge = check_constants.Judge(self.root)
        judge.declared_equalities((binding,), "selected", effective)
        return judge

    def mutate_owner(self, binding, value=None, unit=None, remove=False, duplicate=False):
        _, _, owner, name, _ = binding
        path = self.root / f"Platform/{owner}/forms/runtime-constants.tsv"
        lines = path.read_text().splitlines()
        at = next(i for i, line in enumerate(lines) if line.startswith(name + "\t"))
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
        path.write_text("\n".join(lines) + "\n")

    def mutate_carrier(self, binding, value=None, remove=False):
        path, pointer, *_ = binding
        doc = json.loads((self.root / path).read_text())
        parent, key = parent_at(doc, pointer)
        if remove:
            del parent[key]
        else:
            parent[key] = value
        self.write(path, json.dumps(doc))

    def test_each_declared_carrier_positive_and_coherent_change(self):
        for binding in self.BINDINGS:
            with self.subTest(binding=binding):
                self.restore()
                self.assertEqual(self.check(binding).errors, [])
                value = self.owners[binding[2:4]][0] + 7
                self.mutate_owner(binding, value)
                self.mutate_carrier(binding, value)
                self.assertEqual(self.check(binding).errors, [])

    def test_positive_int64_endpoints_are_dynamic_and_huge_owners_fail_cleanly(self):
        for binding in self.BINDINGS:
            for value in (1, 9223372036854775807):
                with self.subTest(binding=binding, value=value):
                    self.restore()
                    self.mutate_owner(binding, value)
                    self.mutate_carrier(binding, value)
                    self.assertEqual(self.check(binding).errors, [])
            self.restore()
            self.mutate_owner(binding, "9" * 5000)
            self.assertTrue(self.check(binding).errors)

    def test_each_owner_drift_missing_duplicate_type_unit_and_overflow(self):
        for binding in self.BINDINGS:
            value = self.owners[binding[2:4]][0]
            mutations = [dict(value=value+1), dict(remove=True), dict(duplicate=True),
                         dict(unit="invalid"), *[dict(value=v) for v in
                         (True, "1.5", "1.0", "01", "1e2", "0", "-1", "9223372036854775808")]]
            for change in mutations:
                with self.subTest(binding=binding, change=change):
                    self.restore()
                    self.mutate_owner(binding, **change)
                    self.assertTrue(self.check(binding).errors)

    def test_each_carrier_drift_missing_bool_fraction_type_and_overflow(self):
        for binding in self.BINDINGS:
            value = self.owners[binding[2:4]][0]
            for change in [dict(remove=True), *[dict(value=v) for v in
                           (value-1, value+1, True, value+0.5, float(value), str(value), None, [], {}, 2**63)]]:
                with self.subTest(binding=binding, change=change):
                    self.restore()
                    self.mutate_carrier(binding, **change)
                    self.assertTrue(self.check(binding).errors)

    def test_carrier_duplicate_exact_decimal_and_missing_document(self):
        binding = self.BINDINGS[-1]
        path, *_ = binding
        for raw in ('{"x-max-names": 30, "x-max-names": 30}',
                    '{"x-max-names": 30.000000000000000000000000000001}', '[]'):
            self.write(path, raw)
            self.assertTrue(self.check(binding).errors)
        (self.root / path).unlink()
        self.assertTrue(self.check(binding).errors)

    def test_actual_array_pointer_and_external_ref_base_with_all_conjuncts(self):
        binding = check_constants.P06_API_BINDINGS[1]
        value = self.owners[binding[2:4]][0]
        path = binding[0]
        self.write(path, json.dumps({"paths": {"/changes": {"get": {"parameters": [{}, {"schema": {"maximum": value}}]}}}}))
        self.assertEqual(self.check(binding).errors, [])
        binding = check_constants.P06_READER_BINDINGS[1]
        path, pointer, *_ = binding
        value = self.owners[binding[2:4]][0]
        self.write(path, '{"allOf":[{"$ref":"sub/limits.json#/$defs/reader"}]}')
        self.write("Platform/06-console/data/sub/limits.json",
                   json.dumps({"$defs": {"reader": {"allOf": [{"$ref": "next.json"}]}}}))
        target = "Platform/06-console/data/sub/next.json"
        self.write(target, json.dumps({"properties": {"members": {"maxItems": value}}}))
        self.assertEqual(self.check(binding, True).errors, [])
        self.write(path, json.dumps({"allOf": [{"$ref": "sub/limits.json#/$defs/reader"},
                   {"properties": {"members": {"maxItems": value+1}}}]}))
        self.assertTrue(self.check(binding, True).errors)
        self.write(target, '{"$ref":"next.json"}')
        self.assertTrue(self.check(binding, True).errors)

    def test_same_document_root_projection_resolves_target_before_path(self):
        binding = check_constants.P06_READER_BINDINGS[1]
        path, _, owner, name, _ = binding
        value = self.owners[(owner, name)][0]
        self.write(path, json.dumps({"allOf": [{"$ref": "#/$defs/writer"}],
                   "$defs": {"writer": {"properties": {"members": {"maxItems": value}}}}}))
        self.assertEqual(self.check(binding, True).errors, [])
        self.write(path, '{"allOf":[{"$ref":"#/$defs/writer"}],"$defs":{"writer":{"$ref":"#/$defs/writer"}}}')
        self.assertTrue(self.check(binding, True).errors)

    def test_reader_missing_projection_is_not_a_writer_equality_pass(self):
        for binding in check_constants.P06_READER_BINDINGS + check_constants.P09_READER_BINDINGS:
            with self.subTest(binding=binding):
                self.restore()
                path, pointer, *_ = binding
                doc = json.loads((self.root/path).read_text())
                parent, key = parent_at(doc, pointer)
                del parent[key]
                self.write(path, json.dumps(doc))
                self.assertTrue(self.check(binding, True).errors)

    def test_history_owner_is_independent_unique_and_exact(self):
        def check(owner, value):
            self.write(check_constants.HISTORY_OWNER, owner)
            self.write(check_constants.HISTORY_CARRIER, json.dumps({"properties": {"events": {"maxItems": value}}}))
            judge = check_constants.Judge(self.root)
            # The other two named bindings stay valid in this fixture.
            judge.domain_numeric()
            return judge.errors
        self.assertEqual(check("HISTORY_LINES: 71\n", 71), [])
        self.assertEqual(check("HISTORY_LINES: 72\n", 72), [])
        for owner, value in (("HISTORY_LINES: 71\n",72), ("HISTORY_LINES: 72\n",71),
                             ("",71), ("HISTORY_LINES: 71\nHISTORY_LINES: 71\n",71),
                             ("HISTORY_LINES: 1.5\n",1), ("HISTORY_LINES: true\n",1),
                             ("HISTORY_LINES: 9223372036854775808\n",2**63),
                             ("HISTORY_LINES: 71\n",True), ("HISTORY_LINES: 71\n",71.0)):
            with self.subTest(owner=owner, value=value):
                self.assertTrue(check(owner,value))


class EntryURLByteControls(unittest.TestCase):
    def test_independent_field_constraint_coherent_change_and_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            owner = root / "Platform/08-domain/spec/08.10-domain.norms.md"
            owner.parent.mkdir(parents=True)
            carrier = root / check_constants.API
            def check(value, copy, suffix=""):
                owner.write_text(f"ENTRY_MAX: forms/runtime-constants.tsv; bytes with class, url ≤ {value}, via, batch; rest\n" + suffix)
                carrier.write_text(json.dumps({"components": {"schemas": {"Entry": {"properties": {"url": {"x-max-bytes": copy}}}}}}))
                return check_constants.check_p08_entry_url_bytes(root)[0]
            self.assertEqual(check(317,317), [])
            self.assertEqual(check(319,319), [])
            for owner_value, copy in ((317,318),(318,317),(317,True),(317,317.0),(317,"317"),(317,None),
                                      ("true",1),("1.5",1),(2**63,2**63)):
                with self.subTest(owner=owner_value,copy=copy):
                    self.assertTrue(check(owner_value,copy))
            self.assertTrue(check(317,317,"ENTRY_MAX: forms/runtime-constants.tsv; bytes with class, url ≤ 317, via, batch; rest\n"))
            owner.write_text("")
            self.assertTrue(check_constants.check_p08_entry_url_bytes(root)[0])


class NumericSubjectHookIntegration(unittest.TestCase):
    """Execute only the tracked AST method; all checker dependencies are mocks.

    No check_spec module import, Check initialization, Source oracle or full check.
    """
    TARGETS = {
        "06-console": ("check_p06_numeric_constants",),
        "08-domain": ("check_p08_named_constants", "check_p08_entry_url_bytes"),
        "09-agent": ("check_p09_numeric_constants",),
    }
    OLD = ("check_p01_constants", "check_p06_folder_constants", "check_p08_constants")

    def invoke(self, directories=(), files=()):
        import ast
        import sys
        import types
        from unittest.mock import Mock

        path = Path(__file__).with_name("check_spec.py")
        tree = ast.parse(path.read_bytes(), filename=str(path))
        check = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Check")
        method = next(node for node in check.body if isinstance(node, ast.FunctionDef) and node.name == "check_forms")
        # Compile the actual method node, preserving every statement; do not mirror it.
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
        attrs = {node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute)
                 and isinstance(node.value, ast.Name) and node.value.id == "check_forms"}
        selectors = {node.iter.func.attr for node in ast.walk(method) if isinstance(node, ast.For)
                     and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute)
                     and isinstance(node.iter.func.value, ast.Name) and node.iter.func.value.id == "check_forms"}
        forms = types.ModuleType("check_forms")
        for name in attrs:
            setattr(forms, name, Mock(name=name, return_value=[]) if name in selectors else
                    Mock(name=name, side_effect=AssertionError("unrelated form checker executed: " + name)))
        constants = types.ModuleType("check_constants")
        names = self.OLD + tuple(name for group in self.TARGETS.values() for name in group)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for lesson in directories:
            (root / "Platform" / lesson).mkdir(parents=True)
        for lesson in files:
            dest = root / "Platform" / lesson
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("directory guard must reject files")
        payloads = {}
        for index, name in enumerate(names, 1):
            payloads[name] = ([(root / "diagnostics" / name, name + " first"),
                               (Path("relative") / name, name + " second σ")], {name + "_count": index})
            setattr(constants, name, Mock(name=name, return_value=payloads[name]))
        shell = types.SimpleNamespace(root=root, stats={"preexisting_count": 91}, errors=[])
        shell.error = Mock(side_effect=lambda path, message: shell.errors.append((path, message)))
        # check_forms reads the shared validated package rows first (Check.standard_forms, c4b8f32c2, OBSH.39);
        # the stub gives no validated tables and no selected paths, so every form selector runs on its own.
        shell.standard_forms = Mock(return_value=({}, set()))
        with patch.dict(sys.modules, {"check_forms": forms, "check_constants": constants}):
            namespace["check_forms"](shell)
        shell.standard_forms.assert_called_once_with()
        for name in selectors:
            getattr(forms, name).assert_called_once_with(root)
        for name in attrs - selectors:
            getattr(forms, name).assert_not_called()
        return shell, constants, payloads

    def assert_calls_and_forwarding(self, shell, constants, payloads, expected):
        for name in payloads:
            helper = getattr(constants, name)
            if name in expected:
                helper.assert_called_once_with(shell.root)
            else:
                helper.assert_not_called()
        errors = [error for name in expected for error in payloads[name][0]]
        stats = {"preexisting_count": 91}
        for name in expected:
            stats.update(payloads[name][1])
        self.assertEqual(shell.errors, errors)
        self.assertEqual(shell.error.call_args_list, [unittest.mock.call(*error) for error in errors])
        self.assertEqual(shell.stats, stats)

    def test_all_new_subject_errors_and_separate_counts_are_forwarded(self):
        shell, constants, payloads = self.invoke(("01-store", *self.TARGETS))
        expected = ("check_p01_constants", "check_p06_folder_constants", "check_p06_numeric_constants",
                    "check_p08_constants", "check_p08_named_constants", "check_p08_entry_url_bytes",
                    "check_p09_numeric_constants")
        self.assert_calls_and_forwarding(shell, constants, payloads, expected)

    def test_each_helper_is_called_only_for_its_own_lesson_directory(self):
        for lesson, helpers in self.TARGETS.items():
            with self.subTest(lesson=lesson):
                shell, constants, payloads = self.invoke((lesson,))
                old = {"06-console": ("check_p06_folder_constants",),
                       "08-domain": ("check_p08_constants",), "09-agent": ()}[lesson]
                self.assert_calls_and_forwarding(shell, constants, payloads, old + helpers)

    def test_missing_each_lesson_guard_excludes_only_its_helpers(self):
        order = ("check_p06_folder_constants", "check_p06_numeric_constants", "check_p08_constants",
                 "check_p08_named_constants", "check_p08_entry_url_bytes", "check_p09_numeric_constants")
        for absent, helpers in self.TARGETS.items():
            with self.subTest(absent=absent):
                shell, constants, payloads = self.invoke(tuple(lesson for lesson in self.TARGETS if lesson != absent))
                excluded = set(helpers) | {"06-console": {"check_p06_folder_constants"},
                                          "08-domain": {"check_p08_constants"}, "09-agent": set()}[absent]
                self.assert_calls_and_forwarding(shell, constants, payloads, tuple(name for name in order if name not in excluded))

    def test_absent_unrelated_or_non_directory_lessons_never_call_helpers(self):
        for directories, files in (((), ()), (("unrelated",), ()), ((), tuple(self.TARGETS))):
            with self.subTest(directories=directories, files=files):
                shell, constants, payloads = self.invoke(directories, files)
                self.assert_calls_and_forwarding(shell, constants, payloads, ())

if __name__ == "__main__":
    unittest.main()
