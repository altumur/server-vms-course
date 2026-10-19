"""Regression tests for false-green risks in the document checker, not product tests."""

import tempfile
import unittest
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

from check_spec import Check, UniqueLoader, pointer, references


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
    Example: {type: object, additionalProperties: false}
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

    def cli(self):
        return subprocess.run([sys.executable, str(Path(__file__).with_name("check_spec.py")),
                               "--root", str(self.root), str(self.lesson)], capture_output=True, text=True)

    def assert_cli(self, code, message=None):
        result = self.cli()
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn("PASS" if code == 0 else "FAIL", result.stdout)
        if message:
            self.assertIn(message, result.stdout)

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

    def test_http_status_requires_ascii_digits(self):
        for code in ["100", "200", "299", "400", "500", "599"]:
            with self.subTest(code=code):
                self.scenarios.write_text(f"01-example\t1\tGET /example\t{code} {{}}\n")
                self.assert_cli(0)
        for digit in ["٢", "２", "२", "𝟚"]:
            for position in range(3):
                code = "200"[:position] + digit + "200"[position + 1:]
                with self.subTest(code=code):
                    self.scenarios.write_text(f"01-example\t1\tGET /example\t{code} {{}}\n")
                    self.assert_cli(1, "expected HTTP status and JSON body")
        self.scenarios.write_text("01-example\t1\tGET /example\t600 {}\n")
        self.assert_cli(1, "expected HTTP status and JSON body")

    def test_normative_ids_require_ascii_digits(self):
        original = self.norms.read_text()
        for value in ["М12A/1-0٢", "М12A/1-２0", "М12A/1-०1"]:
            with self.subTest(value=value):
                self.norms.write_text(original.replace("М12A/1-01", value))
                self.assert_cli(1, "no normative checklist ids")

    def test_lesson_filename_requires_ascii_digits(self):
        for number in ["٠1", "０1"]:
            old_stem = self.lesson.stem
            new_stem = number + "-example"
            for path in self.spec.glob(old_stem + ".*"):
                path.rename(path.with_name(path.name.replace(old_stem, new_stem, 1)))
            self.lesson.write_text(self.lesson.read_text().replace(old_stem, new_stem))
            self.lesson = self.lesson.rename(self.lesson.with_name(new_stem + ".md"))
            with self.subTest(number=number):
                self.assert_cli(1, "expected module/NN-slug.md")

    def test_case_names_are_filenames_not_subsystem_identifiers(self):
        self.add_verdicts()
        (self.acceptance / "cases/valid.subsystem.yaml").rename(self.acceptance / "cases/valid_1.0_OFF.subsystem.yaml")
        self.replace(self.acceptance / "verdicts.tsv", "valid\tok", "valid_1.0_OFF\tok")
        self.assertEqual(self.check().errors, [])

    def test_invalid_openapi_shape(self):
        self.replace(self.api, 'version: "1"', 'version: 1')
        self.assertTrue(self.check().errors)

    def test_object_schemas_say_their_openness(self):
        doc = yaml.load(self.api.read_text(), Loader=UniqueLoader)
        schemas = doc["components"]["schemas"]
        cases = [
            ({"type": "object"}, False),
            ({"type": "object", "additionalProperties": {"type": "string"}}, True),
            ({"properties": {"a": {"type": "object", "additionalProperties": True}}, "additionalProperties": False}, True),
            ({"properties": {"a": {"type": "object"}}, "additionalProperties": False}, False),
            ({"allOf": [{"$ref": "#/components/schemas/Base"}, {"properties": {"b": {"type": "string"}}}]}, False),
            ({"allOf": [{"$ref": "#/components/schemas/Base"}, {"properties": {"b": {"type": "string"}}}],
              "unevaluatedProperties": False}, True),
            ({"oneOf": [{"type": "object", "properties": {"a": {"const": 1}}},
                        {"type": "object", "properties": {"b": {"const": 2}}}], "unevaluatedProperties": False}, True),
            ({"type": "object", "additionalProperties": False, "examples": [{"type": "object"}]}, True),
            ({"type": "object", "additionalProperties": False, "not": {"required": ["a", "b"]}}, True),
        ]
        for example, valid in cases:
            with self.subTest(example=example):
                schemas["Example"] = example
                schemas.pop("Base", None)
                if "Base" in str(example):  # a base reached only as a member of a composition stays unsaid
                    schemas["Base"] = {"type": "object", "properties": {"a": {"type": "string"}}}
                self.api.write_text(yaml.safe_dump(doc, allow_unicode=True))
                errors = [e for e in self.check().errors if "openness" in e]
                self.assertEqual(not errors, valid, errors)

    def test_dangling_reference(self):
        self.replace(self.api, "#/components/schemas/Example", "#/components/schemas/Missing")
        self.assertTrue(self.check().errors)

    def test_external_reference_is_not_fetched(self):
        self.replace(self.api, "#/components/schemas/Example", "https://invalid.invalid/schema.json")
        self.assertTrue(self.check().errors)

    def test_duplicate_yaml_key(self):
        self.replace(self.api, "type: object", "type: object, type: string")
        self.assertTrue(self.check().errors)

    def test_yaml12_words_are_distinct_string_property_names(self):
        self.replace(self.api, "Example: {type: object, additionalProperties: false}",
                     "Example: {type: object, additionalProperties: false, properties: {on: {type: string}, yes: {type: string}, "
                     "off: {type: string}, no: {type: string}}}")
        self.assertEqual(self.check().errors, [])
        self.assert_cli(0)

    def test_yaml12_core_values_match_quoted_and_json_representations(self):
        value = yaml.load("{on: yes, off: no, decimal: 012, octal: 0o12, hex: 0x12, "
                          "exponent: 1e3, date: 2026-10-16, flag: true, empty: null}",
                          Loader=UniqueLoader)
        self.assertEqual(value, {"on": "yes", "off": "no", "decimal": 12, "octal": 10,
                                 "hex": 18, "exponent": 1000.0, "date": "2026-10-16",
                                 "flag": True, "empty": None})
        # The checker must not change the dependency's global scalar resolution.
        self.assertIs(yaml.safe_load("yes"), True)

    def test_yaml12_real_duplicate_string_and_resolved_integer_keys(self):
        with self.assertRaisesRegex(ValueError, "duplicate YAML key 'on'"):
            yaml.load('{on: 1, "on": 2}', Loader=UniqueLoader)
        with self.assertRaisesRegex(ValueError, "key must be a string"):
            yaml.load("{012: first, 12: second}", Loader=UniqueLoader)

    def test_yaml12_non_string_object_key_is_not_a_false_duplicate(self):
        self.replace(self.api, "type: object", "type: object, properties: {true: {type: string}}")
        self.assert_cli(1, "key must be a string")

    def test_yaml12_symbol_strings_preserve_properties_and_example_data(self):
        original = self.api.read_text()
        for symbol in ["<<", "="]:
            for spelling in [symbol, '"' + symbol + '"']:
                with self.subTest(spelling=spelling):
                    self.api.write_text(original.replace(
                        "Example: {type: object, additionalProperties: false}",
                        "Example: {type: object, additionalProperties: false, properties: {" + spelling + ": {type: string}}, "
                        "example: {" + spelling + ": {type: string}}}"))
                    schema = yaml.load(self.api.read_text(), Loader=UniqueLoader)["components"]["schemas"]["Example"]
                    expected = {symbol: {"type": "string"}}
                    self.assertEqual(schema["properties"], expected)
                    self.assertEqual(schema["example"], expected)
                    self.assert_cli(0)

    def test_yaml12_alias_under_literal_merge_key_stays_nested_data(self):
        data = "{base: &base {a: 1}, child: {<<: *base}}"
        expected = {"base": {"a": 1}, "child": {"<<": {"a": 1}}}
        self.assertEqual(yaml.load(data, Loader=UniqueLoader), expected)
        # The local Core reader must not change the dependency's global merge behavior.
        self.assertEqual(yaml.safe_load(data), {"base": {"a": 1}, "child": {"a": 1}})
        self.replace(self.api, "Example: {type: object, additionalProperties: false}",
                     "Example: {type: object, additionalProperties: false, example: " + data + "}")
        self.assert_cli(0)

    def test_explicit_non_core_merge_is_not_silently_applied(self):
        self.replace(self.api, "Example: {type: object, additionalProperties: false}",
                     "Example: {type: object, additionalProperties: false, example: "
                     "{base: &base {a: 1}, child: {!!merge '<<': *base}}}")
        self.assert_cli(1, "tag:yaml.org,2002:merge")

    def test_yaml12_duplicate_symbol_string_keys_are_rejected(self):
        original = self.api.read_text()
        for symbol in ["<<", "="]:
            with self.subTest(symbol=symbol):
                self.api.write_text(original.replace(
                    "Example: {type: object, additionalProperties: false}",
                    "Example: {type: object, additionalProperties: false, example: {" + symbol + ': {a: 1}, "' + symbol + '": {a: 2}}}'))
                self.assert_cli(1, "duplicate YAML key")

    def test_yaml_non_json_scalar_does_not_pass(self):
        original = self.api.read_text()
        for value in [".nan", ".inf", "!!timestamp 2026-10-16"]:
            with self.subTest(value=value):
                self.api.write_text(original.replace("type: object", "type: object, default: " + value))
                self.assert_cli(1)

    def test_missing_file_and_broken_link(self):
        self.norms.unlink()
        self.assertGreaterEqual(len(self.check().errors), 2)

    def test_duplicate_norm_id(self):
        self.norms.write_text(self.norms.read_text() + "- [ ] **М12A/1-01** Another\n")
        self.assertTrue(self.check().errors)

    def test_code_cannot_supply_required_heading(self):
        original = self.norms.read_text()
        for fake in ["```markdown\n## Н4 Section\n```", "    ## Н4 Section",
                     "> ## Н4 Section", "`## Н4 Section`"]:
            with self.subTest(fake=fake):
                self.norms.write_text(original.replace("## Н4 Section", fake))
                self.assert_cli(1, "expected Н0–Н5")

    def test_entire_norms_in_example_are_not_structure(self):
        original = self.norms.read_text()
        for fake in ["```markdown\n" + original + "\n```\n",
                     "\n".join("    " + line for line in original.splitlines()),
                     "\n".join("> " + line for line in original.splitlines())]:
            with self.subTest(fake=fake[:20]):
                self.norms.write_text(fake)
                self.assert_cli(1, "no normative checklist ids")

    def test_checklist_id_must_be_real_list_and_strong_text(self):
        original = self.norms.read_text()
        item = "- [ ] **М12A/1-01** Example — проверяется чтением"
        for fake in ["```markdown\n" + item + "\n```", "    " + item,
                     "- `[ ] **М12A/1-01**` Example", "[ ] **М12A/1-01** Example",
                     "> " + item]:
            with self.subTest(fake=fake):
                self.norms.write_text(original.replace(item, fake))
                self.assert_cli(1, "no normative checklist ids")

    def test_markdown_structure_accepts_rendered_variants_and_ignores_examples(self):
        original = self.norms.read_text()
        self.norms.write_text(original.replace("## Н4 Section", "Н4 Section\n----------")
                              .replace("- [ ] **", "* [x] __").replace("-01**", "-01__") +
                              "\n```markdown\n## Н4 Section\n- [ ] **М12A/1-01** Fake duplicate\n```\n")
        self.assert_cli(0)
        self.assertEqual(self.check().stats["norm_ids"], 1)

    def test_checklist_ids_outside_its_section_do_not_supply_checklist(self):
        original = self.norms.read_text()
        self.norms.write_text(original.replace("## Чеклист готовности\n", "") +
                              "\n## Чеклист готовности\nNo items yet.\n")
        self.assert_cli(1, "no normative checklist ids")

    def test_checklist_ends_at_same_or_higher_heading(self):
        original = self.norms.read_text()
        for heading in ["# Appendix", "Appendix\n========", "## Appendix"]:
            with self.subTest(heading=heading):
                self.norms.write_text(original.replace("## Чеклист готовности\n",
                                      "## Чеклист готовности\nNo items.\n\n" + heading + "\n"))
                self.assert_cli(1, "no normative checklist ids")

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
        self.assert_cli(1, "missing link target")

    def test_cli_pointer_array_indices(self):
        doc = yaml.safe_load(self.api.read_text())
        doc["components"]["schemas"]["List"] = {"prefixItems": [{"type": "string"}, {"type": "integer"}]}
        for index in ["0", "1", "2", "-1", "01", "+1", " 1", "1 ", "1_0", "\u0661", "-", ""]:
            with self.subTest(index=index):
                doc["components"]["schemas"]["Example"] = {
                    "$ref": "#/components/schemas/List/prefixItems/" + index}
                self.write_api(doc)
                self.assert_cli(0 if index in {"0", "1"} else 1)

    def test_cli_pointer_escape_sequences(self):
        doc = yaml.safe_load(self.api.read_text())
        doc.update({"x-target~2": {"type": "object"}, "x-target~": {"type": "string"},
                    "x-target/child": {"type": "integer"}})
        for ref, valid in [("#/x-target~2", False), ("#/x-target~", False),
                           ("#/x-target~02", True), ("#/x-target~0", True), ("#/x-target~1child", True)]:
            with self.subTest(ref=ref):
                doc["components"]["schemas"]["Example"] = {"$ref": ref}
                self.write_api(doc)
                self.assert_cli(0 if valid else 1)

    def test_pointer_uri_decoding_and_object_tokens(self):
        doc = {"": "empty", "a/b": "slash", "~1": "tilde", "01": "zero", "-1": "minus",
               "%": "percent", "%FF": "literal percent", "\ufffd": "replacement", "\u044f": "utf8"}
        for ref, expected in [("#/", "empty"), ("#/a~1b", "slash"), ("#/~01", "tilde"),
                              ("#/01", "zero"), ("#/-1", "minus"), ("#/%25", "percent"),
                              ("#/%25FF", "literal percent"), ("#/%D1%8F", "utf8"), ("#%2F01", "zero")]:
            with self.subTest(ref=ref):
                self.assertEqual(pointer(doc, ref), expected)
        self.assertIs(pointer(doc, "#"), doc)
        for ref in ["#/%", "#/%FF", "#/%D1", "#/~", "#/~2", "#anchor", "#/01/0"]:
            with self.subTest(ref=ref), self.assertRaises((ValueError, KeyError, TypeError)):
                pointer(doc, ref)

    def test_cli_markdown_images_all_forms(self):
        (self.spec / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        for use in ["![Diagram]({target})", "![Diagram][image]\n\n[image]: {target}",
                    "![image][]\n\n[image]: {target}", "![image]\n\n[image]: {target}"]:
            for target, valid in [("spec/diagram.svg", True), ("spec/missing.svg", False)]:
                with self.subTest(use=use, target=target):
                    self.lesson.write_text("# Example\n" + use.format(target=target) + "\n")
                    self.assert_cli(0 if valid else 1)

    def test_cli_raw_html_is_explicitly_unsupported(self):
        for html in ['<a href="spec/missing.norms.md">Norms</a>',
                     '<a href="spec/01-example.norms.md">Norms</a>',
                     '<img src="spec/missing.svg">', '<div>text</div>',
                     '<!-- comment -->']:
            with self.subTest(html=html):
                self.lesson.write_text("# Example\n" + html + "\n")
                self.assert_cli(1, "unsupported raw HTML")

    def test_html_and_images_in_code_are_examples(self):
        self.lesson.write_text('''# Example
`<a href="missing.md">not a link</a>`
`![not an image](missing.svg)`
```html
<img src="missing.svg">
```
''')
        self.assert_cli(0)

    def test_image_alt_is_not_independent_link_or_html(self):
        (self.spec / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.lesson.write_text('![Caption [text](missing.md) <b>text</b>](spec/diagram.svg)\n')
        self.assert_cli(0)

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
                "schema": {"type": "object", "additionalProperties": False}, "example": {"$ref": "ordinary application data"}}}},
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

    def test_diagnostic_path_takes_list_indexes_as_integers(self):
        self.add_verdicts()
        (self.acceptance / "diagnostics.tsv").write_text('invalid\t[["unit", "fields", 0]]\t[2]\n')
        self.assertEqual(self.check().errors, [])
        (self.acceptance / "diagnostics.tsv").write_text('invalid\t[["unit", -1], ["unit", true]]\t[2]\n')
        self.assertEqual(len(self.check().errors), 1)

    def test_classes_name_refused_cases_with_a_known_class(self):
        self.add_verdicts()
        classes = self.acceptance / "classes.tsv"
        classes.write_text("# case\tclass\ninvalid\tvalue\n")
        self.assertEqual(self.check().errors, [])
        classes.write_text("valid\tvalue\ninvalid\tsyntax\n")
        self.assertEqual(len(self.check().errors), 2)

    # Form schema next to the norm (ADR-0085): a closed root of one key and no reference rows.
    SCHEMA = """$schema: https://json-schema.org/draft/2020-12/schema
type: object
required: [name]
additionalProperties: false
properties:
  name: {type: string}
"""

    def add_schema(self, verdicts="valid\tok\nextra\trefused\n", classes="extra\tkey\n"):
        (self.spec / "01-example.schema.yaml").write_text(self.SCHEMA)
        (self.spec / "01-example.references.tsv").write_text("path\tcheck\tclass\tnorm\n")
        (self.acceptance / "cases").mkdir()
        (self.acceptance / "cases/valid.subsystem.yaml").write_text("name: valid\n")
        (self.acceptance / "cases/extra.subsystem.yaml").write_text("name: extra\nextra: 1\n")
        (self.acceptance / "verdicts.tsv").write_text(verdicts)
        (self.acceptance / "classes.tsv").write_text(classes)

    def test_form_schema_refuses_an_extra_key_as_key(self):
        self.add_schema()
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["schema_cases"], 2)
        # The course schema of М10/2 refuses an unknown root key in an accepted corpus case, class key.
        from spec_schema.run import Runner
        course = Path(__file__).resolve().parents[3]
        corpus = course / "Source/tests/testdata/acceptance/М10_Platform/02"
        case = corpus / "cases/base.subsystem.yaml"
        self.assertIn("\nbase\tok\n", (corpus / "verdicts.tsv").read_text())
        runner = Runner()
        self.assertEqual(runner.judge(case.read_bytes())["verdict"], "ok")
        got = runner.judge(case.read_bytes() + b"extra_section: 1\n")
        self.assertEqual((got["verdict"], got["class"], got["layer"]), ("refused", "key", "schema"))

    def test_form_schema_verdict_or_class_difference_fails(self):
        self.add_schema(verdicts="valid\tok\nextra\tok\n", classes="")
        (self.acceptance / "classes.tsv").unlink()
        errors = self.check().errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("extra.subsystem.yaml: form schema: verdict expected ok, got refused (layer schema", errors[0])
        self.assert_cli(1, "verdict expected ok, got refused")
        (self.acceptance / "verdicts.tsv").write_text("valid\tok\nextra\trefused\n")
        (self.acceptance / "classes.tsv").write_text("extra\tvalue\n")
        errors = self.check().errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("class expected value, got key (layer schema", errors[0])

    def test_form_schema_outside_profile_or_alone_fails(self):
        self.add_schema()
        self.replace(self.spec / "01-example.schema.yaml", "type: object", "type: object\nminProperties: 1")
        self.assertIn("keyword minProperties is outside the profile", "\n".join(self.check().errors))
        (self.spec / "01-example.references.tsv").unlink()
        self.assertIn("needs both .schema.yaml and .references.tsv", "\n".join(self.check().errors))

    def test_form_schema_without_dependencies_fails_with_the_install_command(self):
        self.add_schema()
        with patch.dict(sys.modules, {"spec_schema": None, "spec_schema.run": None}):
            errors = self.check().errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("form schema check needs jsonschema, ruamel.yaml and regress", errors[0])
        self.assertIn("uv run --no-project", errors[0])

    def write_catalog(self, *rows):
        path = self.root / "Platform/common/data/catalog.tsv"
        path.parent.mkdir(parents=True, exist_ok=True)
        header = "key\tkind\towner\tops\treaders\twhen\tversion\tschema\tnorm\n"
        path.write_text("# catalog\n" + header + "".join("\t".join(row) + "\n" for row in rows))

    def data(self, *lines):
        text = self.norms.read_text().replace("## Н1 Section\n", "## Н1 Section\n**Данные**:\n" + "".join(l + "\n" for l in lines) + "\n")
        self.norms.write_text(text)

    SLOT = ["<sub>/slots/<имя>", "row", "М12A/1",
            'create=<s>worker(cas "", имя свободно),<s>controller(только предложение); cas=<s>worker(своё имя), <s>controller(release)',
            "<s>controller, console", "-", "1", "-", "М12A/1 Н1"]

    def test_catalog_and_data_paragraph_agree(self):
        self.write_catalog(self.SLOT, ["platform/spec/<sub>", "row", "М12A/1", "put=admin", "*", "-", "1", "-", "М12A/1 Н1"])
        self.data("- владеет: `<sub>/slots/<имя>`, `platform/spec/<sub>`;", "- пишет: `<sub>/slots/<имя>` (cas);")
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["catalog_rows"], 2)
        self.assertEqual(result.stats["data_paragraphs"], 1)

    def test_catalog_ops_grammar_and_overlap(self):
        bad_semicolon = list(self.SLOT); bad_semicolon[0] = "a/<x>"; bad_semicolon[3] = "cas=<s>worker(одно; другое)"
        bad_op = list(self.SLOT); bad_op[0] = "b/<x>"; bad_op[3] = "upsert=console"
        bad_role = list(self.SLOT); bad_role[0] = "c/<x>"; bad_role[4] = "operator"
        twin = list(self.SLOT); twin[0] = "<sub>/slots/<id>"
        self.write_catalog(self.SLOT, bad_semicolon, bad_op, bad_role, twin)
        self.data("- владеет: `<sub>/slots/<имя>`, `<sub>/slots/<id>`;")
        errors = "\n".join(self.check().errors)
        self.assertIn("participants of cas", errors)
        self.assertIn("operation 'upsert'", errors)
        self.assertIn("readers: expected role", errors)
        self.assertIn("overlap with equal narrowness", errors)

    def test_catalog_spec_variables_conditional_readers_and_kinds(self):
        units = ["<sub>/<spec:unit.rows>/<id>", "row", "М12A/1", "guard=console(cas по версии строки)", "<s>worker(при door.routes), console", "-", "1", "-", "М12A/1 Н1"]
        tables = ["<sub>/<spec:tables>/<имя>", "row", "М12A/1", "put=console", "*", "-", "1", "-", "М12A/1 Н1"]
        pointer = ["domain/shared", "row", "М12A/1", "cas=domain", "configstore-door, proc:02-installer", "-", "1", "-", "М12A/1 Н1"]
        copy = ["domain/shared", "object", "М12A/1", "put=domainagent", "*", "-", "1", "-", "М12A/1 Н1"]
        bad = ["<sub>/<spec:Bad>/<x>", "row", "М12A/1", "put=console", "*", "-", "1", "-", "М12A/1 Н1"]
        self.write_catalog(units, tables, pointer, copy, bad)
        self.data("- владеет: `<sub>/<spec:unit.rows>/<id>`, `<sub>/<spec:tables>/<имя>`, `domain/shared`;")
        errors = self.check().errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("spec variable", errors[0])

    def test_data_paragraph_must_match_catalog(self):
        self.write_catalog(self.SLOT)
        self.data("- владеет: `nothing/here`;", "- пишет: `<sub>/slots/<имя>` (delete);")
        errors = "\n".join(self.check().errors)
        self.assertIn("nothing/here is not in the catalog", errors)
        self.assertIn("write (delete) is not among the catalog ops", errors)
        self.assertIn("the catalog says ['<sub>/slots/<имя>']", errors)
        self.norms.write_text(self.norms.read_text().replace("**Данные**", "**Иное**"))
        self.assertIn("no «Данные» paragraph", "\n".join(self.check().errors))

    def test_empty_and_unknown_acceptance_are_not_green(self):
        self.scenarios.write_text("# empty\n")
        self.assertTrue(self.check().errors)
        self.scenarios.unlink()
        self.assertTrue(self.check().errors)

    def registry(self, rows):
        path = self.root / "exceptions.tsv"
        path.write_text("# lesson\tkind\tvalue\treason\n" + "".join("\t".join(row) + "\n" for row in rows))
        result = Check(self.root, path)
        result.lesson(self.lesson)
        return result

    def test_no_acceptance_for_a_lesson_whose_acceptance_moved(self):
        result = self.registry([("М12A_Example/01", "no-acceptance", "-", "moved")])
        self.assertTrue(any("stale exception no-acceptance" in e for e in result.errors), result.errors)
        self.scenarios.unlink()
        self.assertTrue(any("no supported acceptance table" in e for e in self.registry([]).errors))
        result = self.registry([("М12A_Example/01", "no-acceptance", "-", "moved")])
        self.assertFalse([e for e in result.errors if "acceptance" in e], result.errors)
        self.assertTrue(any("no-acceptance" in line for line in result.excepted))

    def test_stated_counts_must_match_the_tables(self):
        instructions = self.spec / "01-example.README.md"
        for text, valid in [("Пройти 1 сценарий / 1 шаг.", True), ("Пройти 2 сценария / 1 шаг.", False),
                            ("Пройти 1 сценарий/3 шага.", False), ("Все сценарии scenarios.tsv (01–01).", True),
                            ("Все сценарии scenarios.tsv (01–02).", False), ("Пройти М12A/1-01…01.", True),
                            ("Пройти М12A/1-01…02.", False), ("Все 1 id имеют свидетельства.", True),
                            ("Все 2 id имеют свидетельства.", False), ("Для 2 пунктов чеклиста.", False),
                            ("Проверены все 2 норм.", False), ("Срок 25 с, 3 попытки.", True)]:
            with self.subTest(text=text):
                instructions.write_text(f"# Instructions\n{text}\n")
                self.assertEqual(not self.check().errors, valid, self.check().errors)

    def test_norms_may_name_a_subset_of_checklist_ids(self):
        self.replace(self.norms, "## Н5 Section", "## Н5 Section\nТаблица: М12A/1-01…03 — гонки.")
        self.assertFalse(self.check().errors)

    def test_registry_allows_named_deviations_and_reports_them(self):
        self.api.unlink()
        (self.acceptance / "extra.tsv").write_text("x\n")
        self.scenarios.write_text("scenario\tstep\trequest\texpect\n01-example\t1\t@start x\tok\n")
        self.assertGreaterEqual(len(self.check().errors), 4)
        result = self.registry([("М12A_Example/01", "no-openapi", "-", "ADR"),
                                ("М12A_Example/01", "acceptance-entry", "extra.tsv", "README"),
                                ("М12A_Example/01", "scenarios-format", "own", "README")])
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.excepted), 3)

    def test_registry_rows_that_are_no_longer_needed_fail(self):
        result = self.registry([("М12A_Example/01", "no-openapi", "-", "ADR"),
                                ("М12A_Example/01", "acceptance-entry", "extra.tsv", "README"),
                                ("М12A_Example/01", "scenarios-format", "own", "README"),
                                ("М12A_Example/02", "no-openapi", "-", "another lesson is not checked here")])
        self.assertEqual(len(result.errors), 3, result.errors)
        self.assertTrue(all("stale exception" in error for error in result.errors))

    def test_registry_rows_need_a_known_kind_and_a_reason(self):
        for row in [("М12A_Example/01", "anything", "-", "reason"), ("М12A_Example/01", "no-openapi", "-", "")]:
            with self.subTest(row=row):
                self.assertTrue(self.registry([row]).errors)

    def test_registry_rows_the_lesson_does_not_use_are_stale(self):
        result = self.registry([("М12A_Example/01", "scenarios-format", "own", "README")])
        self.assertTrue(any("stale exception scenarios-format" in e for e in result.errors), result.errors)
        result = self.registry([("М12A_Example/01", "acceptance-entry", "README.md", "supported anyway")])
        self.assertTrue(any("supported without it" in e for e in result.errors), result.errors)

    def test_own_format_keeps_structure_errors(self):
        self.scenarios.write_text("scenario\tstep\trequest\texpect\n01-a\t1\t@start x\tok\n01-a\t3\t@stop x\tok\n")
        result = self.registry([("М12A_Example/01", "scenarios-format", "own", "README")])
        self.assertEqual(len(result.errors), 1, result.errors)
        self.assertIn("invalid scenario/step sequence", result.errors[0])
        self.scenarios.write_text("scenario\tstep\trequest\texpect\n01-a\t1\t@start x\tok\textra\n")
        result = self.registry([("М12A_Example/01", "scenarios-format", "own", "README")])
        self.assertTrue(any("expected 4 TSV columns" in e for e in result.errors), result.errors)

    def test_counts_leave_out_a_header_row(self):
        self.scenarios.write_text("scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n")
        result = self.check()
        self.assertEqual((result.stats["scenarios"], result.stats["steps"]), (1, 1))

    def test_verdict_corpus_phrases_and_n5_rows_match_the_tables(self):
        self.scenarios.unlink()
        self.add_verdicts()
        verdicts = [v for v in (self.acceptance / "verdicts.tsv").read_text().split()[1::2]]
        total, ok = len(verdicts), verdicts.count("ok")
        readme = self.acceptance / "README.md"
        for text, valid in [(f"Корпус: {total} файлов, {ok} ok/{total - ok} refused.", True),
                            (f"Корпус: {total + 1} файлов, {ok} ok/{total - ok + 1} refused.", False)]:
            with self.subTest(text=text):
                readme.write_text(f"# Acceptance\n{text}\n")
                self.assertEqual(not self.check().errors, valid, self.check().errors)
        readme.write_text("# Acceptance\n")
        self.scenarios.write_text('# scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n')
        for row, valid in [("| 01 | пример |", True), ("| 02 | нет такого |", False)]:
            with self.subTest(row=row):
                self.replace(self.norms, "## Н5 Section", f"## Н5 Section\n| № | что |\n|---|---|\n{row}")
                self.assertEqual(not self.check().errors, valid, self.check().errors)
                self.replace(self.norms, f"## Н5 Section\n| № | что |\n|---|---|\n{row}", "## Н5 Section")

    def test_counts_read_the_bracket_form_and_skip_code_and_subsets(self):
        self.scenarios.unlink()
        self.add_verdicts()
        readme = self.acceptance / "README.md"
        for text, valid in [("Корпус: 2 файла, `ok` (1), `refused` (1).", True),
                            ("Корпус: 2 файла, `ok` (2), `refused` (0).", False),
                            ("```\nКорпус: 9 файлов, 1 ok/8 refused.\n```", True),
                            ("Например, 9 файлов, 1 ok/8 refused.", True)]:
            with self.subTest(text=text):
                readme.write_text(f"# Acceptance\n{text}\n")
                self.assertEqual(not self.check().errors, valid, self.check().errors)

    def test_every_scenario_has_a_row_in_the_n5_table(self):
        self.scenarios.write_text("# scenario\tstep\trequest\texpect\n01-a\t1\tGET /example\t200 {}\n"
                                  "02-b\t1\tGET /example\t200 {}\n")
        self.replace(self.norms, "## Н5 Section", "## Н5 Section\n| № | что |\n|---|---|\n| 01 | a |")
        self.assertTrue(any("scenario 02" in e for e in self.check().errors), self.check().errors)

    def test_directives_are_in_the_stand_dictionary(self):
        stand = self.acceptance / "README.md"
        stand.write_text("# Acceptance\n## Стенд\n### Словарь директив\n- `@start` — запустить процесс.\n")
        self.scenarios.write_text("# scenario\tstep\trequest\texpect\n01-a\t1\tGET /example\t200 {}\n")
        self.assertFalse(self.check().errors)
        self.scenarios.write_text("# scenario\tstep\trequest\texpect\n01-a\t1\tGET /example?x=a@b\t200 {}\n"
                                  "01-a\t2\t@stop x\t200 {}\n")
        errors = self.registry([("М12A_Example/01", "scenarios-format", "own", "README")]).errors
        self.assertEqual([e for e in errors if "directive" in e][:1] and len([e for e in errors if "directive" in e]), 1,
                         errors)

    def test_directives_join_the_shared_m10_dictionary_and_the_modules_own(self):
        shared = self.root / "Source/tests/testdata/acceptance/М10_Platform/01/README.md"
        shared.parent.mkdir(parents=True)
        shared.write_text("# Acceptance\n## Стенд\n### Словарь директив\n- `@start` — запустить процесс.\n")
        (self.acceptance / "README.md").write_text("# Acceptance\n## Стенд\n### Словарь директив\n- `@cut` — разрыв.\n")
        self.scenarios.write_text("# scenario\tstep\trequest\texpect\n01-a\t1\t@start x\t200 {}\n01-a\t2\t@cut m1\t200 {}\n")
        self.assertFalse([e for e in self.check().errors if "directive" in e])
        self.scenarios.write_text("# scenario\tstep\trequest\texpect\n01-a\t1\t@join m1\t200 {}\n")
        self.assertEqual(len([e for e in self.check().errors if "directive @join" in e]), 1, self.check().errors)

    def test_choice_counts_match_the_numbered_items(self):
        self.replace(self.norms, "## Решает реализация\n", "## Решает реализация\n1. одно\n2. другое\n")
        instructions = self.spec / "01-example.README.md"
        for text, valid in [("Названы 2 выбора реализации.", True), ("Названы 3 выбора реализации.", False)]:
            with self.subTest(text=text):
                instructions.write_text(f"# Instructions\n{text}\n")
                self.assertEqual(not self.check().errors, valid, self.check().errors)

    def test_cli_names_exceptions_and_keeps_them_out_of_pass(self):
        self.api.unlink()
        registry = self.root / "exceptions.tsv"
        registry.write_text("М12A_Example/01\tno-openapi\t-\tADR\n")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("check_spec.py")), "--root",
                                 str(self.root), "--exceptions", str(registry), str(self.lesson)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EXCEPTION М12A_Example/01 no-openapi -: ADR", result.stdout)
        self.assertIn("PASS with 1 exceptions", result.stdout)


if __name__ == "__main__":
    unittest.main()


class PlatformLessonTests(unittest.TestCase):
    """A lesson of the Platform module: chapters spec/NN.K-<процесс>.norms.md, acceptance/K/ per chapter."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.dir = self.root / "Platform/01-store"
        self.spec = self.dir / "spec"
        self.spec.mkdir(parents=True)
        self.lesson = self.dir / "01-store.md"
        self.lesson.write_text("# Store\n")
        self.readme = self.spec / "01-store.README.md"
        self.readme.write_text("# Instructions\n")
        for chapter in ("1", "2"):
            (self.spec / f"01.{chapter}-store.norms.md").write_text(
                "\n".join(f"## Н{i} Section" for i in range(6)) +
                "\n## Решает реализация\n## Чеклист готовности\n" +
                f"- [ ] **P/01.{chapter}-01** Example — проверяется чтением\n")
            acceptance = self.dir / "acceptance" / chapter
            acceptance.mkdir(parents=True)
            (acceptance / "README.md").write_text("# Acceptance\n")
            (acceptance / "corrections.tsv").write_text("date\tsample\tfix\tlanguages\n")
            (acceptance / "scenarios.tsv").write_text(
                "# scenario\tstep\trequest\texpect\n01-example\t1\tGET /example\t200 {}\n")
        (self.spec / "01-store.api.openapi.yaml").write_text(self.API)

    API = '''openapi: 3.1.0
info: {title: Store, version: "1"}
paths:
  /example:
    get:
      responses:
        "200":
          description: Example
          content:
            application/json:
              schema: {type: object, additionalProperties: false}
'''

    def check(self):
        result = Check(self.root)
        result.lesson(self.lesson)
        return result

    def test_two_chapters_pass(self):
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["norm_ids"], 2)
        self.assertEqual(result.stats["lessons"], 1)

    def test_foreign_chapter_id(self):
        path = self.spec / "01.1-store.norms.md"
        path.write_text(path.read_text().replace("P/01.1-01", "P/01.2-01"))
        self.assertTrue(any("foreign checklist id P/01.2-01" in e for e in self.check().errors))

    def test_chapter_without_sections(self):
        (self.spec / "01.2-store.norms.md").write_text("## Чеклист готовности\n- [ ] **P/01.2-01** x\n")
        self.assertTrue(any("01.2-store.norms.md: expected Н0–Н5" in e for e in self.check().errors))

    def test_unsupported_chapter_acceptance_entry(self):
        (self.dir / "acceptance/2/notes.txt").write_text("x\n")
        self.assertTrue(any("notes.txt: unsupported acceptance entry" in e for e in self.check().errors))

    def test_entry_outside_chapter_directories(self):
        (self.dir / "acceptance/3").mkdir()
        self.assertTrue(any("only chapter directories" in e for e in self.check().errors))

    def test_lesson_scenario_count_is_the_sum_of_chapters(self):
        self.readme.write_text("# Instructions\n3 сценария / 2 шага.\n")
        self.assertTrue(any("says 3 scenarios, the tables have 2" in e for e in self.check().errors))
        self.readme.write_text("# Instructions\n2 сценария / 2 шага.\n")
        self.assertEqual(self.check().errors, [])

    def test_own_scenario_grammar_is_excepted_per_chapter(self):
        (self.dir / "acceptance/2/scenarios.tsv").write_text(
            "# scenario\tstep\trequest\texpect\n01-example\t1\t@own directive\t200 {}\n")
        self.assertTrue(self.check().errors)
        registry = self.root / "exceptions.tsv"
        registry.write_text("P/01\tscenarios-format\t2/own\tchapter grammar\n")
        result = Check(self.root, registry)
        result.lesson(self.lesson)
        self.assertEqual(result.errors, [])
        registry.write_text("P/01\tscenarios-format\t1/own\tchapter grammar\n")
        result = Check(self.root, registry)
        result.lesson(self.lesson)
        self.assertTrue(any("stale exception scenarios-format 1/own" in e for e in result.errors), result.errors)

    def test_chapter_with_only_an_excepted_entry(self):
        acceptance = self.dir / "acceptance/2"
        (acceptance / "scenarios.tsv").unlink()
        (acceptance / "puts.tsv").write_text("x\n")
        self.assertTrue(any("no supported acceptance table" in e for e in self.check().errors))
        registry = self.root / "exceptions.tsv"
        registry.write_text("P/01\tacceptance-entry\t2/puts.tsv\tchecked by the README\n")
        result = Check(self.root, registry)
        result.lesson(self.lesson)
        self.assertFalse([e for e in result.errors if "acceptance" in e], result.errors)

    def test_whole_and_chapter_norms_conflict(self):
        (self.spec / "01-store.norms.md").write_text("# x\n")
        self.assertTrue(any("either one norms file or chapter norms" in e for e in self.check().errors))


class FormSourceChapterTests(unittest.TestCase):
    """Глава Platform-урока с источником формы ADR-0087: раздел байт в байт, корпус через построенный загрузчик."""

    def setUp(self):
        from test_form_source import FORM, REFS, SCALARS
        from form_source import build_section
        from form_source.section import BEGIN, END
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.dir = self.root / "Platform/02-installer"
        self.spec = self.dir / "spec"
        self.spec.mkdir(parents=True)
        self.lesson = self.dir / "02-installer.md"
        self.lesson.write_text("# Installer\n")
        (self.spec / "02-installer.README.md").write_text("# Instructions\n")
        base = self.spec / "02.1-installer"
        for suffix, text in ((".form.yaml", FORM), (".references.tsv", REFS), (".scalars.tsv", SCALARS)):
            Path(str(base) + suffix).write_text(text, encoding="utf-8")
        section = build_section(*(Path(str(base) + s) for s in (".form.yaml", ".references.tsv", ".scalars.tsv")))
        self.norms = self.spec / "02.1-installer.norms.md"
        self.norms.write_text("\n".join(f"## Н{i} Section" for i in range(6)) + "\n" + BEGIN + "\n" + section + END + "\n" +
                              "## Решает реализация\n## Чеклист готовности\n" +
                              "- [ ] **P/02.1-01** Example — проверяется чтением\n")
        self.acceptance = self.dir / "acceptance/1"
        (self.acceptance / "cases").mkdir(parents=True)
        (self.acceptance / "README.md").write_text("# Acceptance\n")
        (self.acceptance / "corrections.tsv").write_text("date\tsample\tfix\tlanguages\n")
        (self.acceptance / "verdicts.tsv").write_text("good\tok\nbad\trefused\n")
        (self.acceptance / "cases/good.subsystem.yaml").write_text("name: a\n")
        (self.acceptance / "cases/bad.subsystem.yaml").write_text("name: a\nzz: 1\n")
        (self.spec / "02-installer.api.openapi.yaml").write_text(PlatformLessonTests.API)

    def check(self):
        result = Check(self.root)
        result.lesson(self.lesson)
        return result

    def test_pass(self):
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual((result.stats["form_cases"], result.stats["form_rows"]), (2, 3))

    def test_section_must_match(self):
        self.norms.write_text(self.norms.read_text().replace("| `tmpl` | строка |", "| `tmpl` | слово |"))
        self.assertTrue(any("section differs" in e for e in self.check().errors))

    def test_corpus_through_the_loader(self):
        (self.acceptance / "verdicts.tsv").write_text("good\tok\nbad\tok\n")
        self.assertTrue(any("verdict expected ok, got refused" in e for e in self.check().errors))
        (self.acceptance / "verdicts.tsv").write_text("good\tok\nbad\trefused\n")
        (self.acceptance / "classes.tsv").write_text("bad\tvalue\n")
        self.assertTrue(any("class expected value, got key" in e for e in self.check().errors))
        (self.acceptance / "classes.tsv").unlink()
        (self.acceptance / "diagnostics.tsv").write_text('bad\t[["aa"]]\t[]\n')
        self.assertTrue(any("paths expected" in e for e in self.check().errors))

    def test_pair_and_source_conflict(self):
        (self.spec / "02.1-installer.schema.yaml").write_text("{}\n")
        self.assertTrue(any("not both" in e for e in self.check().errors))

    def test_strict_coverage(self):
        result = Check(self.root, strict_coverage=True)
        result.lesson(self.lesson)
        self.assertTrue(any("sole cause" in e for e in result.errors))

