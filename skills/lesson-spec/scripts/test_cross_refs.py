"""Cross-file $ref between Platform contracts (lesson 6 transfer plan, В7): synthetic contracts only."""

import tempfile
import unittest
from pathlib import Path

import yaml

from check_spec import Check

EVENT = "../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/Event"


def contract(schema=None, components=None):
    doc = {"openapi": "3.1.0", "info": {"title": "Example", "version": "1"}}
    if schema is not None:
        doc["paths"] = {"/events": {"get": {"responses": {"200": {
            "description": "Events", "content": {"application/json": {"schema": schema}}}}}}}
    if components is not None:
        doc["components"] = {"schemas": components}
    return doc


class CrossRefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.platform = self.root / "Platform"
        self.resource = self.write("05-resource/spec/05-resource.api.openapi.yaml", contract(
            {"$ref": "#/components/schemas/Event"},
            {"Event": {"type": "object", "additionalProperties": False,
                       "properties": {"kind": {"$ref": "#/components/schemas/Kind"}}},
             "Kind": {"type": "string"}}))
        self.console = self.write("06-console/spec/06-console.api.openapi.yaml",
                                  contract({"type": "array", "items": {"$ref": EVENT}}))

    def write(self, name, doc):
        path = self.platform / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        return path

    def check(self, *paths):
        result = Check(self.root)
        for path in paths or (self.console,):
            result.openapi(path)
        return result

    def assert_error(self, message, result=None):
        result = result or self.check()
        self.assertTrue(any(message in error for error in result.errors), result.errors)
        return result

    def test_valid_reference_to_an_earlier_lesson(self):
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi"], 1)
        self.assertEqual(result.stats["openapi_cross_refs"], 1)

    def test_each_position_counts_once_per_run(self):
        result = self.check(self.console, self.resource)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi"], 2)
        self.assertEqual(result.stats["openapi_cross_refs"], 1)

    def test_no_cross_refs_count_zero(self):
        result = self.check(self.resource)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi_cross_refs"], 0)

    def test_common_contract_with_components_only(self):
        self.write("common/contracts/view.openapi.yaml", contract(components={
            "View": {"type": "object", "additionalProperties": True}}))
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/contracts/view.openapi.yaml#/components/schemas/View"}))
        self.assertEqual(self.check().errors, [])

    def test_transitive_reference_through_an_earlier_lesson(self):
        self.write("common/contracts/kind.openapi.yaml", contract(components={"Kind": {"type": "string"}}))
        doc = yaml.safe_load(self.resource.read_text())
        doc["components"]["schemas"]["Kind"] = {
            "$ref": "../../common/contracts/kind.openapi.yaml#/components/schemas/Kind"}
        self.write("05-resource/spec/05-resource.api.openapi.yaml", doc)
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi_cross_refs"], 2)

    def test_file_not_found(self):
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../05-resource/spec/missing.openapi.yaml#/components/schemas/Event"}))
        result = self.assert_error("file not found: Platform/05-resource/spec/missing.openapi.yaml")
        # The place: the file and the JSON Pointer to the $ref.
        self.assert_error("at Platform/06-console/spec/06-console.api.openapi.yaml:"
                          "#/paths/~1events/get/responses/200/content/application~1json/schema/$ref", result)

    def test_pointer_not_found(self):
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../05-resource/spec/05-resource.api.openapi.yaml#/components/schemas/Missing"}))
        self.assert_error("unresolved/unsupported $ref")

    def test_reference_outside_platform(self):
        (self.root / "outside.openapi.yaml").write_text(yaml.safe_dump(contract(components={"X": {}})))
        for ref in ["../../../outside.openapi.yaml#/components/schemas/X",
                    "../../../Platform/../outside.openapi.yaml#/components/schemas/X"]:
            with self.subTest(ref=ref):
                self.write("06-console/spec/06-console.api.openapi.yaml", contract({"$ref": ref}))
                self.assert_error("stays between contracts inside Platform/")

    def test_reference_through_a_symlink_outside_platform(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "x.openapi.yaml").write_text(yaml.safe_dump(contract(components={"X": {}})))
        (self.platform / "common").mkdir()
        (self.platform / "common/link").symlink_to(outside)
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/link/x.openapi.yaml#/components/schemas/X"}))
        self.assert_error("stays between contracts inside Platform/")

    def test_reference_to_a_lesson_read_later(self):
        self.write("05-resource/spec/05-resource.api.openapi.yaml", contract(
            {"$ref": "../../06-console/spec/06-console.api.openapi.yaml#/paths"}))
        self.assert_error("reference to a lesson read later: P/06 is not read before P/05",
                          self.check(self.resource))

    def late_door(self, chapter, header, ref="../../08-domain/spec/08-domain.api.openapi.yaml#/components/schemas/Name",
                  where="paths"):
        self.write("08-domain/spec/08-domain.api.openapi.yaml", contract(components={"Name": {"type": "string"}}))
        norms = self.platform / f"06-console/spec/06.{chapter}-console.norms.md"
        norms.write_text(f"# P/06.{chapter}\n\nКанон главы. {header}\n", encoding="utf-8")
        doc = contract({"$ref": ref} if where == "paths" else {"$ref": "#/components/schemas/Name"},
                       {"Name": {"$ref": ref}} if where == "components" else None)
        doc["paths"]["/events"]["description"] = f"Глава 6.{chapter} — пересылка подписанту."
        self.write("06-console/spec/06-console.api.openapi.yaml", doc)

    def test_late_layer_door_refers_to_the_lesson_that_introduces_it(self):
        for header in ["**Глава позднего слоя: вводит урок 8**", "**Глава позднего слоя: вводят уроки 8 и 10**"]:
            with self.subTest(header=header):
                self.late_door(7, header)
                result = self.check()
                self.assertEqual(result.errors, [])
                self.assertEqual(result.stats["openapi_cross_refs"], 1)

    def test_late_layer_reference_is_narrow(self):
        cases = {"another lesson": (7, "**Глава позднего слоя: вводит урок 10**", "paths"),
                 "early chapter": (5, "Глава раннего слоя.", "paths"),
                 "outside a door": (7, "**Глава позднего слоя: вводит урок 8**", "components")}
        for name, (chapter, header, where) in cases.items():
            with self.subTest(name):
                self.late_door(chapter, header, where=where)
                self.assert_error("reference to a lesson read later: P/08 is not read before P/06")

    def test_common_refers_to_common_only(self):
        self.write("common/contracts/view.openapi.yaml", contract(components={"View": {"$ref": EVENT}}))
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/contracts/view.openapi.yaml#/components/schemas/View"}))
        self.assert_error("common contracts refer to common ones")

    def test_cycle_between_files(self):
        self.write("common/contracts/a.openapi.yaml", contract(components={
            "A": {"type": "array", "items": {"$ref": "b.openapi.yaml#/components/schemas/B"}}}))
        self.write("common/contracts/b.openapi.yaml", contract(components={
            "B": {"type": "array", "items": {"$ref": "a.openapi.yaml#/components/schemas/A"}}}))
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/contracts/a.openapi.yaml#/components/schemas/A"}))
        result = self.assert_error("cycle of cross-file $ref: Platform/common/contracts/a.openapi.yaml → "
                                   "Platform/common/contracts/b.openapi.yaml → Platform/common/contracts/a.openapi.yaml")
        self.assert_error("has errors", result)

    def test_own_file_by_path(self):
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "06-console.api.openapi.yaml#/paths"}))
        self.assert_error("use a local #/")

    def test_form_of_the_reference(self):
        for ref in ["https://example.invalid/05.openapi.yaml#/components/schemas/Event",
                    "../../05-resource/spec/05-resource.api.openapi.yaml",
                    "../../05-resource/README.md#/x",
                    "/abs/05-resource.api.openapi.yaml#/components/schemas/Event"]:
            with self.subTest(ref=ref):
                self.write("06-console/spec/06-console.api.openapi.yaml", contract({"$ref": ref}))
                self.assert_error("unresolved/unsupported $ref")

    def test_checks_see_the_target(self):
        # The target's own checks run even when its lesson is not on the command line: openness, the validator.
        for schema, message in [({"type": "object"}, "does not say its openness"),
                                ({"type": "strin", "additionalProperties": False}, "OpenAPI: "),
                                ({"$id": "x.json", "additionalProperties": False}, "unsupported schema keyword")]:
            with self.subTest(schema=schema):
                doc = yaml.safe_load(self.resource.read_text())
                doc["components"]["schemas"]["Event"] = schema
                self.write("05-resource/spec/05-resource.api.openapi.yaml", doc)
                result = self.assert_error(message)
                self.assert_error("Platform/05-resource/spec/05-resource.api.openapi.yaml: ", result)
                self.assert_error("the target contract Platform/05-resource/spec/05-resource.api.openapi.yaml "
                                  "has errors", result)

    def test_validator_resolves_the_target(self):
        # A target reached only through an extension is not checked by its file's walk; the referrer's validator
        # still resolves it, so a wrong schema there fails the referrer.
        doc = yaml.safe_load(self.resource.read_text())
        doc["x-defs"] = {"Bad": {"type": "strin"}}
        self.write("05-resource/spec/05-resource.api.openapi.yaml", doc)
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../05-resource/spec/05-resource.api.openapi.yaml#/x-defs/Bad"}))
        result = self.check()
        self.assertTrue(any(e.startswith("Platform/06-console/") and "'strin'" in e for e in result.errors),
                        result.errors)


if __name__ == "__main__":
    unittest.main()
