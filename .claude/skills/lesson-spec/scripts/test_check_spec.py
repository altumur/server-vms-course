"""Regression tests for false-green risks in the document checker, not product tests."""

import tempfile
import unittest
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

from check_spec import Check, references


class CheckSpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.module = self.root / "М12A_Example"
        self.spec = self.module / "spec"
        self.spec.mkdir(parents=True)
        self.lesson = self.module / "01-example.md"
        self.lesson.write_text("# Example\n[Norms](spec/01-example.norms.md)\n")
        self.norms = self.spec / "01-example.norms.md"
        self.norms.write_text("\n".join(f"## Н{i} Section" for i in range(6)) +
                              "\n## Решает реализация\n## Чеклист готовности\n" +
                              "- [ ] **М12A/1-01** Example — проверяется чтением\n")
        (self.spec / "01-example.README.md").write_text("# Instructions\n")
        self.api = self.spec / "01-example.api.openapi.yaml"
        self.api.write_text('''openapi: 3.1.0
info: {title: Example, version: "1"}
paths:
  /example:
    get:
      responses:
        "200":
          description: Example
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Example"}
components:
  schemas:
    Example: {type: object}
''')
        self.acceptance = self.root / "Source/tests/testdata/acceptance/М12A_Example/01"
        self.acceptance.mkdir(parents=True)
        (self.acceptance / "README.md").write_text("# Acceptance\n")
        (self.acceptance / "corrections.tsv").write_text("date\tsample\tfix\tlanguages\n")
        self.scenarios = self.acceptance / "scenarios.tsv"
        self.scenarios.write_text('# scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n')

    def check(self):
        result = Check(self.root)
        result.lesson(self.lesson)
        return result

    def replace(self, path, before, after):
        text = path.read_text()
        self.assertIn(before, text)
        path.write_text(text.replace(before, after))

    def add_verdicts(self):
        (self.acceptance / "cases").mkdir()
        (self.acceptance / "cases/valid.subsystem.yaml").write_text("name: valid\n")
        # Invalid bytes belong to a deliberate negative case; the checker must not load it.
        (self.acceptance / "cases/invalid.subsystem.yaml").write_bytes(b'\xff\x00')
        (self.acceptance / "verdicts.tsv").write_text("valid\tok\ninvalid\trefused\n")
        (self.acceptance / "diagnostics.tsv").write_text('invalid\t[["field"]]\t[2]\n')

    def test_valid_letter_module_and_negative_yaml_data(self):
        self.add_verdicts()
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi"], 1)
        self.assertEqual(result.stats["verdicts"], 2)

    def test_wrong_openapi_version(self):
        self.replace(self.api, "3.1.0", "wrong")
        self.assertTrue(self.check().errors)

    def test_case_names_are_filenames_not_subsystem_identifiers(self):
        self.add_verdicts()
        (self.acceptance / "cases/valid.subsystem.yaml").rename(self.acceptance / "cases/valid_1.0_OFF.subsystem.yaml")
        self.replace(self.acceptance / "verdicts.tsv", "valid\tok", "valid_1.0_OFF\tok")
        self.assertEqual(self.check().errors, [])

    def test_invalid_openapi_shape(self):
        self.replace(self.api, 'version: "1"', 'version: 1')
        self.assertTrue(self.check().errors)

    def test_dangling_reference(self):
        self.replace(self.api, "#/components/schemas/Example", "#/components/schemas/Missing")
        self.assertTrue(self.check().errors)

    def test_external_reference_is_not_fetched(self):
        self.replace(self.api, "#/components/schemas/Example", "https://invalid.invalid/schema.json")
        self.assertTrue(self.check().errors)

    def test_duplicate_yaml_key(self):
        self.replace(self.api, "type: object", "type: object, type: string")
        self.assertTrue(self.check().errors)

    def test_missing_file_and_broken_link(self):
        self.norms.unlink()
        self.assertGreaterEqual(len(self.check().errors), 2)

    def test_duplicate_norm_id(self):
        self.norms.write_text(self.norms.read_text() + "- [ ] **М12A/1-01** Another\n")
        self.assertTrue(self.check().errors)

    def test_unfilled_template(self):
        self.lesson.write_text("# {{TITLE}}\n")
        self.assertTrue(self.check().errors)

    def test_multiline_marker_from_instruction_template(self):
        template = Path(__file__).resolve().parent.parent / "assets/instructions.md"
        marker = next(m for m in re.findall(r"\{\{.*?\}\}", template.read_text(), re.S) if "\n" in m)
        self.lesson.write_text("# Example\n" + marker + "\n")
        self.assertTrue(self.check().errors)

    def test_reference_links_all_forms(self):
        for use in ["[Norms][canon]", "[canon][]", "[canon]"]:
            for target, valid in [("spec/01-example.norms.md", True), ("spec/missing.md", False)]:
                with self.subTest(use=use, target=target):
                    self.lesson.write_text(f"# Example\n{use}\n\n[canon]: {target}\n")
                    self.assertEqual(not self.check().errors, valid)

    def test_markdown_destinations_and_code(self):
        (self.spec / "file (one).md").write_text("# Target\n")
        self.lesson.write_text(r'''# Example
[Space](<spec/file (one).md>)
[Escaped](spec/file%20\(one\).md)
`[not a link](missing.md)`
```markdown
[not a link][missing]

[missing]: missing.md
```
''')
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["local_links"], 2)

    def test_cli_fails_for_broken_reference_link(self):
        self.lesson.write_text("[Norms][canon]\n\n[canon]: spec/missing.md\n")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("check_spec.py")),
                                 "--root", str(self.root), str(self.lesson)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing link target", result.stdout)

    def test_unknown_acceptance_alongside_supported(self):
        (self.acceptance / "assertions.tsv").write_text("id\tassertion\nextra\tunknown\n")
        (self.acceptance / "README.md").write_text("[Assertions](assertions.tsv)\n")
        self.assertTrue(self.check().errors)

    def test_unlisted_case_with_another_extension(self):
        self.add_verdicts()
        (self.acceptance / "cases/unlisted.yaml").write_text("name: unlisted\n")
        self.assertTrue(self.check().errors)

    def test_case_must_be_file(self):
        self.add_verdicts()
        case = self.acceptance / "cases/valid.subsystem.yaml"
        case.unlink()
        case.mkdir()
        self.assertTrue(self.check().errors)

    def write_api(self, doc):
        self.api.write_text(yaml.safe_dump(doc, allow_unicode=True))

    def test_ref_in_payload_data_is_not_a_reference(self):
        doc = yaml.safe_load(self.api.read_text())
        data = {"$ref": "ordinary application data"}
        media = doc["paths"]["/example"]["get"]["responses"]["200"]["content"]["application/json"]
        for keyword in ["example", "examples"]:
            with self.subTest(keyword=keyword):
                media.pop("example", None)
                media.pop("examples", None)
                media[keyword] = data if keyword == "example" else {"sample": {"value": data}}
                self.write_api(doc)
                self.assertEqual(self.check().errors, [])
        schema = doc["components"]["schemas"]["Example"]
        schema.update(example=data, examples=[data], const=data, enum=[data])
        self.write_api(doc)
        self.assertEqual(self.check().errors, [])
        # The dependency has a separate limitation on object defaults; classification is still data.
        schema["default"] = data
        self.assertEqual(list(references(doc)), ["#/components/schemas/Example"])

    def test_property_names_do_not_hide_schema_references(self):
        doc = yaml.safe_load(self.api.read_text())
        schema = doc["components"]["schemas"]["Example"]
        for name in ["example", "examples", "default", "$ref"]:
            with self.subTest(name=name):
                schema["properties"] = {name: {"$ref": "#/components/schemas/Missing"}}
                self.write_api(doc)
                self.assertTrue(self.check().errors)

    def test_example_object_reference_is_checked_before_validator(self):
        doc = yaml.safe_load(self.api.read_text())
        media = doc["paths"]["/example"]["get"]["responses"]["200"]["content"]["application/json"]
        for ref in ["#/components/examples/Missing", "https://invalid.invalid/example.json"]:
            with self.subTest(ref=ref), patch("check_spec.validate") as validator:
                media["examples"] = {"sample": {"$ref": ref}}
                self.write_api(doc)
                self.assertTrue(self.check().errors)
                validator.assert_not_called()

    def test_local_reference_to_example_value(self):
        doc = yaml.safe_load(self.api.read_text())
        media = doc["paths"]["/example"]["get"]["responses"]["200"]["content"]["application/json"]
        media["examples"] = {"sample": {"$ref": "#/components/examples/Sample"}}
        doc["components"]["examples"] = {"Sample": {"value": {"$ref": "ordinary application data"}}}
        self.write_api(doc)
        self.assertEqual(self.check().errors, [])

    def test_request_body_example_payload(self):
        doc = yaml.safe_load(self.api.read_text())
        doc["paths"]["/example"]["post"] = {
            "requestBody": {"content": {"application/json": {
                "schema": {"type": "object"}, "example": {"$ref": "ordinary application data"}}}},
            "responses": {"200": {"description": "OK"}},
        }
        self.write_api(doc)
        self.assertEqual(self.check().errors, [])

    def test_nested_schema_references_are_checked(self):
        for schema in [
            {"$defs": {"Child": {"$ref": "#/missing"}}},
            {"allOf": [{"$ref": "#/missing"}]},
            {"items": {"$ref": "#/missing"}},
            {"dependentSchemas": {"example": {"$ref": "#/missing"}}},
            {"if": {"$ref": "#/missing"}},
            {"prefixItems": [{"$ref": "#/missing"}]},
        ]:
            with self.subTest(schema=schema), patch("check_spec.validate") as validator:
                doc = yaml.safe_load(self.api.read_text())
                doc["components"]["schemas"]["Example"] = schema
                self.write_api(doc)
                self.assertTrue(self.check().errors)
                validator.assert_not_called()

    def test_reference_target_in_extension_is_checked(self):
        doc = yaml.safe_load(self.api.read_text())
        doc["components"]["schemas"]["Example"] = {"$ref": "#/x-schema"}
        doc["x-schema"] = {"$ref": "https://invalid.invalid/schema.json"}
        self.write_api(doc)
        with patch("check_spec.validate") as validator:
            self.assertTrue(self.check().errors)
            validator.assert_not_called()

    def test_recursive_schema_is_supported(self):
        doc = yaml.safe_load(self.api.read_text())
        doc["components"]["schemas"]["Example"]["properties"] = {
            "next": {"$ref": "#/components/schemas/Example"}}
        self.write_api(doc)
        self.assertEqual(self.check().errors, [])

    def test_unsupported_resolution_is_explicit(self):
        for schema in [{"$id": "other.json"}, {"$dynamicRef": "#node"}, {"$schema": "https://invalid.invalid/dialect"}]:
            with self.subTest(schema=schema), patch("check_spec.validate") as validator:
                doc = yaml.safe_load(self.api.read_text())
                doc["components"]["schemas"]["Example"] = schema
                self.write_api(doc)
                self.assertTrue(any("unsupported" in error for error in self.check().errors))
                validator.assert_not_called()

    def test_dependency_does_not_fetch_ref_in_default_data(self):
        doc = yaml.safe_load(self.api.read_text())
        doc["components"]["schemas"]["Example"]["default"] = {"$ref": "https://invalid.invalid/data"}
        self.write_api(doc)
        # Known dependency limitation: a raw object default is dereferenced internally.
        # Even that traversal must not reach the network.
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")) as fetch:
            self.assertTrue(self.check().errors)
            fetch.assert_not_called()

    def test_bad_step_and_duplicate_json_key(self):
        self.scenarios.write_text('01-example\t2\tGET /example\t200 {"a":1,"a":2}\n')
        self.assertGreaterEqual(len(self.check().errors), 2)

    def test_missing_and_unlisted_case(self):
        self.add_verdicts()
        (self.acceptance / "cases/valid.subsystem.yaml").rename(self.acceptance / "cases/unlisted.subsystem.yaml")
        self.assertTrue(self.check().errors)

    def test_diagnostic_requires_refusal_and_integer_line(self):
        self.add_verdicts()
        (self.acceptance / "diagnostics.tsv").write_text('valid\t[["field"]]\t[2]\ninvalid\t[["field"]]\t[true]\n')
        self.assertEqual(len(self.check().errors), 2)

    def test_empty_and_unknown_acceptance_are_not_green(self):
        self.scenarios.write_text("# empty\n")
        self.assertTrue(self.check().errors)
        self.scenarios.unlink()
        self.assertTrue(self.check().errors)


if __name__ == "__main__":
    unittest.main()
