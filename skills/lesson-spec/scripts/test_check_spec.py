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
        self.replace(self.api, "Example: {type: object}",
                     "Example: {type: object, properties: {on: {type: string}, yes: {type: string}, "
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
                        "Example: {type: object}",
                        "Example: {type: object, properties: {" + spelling + ": {type: string}}, "
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
        self.replace(self.api, "Example: {type: object}",
                     "Example: {type: object, example: " + data + "}")
        self.assert_cli(0)

    def test_explicit_non_core_merge_is_not_silently_applied(self):
        self.replace(self.api, "Example: {type: object}",
                     "Example: {type: object, example: "
                     "{base: &base {a: 1}, child: {!!merge '<<': *base}}}")
        self.assert_cli(1, "tag:yaml.org,2002:merge")

    def test_yaml12_duplicate_symbol_string_keys_are_rejected(self):
        original = self.api.read_text()
        for symbol in ["<<", "="]:
            with self.subTest(symbol=symbol):
                self.api.write_text(original.replace(
                    "Example: {type: object}",
                    "Example: {type: object, example: {" + symbol + ': {a: 1}, "' + symbol + '": {a: 2}}}'))
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
