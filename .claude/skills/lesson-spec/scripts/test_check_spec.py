"""Regression tests for false-green risks in the document checker, not product tests."""

import tempfile
import unittest
from pathlib import Path

from check_spec import Check


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
