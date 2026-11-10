import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import check_forms
import check_spec
import check_tables
import frictionless_forms

ROOT = Path(__file__).resolve().parents[3]


class MandatoryFormControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mandatory-form-controls-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package_path = self.root / frictionless_forms.PACKAGE
        names = [frictionless_forms.PACKAGE]
        for relative in frictionless_forms.RESOURCES.values():
            names.extend(["Platform/" + relative, "Platform/" + relative + ".schema.json"])
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
    def package(self):
        return json.loads(self.package_path.read_text(encoding="utf-8"))

    def save(self, descriptor):
        self.package_path.write_text(json.dumps(descriptor), encoding="utf-8")

    def check(self):
        return frictionless_forms.check(self.root)

    def cell(self, name, column, value):
        path = self.root / "Platform" / frictionless_forms.RESOURCES[name]
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        columns = lines[header].split("\t")
        row = lines[header + 1].split("\t")
        row[columns.index(column)] = value
        lines[header + 1] = "\t".join(row)
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_actual_nine_forms_and_raw_semantic_readers(self):
        tables = {}
        errors, stats = frictionless_forms.check(ROOT, tables=tables)
        self.assertEqual(errors, [])
        self.assertEqual(stats["standard_form_tables"], 9)
        self.assertEqual(len(tables), 9)
        self.assertTrue(all(isinstance(value, str) for table in tables.values()
                            for row in table["rows"] for value in row))
        forms = ROOT / "Platform/01-store/forms"
        for name, validator in [("daemon-flags.tsv", check_forms.check_flags),
                                ("refusals.tsv", check_forms.check_refusals),
                                ("runtime-constants.tsv", check_forms.check_runtime_constants)]:
            with self.subTest(name=name):
                path = forms / name
                self.assertEqual(validator(path, validated=tables[path]), validator(path))
                self.assertEqual(validator(path, validated=tables[path])[0], [])
        checks = forms / "write-checks.tsv"
        probes = forms / "write-checks.probes.tsv"
        selected = check_tables.check(checks, validated=tables[checks], validated_probes=tables[probes])
        self.assertEqual(selected, check_tables.check(checks))
        self.assertEqual(selected[0], [])

    def test_all_five_added_forms_are_actually_validated(self):
        for name, column, bad in [
            ("daemon_flags_p01", "type", "UNKNOWN"),
            ("refusals_p01", "surface", "unknown_surface"),
            ("runtime_constants_p01", "unit", "KiB"),
            ("write_checks_p01", "op", "UNKNOWN"),
            ("write_checks_probes_p01", "case", "unknown_case"),
        ]:
            with self.subTest(resource=name):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[name]
                saved = path.read_bytes()
                self.cell(name, column, bad)
                errors, _ = self.check()
                self.assertTrue(any(str(path) in error and "constraint-error" in error
                                    for error in errors), errors)
                path.write_bytes(saved)

    def test_retired_lexical_and_primary_key_checks(self):
        cases = [
            ("daemon_flags_p01", "flag", "BAD"),
            ("daemon_flags_p01", "commands", "BAD"),
            ("refusals_p01", "name", "Bad"),
            ("refusals_p01", "code", "BAD"),
            ("runtime_constants_p01", "name", "bad"),
            ("runtime_constants_p01", "value", "00"),
            ("write_checks_p01", "id", "BAD"),
        ]
        for name, column, value in cases:
            with self.subTest(name=name, column=column):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[name]
                original = path.read_bytes()
                self.cell(name, column, value)
                errors, _ = self.check()
                self.assertTrue(any(str(path) in error and "constraint-error" in error
                                    for error in errors), errors)
                path.write_bytes(original)
        for name in ("daemon_flags_p01", "refusals_p01", "runtime_constants_p01", "write_checks_p01"):
            with self.subTest(name=name):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[name]
                original = path.read_bytes()
                lines = original.decode("utf-8").splitlines()
                header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
                path.write_bytes(original + lines[header + 1].encode("utf-8") + b"\n")
                errors, _ = self.check()
                self.assertTrue(any(str(path) in error and "primary-key" in error
                                    for error in errors), errors)
                path.write_bytes(original)

    def test_all_five_headers_and_physical_width_are_checked(self):
        for name in ("daemon_flags_p01", "refusals_p01", "runtime_constants_p01",
                     "write_checks_p01", "write_checks_probes_p01"):
            path = self.root / "Platform" / frictionless_forms.RESOURCES[name]
            original = path.read_bytes()
            lines = original.decode("utf-8").splitlines()
            header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
            for index, suffix, diagnostic in [(header, "_wrong", "label"),
                                              (header + 1, "\textra", "extra-cell"),
                                              (header + 1, None, "missing-cell"),
                                              (header + 1, "", "blank-row")]:
                with self.subTest(name=name, diagnostic=diagnostic):
                    mutant = lines[:]
                    mutant[index] = (mutant[index].rsplit("\t", 1)[0] if suffix is None
                                     else mutant[index] + suffix if suffix else "")
                    path.write_text("\n".join(mutant) + "\n", encoding="utf-8")
                    errors, _ = self.check()
                    self.assertTrue(any(str(path) in error and diagnostic in error
                                        for error in errors), errors)
            path.write_bytes(original)

    def test_retained_semantic_checks_receive_structurally_valid_mutants(self):
        forms = self.root / "Platform/01-store/forms"
        checks = forms / "write-checks.tsv"
        probes = forms / "write-checks.probes.tsv"
        shutil.copytree(ROOT / "Platform/01-store/spec", forms.parent / "spec")
        for resource, column, value, diagnostic in [
            ("daemon_flags_p01", "required", "[", "does not compile"),
            ("runtime_constants_p01", "value", "9223372036854775808", "exceeds positive int64"),
            ("runtime_constants_p01", "norm", "P/01.1-R999", "has no anchor"),
            ("write_checks_p01", "n", "999", "n must be 1"),
            ("write_checks_p01", "group", "items", "group and each go together"),
            ("write_checks_p01", "kind", "word_1", "/ kind"),
            ("write_checks_probes_p01", "n", "999", "a row of the table"),
            ("write_checks_probes_p01", "body", "{", "body is not JSON"),
        ]:
            with self.subTest(resource=resource, column=column, value=value):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
                original = path.read_bytes()
                self.cell(resource, column, value)
                tables = {}
                errors, _ = frictionless_forms.check(self.root, tables=tables)
                self.assertEqual(errors, [])
                if resource == "daemon_flags_p01":
                    errors, _ = check_forms.check_flags(path, validated=tables[path])
                elif resource == "runtime_constants_p01":
                    errors, _ = check_forms.check_runtime_constants(path, validated=tables[path])
                else:
                    errors, _ = check_tables.check(checks, validated=tables[checks],
                                                   validated_probes=tables[probes])
                self.assertTrue(any(diagnostic in error for error in errors), errors)
                path.write_bytes(original)

    def test_platform_readers_share_one_validation_and_skip_invalid_rows(self):
        platform = check_spec.Check(self.root, scope="platform")
        with mock.patch.object(frictionless_forms, "check", wraps=frictionless_forms.check) as validate:
            platform.check_tables()
            tables, selected = platform.standard_forms()
            validate.assert_called_once()
        self.assertEqual(platform.errors, [])
        self.assertEqual(set(tables), selected)
        self.assertGreater(platform.stats["check_probes"], 0)

        self.cell("write_checks_probes_p01", "case", "bad_case")
        platform = check_spec.Check(self.root, scope="platform")
        with mock.patch.object(check_tables, "check", wraps=check_tables.check) as semantic:
            platform.check_tables()
            semantic.assert_not_called()
        tables, selected = platform.standard_forms()
        self.assertEqual(tables, {})
        self.assertEqual(len(selected), 9)
        self.assertTrue(any("constraint-error" in error for error in platform.errors), platform.errors)

    def test_missing_new_resource_refuses(self):
        descriptor = self.package()
        descriptor["resources"] = [resource for resource in descriptor["resources"]
                                   if resource["name"] != "runtime_constants_p01"]
        self.save(descriptor)
        self.assertTrue(any("selected nine-form group" in error for error in self.check()[0]))

    def test_unknown_or_duplicate_declared_resource_refuses(self):
        for kind in ("unknown", "duplicate"):
            with self.subTest(kind=kind):
                descriptor = self.package()
                extra = copy.deepcopy(descriptor["resources"][-1])
                if kind == "unknown":
                    extra["name"] = "unregistered_form"
                descriptor["resources"].append(extra)
                self.save(descriptor)
                self.assertTrue(any("selected nine-form group" in error for error in self.check()[0]))

    def test_declared_missing_sidecar_or_data_refuses(self):
        descriptor = self.package()
        self.save(descriptor)
        for suffix in ("", ".schema.json"):
            with self.subTest(suffix=suffix):
                path = self.root / "Platform/01-store/forms/daemon-flags.tsv"
                path = path.with_name(path.name + suffix)
                saved = path.read_bytes()
                path.unlink()
                self.assertTrue(any("ordinary form Source file" in error for error in self.check()[0]))
                path.write_bytes(saved)

    def test_anchored_source_pattern_refuses_old_alternation_prefix_gap(self):
        self.cell("stages_kit_p01", "parts", "-x")
        self.assertTrue(any("constraint-error" in error for error in self.check()[0]))
        schema_path = self.root / "Platform/01-store/forms/stages.kit.tsv.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        field = next(field for field in schema["fields"] if field["name"] == "parts")
        pattern = field["constraints"]["pattern"]
        self.assertTrue(pattern.startswith("(?:") and pattern.endswith(")"))
        field["constraints"]["pattern"] = pattern[3:-1]
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        errors, _ = self.check()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
