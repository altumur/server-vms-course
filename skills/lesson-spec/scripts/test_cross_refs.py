"""Cross-file $ref between Platform contracts (lesson 6 transfer plan, В7): synthetic contracts only."""

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import yaml

from check_spec import Check, validate

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
        result = self.assert_error("cycle of cross-file $ref:")
        self.assert_error("a.openapi.yaml:#/components/schemas/A", result)
        self.assert_error("b.openapi.yaml:#/components/schemas/B", result)
        self.assert_error("has errors", result)

    def test_cross_file_cycle_normalizes_uri_fragment_escapes(self):
        self.write("common/contracts/a.openapi.yaml", contract(components={
            "A": {"$ref": "b.openapi.yaml#/%63omponents/schemas/%42"}}))
        self.write("common/contracts/b.openapi.yaml", contract(components={
            "B": {"$ref": "a.openapi.yaml#/%63omponents/schemas/%41"}}))
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/contracts/a.openapi.yaml#/%63omponents/schemas/%41"}))
        result = self.assert_error("cycle of cross-file $ref:")
        self.assert_error("a.openapi.yaml:#/components/schemas/A", result)
        self.assert_error("b.openapi.yaml:#/components/schemas/B", result)

    def test_reciprocal_files_with_different_pointers_are_not_a_cycle(self):
        a = self.write("common/contracts/a.openapi.yaml", contract(components={
            "A": {"$ref": "b.openapi.yaml#/components/schemas/B"},
            "Leaf": {"type": "string"}}))
        b = self.write("common/contracts/b.openapi.yaml", contract(components={
            "B": {"$ref": "a.openapi.yaml#/components/schemas/Leaf"}}))
        self.write("06-console/spec/06-console.api.openapi.yaml", contract(
            {"$ref": "../../common/contracts/a.openapi.yaml#/components/schemas/A"}))
        with patch("check_spec.validate", wraps=validate) as validator:
            result = self.check(self.console)
            result.contract(a)
            result.contract(b)
        self.assertEqual(result.errors, [])
        checked = [call.args[1] for call in validator.call_args_list]
        self.assertEqual(checked.count(a), 1)
        self.assertEqual(checked.count(b), 1)
        self.assertEqual(checked.count(self.console), 1)
        self.assertEqual(result.stats["openapi_cross_refs"], 3)

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

    def json_schema(self, name, doc):
        path = self.platform / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def use_json_schema(self, ref):
        self.write("06-console/spec/06-console.api.openapi.yaml", contract({"$ref": ref}))

    def test_standalone_owner_schema_root_and_pointer(self):
        self.json_schema("06-console/data/answer.schema.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": {"Name": {"type": "string"}}, "type": "object", "additionalProperties": False,
            "properties": {"name": {"$ref": "#/$defs/Name"}}})
        for ref in ("../data/answer.schema.json", "../data/answer.schema.json#",
                    "../data/answer.schema.json#/$defs/Name"):
            with self.subTest(ref=ref):
                self.use_json_schema(ref)
                result = self.check()
                self.assertEqual(result.errors, [])
                self.assertEqual(result.stats["openapi"], 1)
                self.assertEqual(len(result.schema_documents), 1)

    def test_standalone_common_schema_root_and_boolean(self):
        for value in ({"type": "string"}, {}, True, False):
            with self.subTest(value=value):
                self.json_schema("common/data/value.schema.json", value)
                self.use_json_schema("../../common/data/value.schema.json")
                self.assertEqual(self.check().errors, [])

    def test_standalone_schema_transitive_relative_base(self):
        self.json_schema("common/data/entry.schema.json", {"$ref": "value.schema.json#/$defs/Value"})
        self.json_schema("common/data/value.schema.json", {"$defs": {"Value": {"type": "integer"}}})
        self.use_json_schema("../../common/data/entry.schema.json")
        result = self.check()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.stats["openapi_cross_refs"], 2)

    def test_contract_target_keeps_its_own_schema_base(self):
        self.json_schema("05-resource/data/event.schema.json", {"type": "string"})
        self.write("05-resource/spec/05-resource.api.openapi.yaml", contract(components={
            "Event": {"$ref": "../data/event.schema.json"}}))
        self.assertEqual(self.check().errors, [])

    def test_standalone_local_recursive_schema(self):
        self.json_schema("06-console/data/tree.schema.json", {
            "$defs": {"Tree": {"type": "object", "additionalProperties": False,
                                "properties": {"next": {"$ref": "#/$defs/Tree"}}}},
            "$ref": "#/$defs/Tree"})
        self.use_json_schema("../data/tree.schema.json")
        self.assertEqual(self.check().errors, [])

    def test_standalone_schema_cannot_replace_other_openapi_objects(self):
        self.json_schema("06-console/data/value.schema.json", {"type": "string"})
        ref = "../data/value.schema.json"
        for kind in ("path", "parameter", "response"):
            with self.subTest(kind=kind):
                doc = contract({"type": "string"})
                if kind == "path":
                    doc["paths"]["/events"] = {"$ref": ref}
                elif kind == "parameter":
                    doc["paths"]["/events"]["parameters"] = [{"$ref": ref}]
                else:
                    doc["paths"]["/events"]["get"]["responses"]["200"] = {"$ref": ref}
                self.write("06-console/spec/06-console.api.openapi.yaml", doc)
                with patch("check_spec.validate") as validator:
                    self.assert_error("standalone JSON Schema cannot replace")
                    validator.assert_not_called()

    def test_standalone_schema_missing_and_invalid_pointer(self):
        self.json_schema("06-console/data/value.schema.json", {
            "$defs": {"a/b": {"type": "string"}}, "type": "object", "additionalProperties": False,
            "required": ["x"]})
        for ref in ("../data/missing.schema.json", "../data/value.schema.json#/missing",
                    "../data/value.schema.json#name", "../data/value.schema.json#/$defs/a~2b",
                    "../data/value.schema.json#/%ZZ", "../data/value.schema.json#/required/01"):
            with self.subTest(ref=ref):
                self.use_json_schema(ref)
                self.assert_error("unresolved/unsupported $ref")
        self.use_json_schema("../data/value.schema.json#/$defs/a~1b")
        self.assertEqual(self.check().errors, [])

    def test_standalone_pointer_target_must_be_schema_kind(self):
        self.json_schema("06-console/data/value.schema.json", {
            "type": "object", "additionalProperties": False, "required": ["x"]})
        for fragment in ("/type", "/required"):
            with self.subTest(fragment=fragment):
                self.use_json_schema("../data/value.schema.json#" + fragment)
                self.assert_error("target is not a Schema object or boolean")

    def test_standalone_wrong_root_or_openapi_document_is_rejected(self):
        for value in ([], 1, "schema", contract({"type": "string"})):
            with self.subTest(value=value):
                self.json_schema("06-console/data/value.schema.json", value)
                self.use_json_schema("../data/value.schema.json")
                self.assert_error("expected a standalone JSON Schema object or boolean")

    def test_standalone_strict_json_and_meta_schema(self):
        path = self.json_schema("06-console/data/value.schema.json", {})
        self.use_json_schema("../data/value.schema.json")
        for text in ('{"type":"string","type":"integer"}', '{"const":NaN}', '{"const":Infinity}',
                     '{"type":"strin"}', '{"properties":[]}'):
            with self.subTest(text=text):
                path.write_text(text)
                self.assert_error("JSON Schema:")
        path.write_bytes(b'\xff')
        self.assertTrue(self.check().errors)

    def test_standalone_schema_dialect_and_base_changes_are_explicit(self):
        for schema in ({"$schema": "https://example.invalid/dialect"}, {"$id": "other.json"},
                       {"$dynamicRef": "#node"}, {"$recursiveRef": "#"}):
            with self.subTest(schema=schema):
                self.json_schema("06-console/data/value.schema.json", schema)
                self.use_json_schema("../data/value.schema.json")
                self.assert_error("unsupported schema")

    def test_standalone_schema_keeps_its_openness_and_contract_rule(self):
        self.json_schema("06-console/data/value.schema.json", {
            "$defs": {"Value": {"type": "object"}}})
        self.use_json_schema("../data/value.schema.json#/$defs/Value")
        self.assertEqual(self.check().errors, [])
        self.write("06-console/spec/06-console.api.openapi.yaml", contract({"type": "object"}))
        self.assert_error("does not say its openness")

    def test_standalone_schema_owner_and_directory_boundaries(self):
        for name, ref in (("06-console/spec/value.schema.json", "value.schema.json"),
                          ("common/contracts/value.schema.json", "../../common/contracts/value.schema.json")):
            with self.subTest(name=name):
                self.json_schema(name, {"type": "string"})
                self.use_json_schema(ref)
                self.assert_error("declared owner data/ inside Platform/")

    def test_standalone_earlier_owner_keeps_existing_reading_order(self):
        self.json_schema("09-agent/data/alarms.schema.json", {
            "type": "object", "additionalProperties": False, "properties": {"events": {
                "type": "array", "items": {"type": "object", "additionalProperties": False,
                "properties": {"t": {"type": "number"}, "kind": {"type": "string"},
                               "class": {"type": "string"}}}}}})
        for field in ("t", "kind", "class"):
            with self.subTest(field=field):
                path = self.write("10-domain-console/spec/10-domain-console.api.openapi.yaml", contract({
                    "$ref": "../../09-agent/data/alarms.schema.json#/properties/events/items/properties/" + field}))
                self.assertEqual(self.check(path).errors, [])

    def test_standalone_later_owner_requires_existing_late_layer_guard(self):
        self.json_schema("08-domain/data/value.schema.json", {"type": "string"})
        self.use_json_schema("../../08-domain/data/value.schema.json")
        self.assert_error("reference to a lesson read later")
        self.late_door(7, "**Глава позднего слоя: вводит урок 8**",
                       ref="../../08-domain/data/value.schema.json")
        self.assertEqual(self.check().errors, [])

    def test_standalone_common_cannot_read_lesson(self):
        self.json_schema("06-console/data/value.schema.json", {"type": "string"})
        self.json_schema("common/data/entry.schema.json", {"$ref": "../../06-console/data/value.schema.json"})
        self.use_json_schema("../../common/data/entry.schema.json")
        self.assert_error("common contracts refer to common ones")

    def test_standalone_paths_and_network_stay_closed(self):
        for ref in ("https://example.invalid/a.schema.json", "file:///a.schema.json",
                    "//example.invalid/a.schema.json", "/abs/a.schema.json", "../data/a.schema.json?q=1",
                    "../../../outside.schema.json", "../../../Platform/../outside.schema.json",
                    "../data/value.json", "../data/value.schema.json#%FF"):
            with self.subTest(ref=ref), patch("urllib.request.urlopen") as fetch:
                self.use_json_schema(ref)
                self.assertTrue(self.check().errors)
                fetch.assert_not_called()

    def test_standalone_symlink_escape_and_foreign_owner_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "value.schema.json").write_text('{"type":"string"}')
        data = self.platform / "06-console/data"
        data.mkdir()
        (data / "escape.schema.json").symlink_to(outside / "value.schema.json")
        other = self.json_schema("08-domain/data/value.schema.json", {"type": "string"})
        (data / "foreign.schema.json").symlink_to(other)
        for ref in ("../data/escape.schema.json", "../data/foreign.schema.json"):
            with self.subTest(ref=ref):
                self.use_json_schema(ref)
                self.assertTrue(self.check().errors)

    def test_standalone_cross_file_cycle_and_self_path_rejected(self):
        self.json_schema("common/data/a.schema.json", {"$ref": "b.schema.json"})
        self.json_schema("common/data/b.schema.json", {"$ref": "a.schema.json"})
        self.use_json_schema("../../common/data/a.schema.json")
        self.assert_error("cycle of cross-file $ref")
        self.json_schema("06-console/data/self.schema.json", {"$ref": "self.schema.json"})
        self.use_json_schema("../data/self.schema.json")
        self.assert_error("use a local #/")

    def test_standalone_refs_in_data_do_not_become_schema_edges(self):
        self.json_schema("common/data/value.schema.json", {"type": "string"})
        data = {"$ref": "https://example.invalid/not-a-schema.json"}
        for keyword in ("examples", "const", "enum", "default"):
            with self.subTest(keyword=keyword), patch("urllib.request.urlopen") as fetch:
                schema = {"$ref": "../../common/data/value.schema.json"}
                schema[keyword] = [data] if keyword in ("examples", "enum") else data
                self.write("06-console/spec/06-console.api.openapi.yaml", contract(schema))
                result = self.check()
                if keyword != "default":
                    self.assertEqual(result.errors, [])
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
