import copy
import json
from pathlib import Path
import tempfile
import unittest

import frictionless_forms

ROOT = Path(__file__).resolve().parents[3]
OPTIONAL_HEADERS = {
    "daemon_flags_p01": 18,
    "refusals_p01": 8,
    "runtime_constants_p01": 2,
    "write_checks_p01": 19,
    "write_checks_probes_p01": 15,
}


class OptionalFormCompatibilityControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="optional-form-compat-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package_path = self.root / frictionless_forms.PACKAGE
        names = [frictionless_forms.PACKAGE]
        for relative in frictionless_forms.KNOWN_RESOURCES.values():
            names.extend(["Platform/" + relative, "Platform/" + relative + ".schema.json"])
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        descriptor = self.package()
        descriptor["resources"] = [resource for resource in descriptor["resources"]
                                   if resource["name"] in frictionless_forms.RESOURCES]
        self.save(descriptor)

    def package(self):
        return json.loads(self.package_path.read_text(encoding="utf-8"))

    def save(self, descriptor):
        self.package_path.write_text(json.dumps(descriptor), encoding="utf-8")

    def proposal(self):
        descriptor = self.package()
        for name, relative in frictionless_forms.OPTIONAL_RESOURCES.items():
            descriptor["resources"].append({
                "name": name, "path": relative, "format": "tsv", "encoding": "utf-8",
                "dialect": {"commentChar": "#", "headerRows": [OPTIONAL_HEADERS[name]],
                            "csv": {"delimiter": "\t"}},
                "schema": relative + ".schema.json",
            })
        return descriptor

    def check(self):
        return frictionless_forms.check(self.root)

    def cell(self, name, column, value):
        path = self.root / "Platform" / frictionless_forms.KNOWN_RESOURCES[name]
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        columns = lines[header].split("\t")
        row = lines[header + 1].split("\t")
        row[columns.index(column)] = value
        lines[header + 1] = "\t".join(row)
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_actual_live_four_source_resources_stay_valid(self):
        errors, stats = frictionless_forms.check(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(stats["standard_form_tables"], len(frictionless_forms.RESOURCES))

    def test_external_nine_resource_proposal_is_valid_and_raw(self):
        self.save(self.proposal())
        tables = {}
        errors, stats = frictionless_forms.check(self.root, tables=tables)
        self.assertEqual(errors, [])
        self.assertEqual(stats["standard_form_tables"], len(frictionless_forms.KNOWN_RESOURCES))
        self.assertEqual(len(tables), len(frictionless_forms.KNOWN_RESOURCES))
        self.assertTrue(all(isinstance(value, str) for table in tables.values()
                            for row in table["rows"] for value in row))

    def test_undeclared_optional_inputs_do_not_auto_activate(self):
        for relative in frictionless_forms.OPTIONAL_RESOURCES.values():
            (self.root / "Platform" / (relative + ".schema.json")).unlink()
        errors, stats = self.check()
        self.assertEqual(errors, [])
        self.assertEqual(stats["standard_form_tables"], len(frictionless_forms.RESOURCES))

    def test_all_declared_optional_forms_are_actually_validated(self):
        self.save(self.proposal())
        for name, column, bad in [
            ("daemon_flags_p01", "type", "UNKNOWN"),
            ("refusals_p01", "surface", "unknown_surface"),
            ("runtime_constants_p01", "unit", "KiB"),
            ("write_checks_p01", "op", "UNKNOWN"),
            ("write_checks_probes_p01", "case", "unknown_case"),
        ]:
            with self.subTest(resource=name):
                path = self.root / "Platform" / frictionless_forms.KNOWN_RESOURCES[name]
                saved = path.read_bytes()
                self.cell(name, column, bad)
                errors, _ = self.check()
                self.assertTrue(any(str(path) in error and "constraint-error" in error
                                    for error in errors), errors)
                path.write_bytes(saved)

    def test_missing_mandatory_resource_refuses_even_with_optional_present(self):
        descriptor = self.proposal()
        descriptor["resources"] = [resource for resource in descriptor["resources"]
                                   if resource["name"] != "stages_p01"]
        self.save(descriptor)
        self.assertTrue(any("selected four-form group" in error for error in self.check()[0]))

    def test_unknown_or_duplicate_declared_resource_refuses(self):
        for kind in ("unknown", "duplicate"):
            with self.subTest(kind=kind):
                descriptor = self.proposal()
                extra = copy.deepcopy(descriptor["resources"][-1])
                if kind == "unknown":
                    extra["name"] = "unregistered_form"
                descriptor["resources"].append(extra)
                self.save(descriptor)
                self.assertTrue(any("closed optional form set" in error for error in self.check()[0]))

    def test_declared_optional_missing_sidecar_or_data_refuses(self):
        descriptor = self.proposal()
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
