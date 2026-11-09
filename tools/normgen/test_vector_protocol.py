import json
import unittest

import vector_protocol as protocol


class ProtocolStructureControls(unittest.TestCase):
    def test_cell_shapes_preserve_legitimate_names_without_column_associations(self):
        value = {"variant": "read", "when": 'row["case"] == "private-case"',
                 "case": "private-id", "cells": {
                     "expect": {"column": "private-answer"},
                     "body": {"column": "private-fixture", "decode": "raw-json"}}}
        got = protocol.input_shape(value)
        self.assertEqual(got, {"variant": "read", "cells": {
            "expect": {"type": "string"}, "body": {}}})
        self.assertNotIn("private-", json.dumps(got))

    def test_file_input_object_preserves_only_its_structural_fields(self):
        got = protocol.input_shape({"variant": "", "arg_file": {"json": {
            "object": {"sender": {"column": "sender", "decode": "text"},
                       "rid": {"column": "rid", "decode": "raw-json"}}}}})
        self.assertEqual(got["argument_file"], {"encoding": "json", "schema": {
            "type": "object", "properties": {"sender": {"type": "string"}, "rid": {}},
            "required": ["sender", "rid"], "additionalProperties": False}})
        self.assertNotIn("column", json.dumps(got))

    def test_native_shape_omits_case_selectors_but_keeps_structural_constants(self):
        value = {"when": 'row["expect"] == "private-answer"', "type": "object", "frame": "json",
                 "schema": {"type": "object", "properties": {
                     "case": {"const": "ok"}, "expect": {"type": "string"}},
                     "required": ["case"], "additionalProperties": False}}
        got = protocol.native_shape(value)
        self.assertEqual(got["schema"], value["schema"])
        self.assertNotIn("private-answer", json.dumps(got))
        self.assertNotIn("when", got)

    def test_input_constant_retains_structural_declaration_not_case_selector(self):
        got = protocol.input_shape({"when": 'row["case"] == "private-rotate-case"',
                                    "cells": {"rotate": {"literal": "true"}}})
        self.assertEqual(got, {"variant": "", "cells": {"rotate": {"const": "true"}}})
        self.assertNotIn("private-rotate-case", json.dumps(got))

    def test_unknown_input_or_native_shape_refuses_instead_of_silent_omission(self):
        for value in ({"cells": {}, "unapproved": "secret"},
                      {"arg_file": {"literal": "private-fixture"}},
                      {"cells": {"x": {"column": "input", "decode": "unknown"}}}):
            with self.subTest(value=value), self.assertRaises(protocol.ProtocolError):
                protocol.input_shape(value)
        for value in ({"type": "object", "frame": "guess"},
                      {"type": "object", "frame": "json", "schema": {"examples": ["private-answer"]}},
                      {"type": "object", "frame": "json", "case": "private-case"}):
            with self.subTest(value=value), self.assertRaises(protocol.ProtocolError):
                protocol.native_shape(value)

    def test_duplicate_json_members_and_nonfinite_numbers_refuse(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(protocol.ProtocolError):
                protocol._load(raw, "control")

    def test_literal_classifier_is_structural_not_substring(self):
        self.assertTrue(protocol.contains_expect_literal([{"value": {"literal": "answer"}}]))
        self.assertFalse(protocol.contains_expect_literal([{"value": {"column": "literal"}}]))
        self.assertFalse(protocol.contains_expect_literal([{"value": "literal"}]))


class DerivedConsistencyControls(unittest.TestCase):
    def row(self):
        return {"package": "common/control", "table": "private-cases.tsv", "surface": "stand:control",
                "header": "case,input,expect", "files": {"private-file": "private-path"},
                "norm": "private-source", "compare": "value", "markers": [],
                "inputs": [{"variant": "", "when": 'row["case"] == "private-id"',
                            "arg_file": {"json": {"object": {
                                "request": {"column": "input", "decode": "text"}}}}}],
                "expect": [{"value": {"literal": "private-answer"}}],
                "native": {"type": "object", "frame": "json", "schema": {
                    "type": "object", "properties": {"result": {"type": "string"}},
                    "required": ["result"], "additionalProperties": False}}}

    def test_command_and_input_output_shape_derive_from_structural_declarations(self):
        got = protocol.structural_row(self.row())
        self.assertEqual(got["entrypoint"], {"surface": "stand", "command": "control"})
        self.assertEqual(got["inputs"][0]["argument_file"]["schema"]["required"], ["request"])
        self.assertEqual(got["outputs"][0]["schema"]["required"], ["result"])
        self.assertNotIn("private-", json.dumps(got))

    def test_expectation_fixture_selectors_and_provenance_mutations_do_not_change_shape(self):
        row = self.row()
        before = protocol.structural_row(row)
        row["expect"] = [{"value": {"literal": "another-answer"}, "when": "private-case"}]
        row["table"] = "another-private-table"
        row["files"] = {"another-private-file": "another-private-path"}
        row["header"] = "another-private-header"
        row["norm"] = "another-private-norm"
        row["markers"] = [{"value": {"literal": "another-private-marker"}}]
        row["inputs"][0]["when"] = 'row["case"] == "another-private-case"'
        self.assertEqual(before, protocol.structural_row(row))

    def test_protocol_shape_changes_are_derived(self):
        row = self.row()
        before = protocol.structural_row(row)
        row["surface"] = "stand:renamed-control"
        row["native"]["schema"]["properties"]["result"]["type"] = "integer"
        row["inputs"][0]["arg_file"]["json"]["object"]["new_field"] = {"column": "new-input"}
        got = protocol.structural_row(row)
        self.assertNotEqual(before, got)
        self.assertEqual(got["entrypoint"]["command"], "renamed-control")
        self.assertEqual(got["outputs"][0]["schema"]["properties"]["result"]["type"], "integer")
        self.assertIn("new_field", got["inputs"][0]["argument_file"]["schema"]["required"])

    def test_grouping_never_exports_table_or_case_associations(self):
        first = self.row()
        second = self.row()
        second["table"] = "other-private-table"
        second["native"]["frame"] = "json-lf"
        merged = protocol.merge_structural_rows(map(protocol.structural_row, [first, second, first]))
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["inputs"]), 1)
        self.assertEqual(len(merged[0]["outputs"]), 2)
        self.assertNotIn("private-", json.dumps(merged))
        self.assertEqual(merged, protocol.merge_structural_rows(map(protocol.structural_row, [second, first])))


class UnionSanitizationControls(unittest.TestCase):
    def native(self, value, variant="", when="true"):
        return {"variant": variant, "when": when, "type": "object", "frame": "json",
                "schema": {"type": "object", "properties": {"status": {"const": value}},
                           "required": ["status"], "additionalProperties": False}}

    def test_case_dependent_constants_become_types_but_invariant_constants_stay(self):
        values = [protocol.native_shape(self.native("ok", when='row["case"] == "private-a"')),
                  protocol.native_shape(self.native("refused", when='row["case"] == "private-b"'))]
        got = protocol.normalize_native_union(values)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["schema"]["properties"]["status"], {"type": "string"})
        invariant = [protocol.native_shape(self.native("ok", when='owner == "03-worker"')),
                     protocol.native_shape(self.native("ok", when='owner == "06-console"'))]
        got = protocol.normalize_native_union(invariant)
        self.assertEqual(len(got), 2)
        self.assertTrue(all(value["schema"]["properties"]["status"] == {"const": "ok"} for value in got))
        self.assertTrue(all("when" in value for value in got))

    def test_generalized_oneof_is_a_union_not_an_impossible_duplicate_exclusive_choice(self):
        import jsonschema
        row = self.native("unused")
        row["schema"] = {"oneOf": [self.native("ok")["schema"], self.native("refused")["schema"]]}
        got = protocol.normalize_native_union([protocol.native_shape(row)])[0]["schema"]
        self.assertNotIn("oneOf", got)
        self.assertIn("anyOf", got)
        jsonschema.Draft202012Validator.check_schema(got)
        validator = jsonschema.Draft202012Validator(got)
        self.assertTrue(validator.is_valid({"status": "ok"}))
        self.assertTrue(validator.is_valid({"status": "refused"}))
        self.assertFalse(validator.is_valid({"status": 7}))

    def test_named_variants_have_separate_constant_invariance(self):
        values = [protocol.native_shape(self.native("read-only", variant="read")),
                  protocol.native_shape(self.native("write-only", variant="write"))]
        got = protocol.normalize_native_union(values)
        self.assertEqual({x["variant"]: x["schema"]["properties"]["status"]["const"] for x in got},
                         {"read": "read-only", "write": "write-only"})

    def test_owner_only_predicates_keep_their_original_expression_case_predicates_disappear(self):
        owner = '(owner == "03-worker" || owner in ["06-console", "08-domain"])'
        self.assertEqual(protocol.owner_condition(owner), owner)
        self.assertIsNone(protocol.owner_condition('owner == "03-worker" && row["case"] == "private-case"'))
        self.assertIsNone(protocol.owner_condition('json(row["expect"])["kind"] == "private-answer"'))
        quoted = 'owner == "row[private-name]"'
        self.assertEqual(protocol.owner_condition(quoted), quoted)
        for bad in ('case == "private-case"', 'owner owner', '(owner == "03-worker"',
                    'owner == "03-worker" garbage', 'owner in ["03-worker",]'):
            with self.subTest(bad=bad), self.assertRaises(protocol.ProtocolError):
                protocol.owner_condition(bad)

    def test_case_varying_enum_becomes_type(self):
        value = self.native("unused")
        value["schema"]["properties"]["status"] = {"enum": ["ok", "refused"]}
        got = protocol.normalize_native_union([protocol.native_shape(value)])
        self.assertEqual(got[0]["schema"]["properties"]["status"], {"type": "string"})


class DerivationContractControls(unittest.TestCase):
    def wire(self, rows):
        import csv
        import io
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(protocol.COLUMNS)
        for row in rows:
            writer.writerow([json.dumps(row[name], separators=(",", ":")) if name in
                             ("inputs", "files", "expect", "markers", "native") else row[name]
                            for name in protocol.COLUMNS])
        return stream.getvalue().encode()

    def row(self):
        return DerivedConsistencyControls().row()

    def test_all_adapter_rows_retained_with_expectation_literal_cells_excluded(self):
        row = self.row()
        public, receipt = protocol.derive(self.wire([row]))
        value = json.loads(public)
        self.assertEqual(len(value["adapters"]), 1)
        self.assertTrue(receipt["classification"][0]["expectation_contains_literal"])
        for forbidden in ("private-answer", "private-cases.tsv", "private-id", "private-file", "private-source",
                          "source_sha256", "source_commit", "classification"):
            self.assertNotIn(forbidden, public.decode())
        self.assertIn("source_sha256", receipt)
        protocol.check_consistency(self.wire([row]), public)

    def test_expected_case_and_fixture_mutations_cannot_change_public_bytes(self):
        row = self.row()
        before, _ = protocol.derive(self.wire([row]))
        row["expect"] = [{"value": {"object": {"secret": {"literal": "answer-canary"}}}}]
        row["markers"] = [{"match": "fixture-canary", "value": {"literal": "marker-canary"}}]
        row["inputs"][0]["when"] = 'row["case"] == "case-canary"'
        row["table"] = "case-canary.tsv"
        row["files"] = {"fixture-canary": "J/path/case-canary"}
        after, _ = protocol.derive(self.wire([row]))
        self.assertEqual(before, after)

    def test_shape_mutations_derive_new_bytes_and_stale_or_handwritten_artifact_refuses(self):
        row = self.row()
        before, _ = protocol.derive(self.wire([row]))
        row["native"]["frame"] = "json-lf"
        changed = self.wire([row])
        after, _ = protocol.derive(changed)
        self.assertNotEqual(before, after)
        protocol.check_consistency(changed, after)
        for stale in (before, after + b" ", b'{"adapters": []}\n'):
            with self.subTest(stale=stale), self.assertRaises(protocol.ProtocolError):
                protocol.check_consistency(changed, stale)

    def test_private_receipt_cannot_be_written_into_public_tree(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            public = pathlib.Path(directory) / "public"
            with self.assertRaises(SystemExit) as context:
                protocol.main(["--source-root", directory, "--source-ref", "main",
                               "--public-root", str(public), "--receipt", str(public / "receipt.json")])
            self.assertEqual(context.exception.code, 2)
            self.assertFalse(public.exists())


class CanonicalProtocolControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.data = (Path(__file__).resolve().parents[2] / protocol.CANONICAL_PATH).read_bytes()

    def wire(self, rows):
        import csv
        import io
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(protocol.COLUMNS)
        for row in rows:
            values = []
            for key in protocol.COLUMNS:
                value = row[key]
                if key == "native" and value is None:
                    value = "-"
                elif key in ("inputs", "files", "expect", "markers", "native"):
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                values.append(value)
            writer.writerow(values)
        return stream.getvalue().encode()

    def test_actual_canonical_commands_inputs_and_all_native_variants_admit(self):
        public, receipt = protocol.derive(self.data)
        value = json.loads(public)
        expected = {(row["package"], row["surface"]) for row in protocol.read_rows(self.data)
                    if row["surface"] != "layout"}
        actual = {(row["package"], "stand:" + row["entrypoint"]["command"]
                   if row["entrypoint"]["surface"] == "stand" else "vectors")
                  for row in value["adapters"]}
        self.assertEqual(actual, expected)
        self.assertEqual(receipt["public_entrypoints"], len(expected))
        self.assertTrue(all(row["inputs"] and row["outputs"] for row in value["adapters"]))
        for row in value["adapters"]:
            for item in row["inputs"] + row["outputs"]:
                if "when" in item:
                    self.assertEqual(protocol.owner_condition(item["when"]), item["when"])

    def test_all_actual_expectation_literal_rows_and_case_associations_are_noninterfering(self):
        rows = protocol.read_rows(self.data)
        before, _ = protocol.derive(self.data)
        literal_rows = sum(protocol.contains_expect_literal(row["expect"]) for row in rows)
        self.assertGreater(literal_rows, 0)
        for index, row in enumerate(rows):
            row["expect"] = [{"value": {"literal": "EXPECTATION_CANARY_" + str(index)}}]
            row["markers"] = [{"match": "CASE_CANARY_" + str(index),
                               "value": {"literal": "MARKER_CANARY_" + str(index)}}]
            row["table"] = "J_CASE_CANARY_" + str(index)
            row["header"] = "FIXTURE_HEADER_CANARY_" + str(index)
            row["files"] = {"J_FILE_CANARY": "J_PATH_CANARY_" + str(index)}
            row["norm"] = "J_SOURCE_CANARY_" + str(index)
            for value in row["inputs"]:
                value["case"] = "CASE_ID_CANARY_" + str(index)
                value["group_by"] = ["CASE_GROUP_CANARY_" + str(index)]
                if "when" in value and protocol.owner_condition(value["when"]) is None:
                    value["when"] = 'row["case"] == "SELECTOR_CANARY"'
            native = row["native"]
            for value in native if isinstance(native, list) else ([] if native is None else [native]):
                if "when" in value and protocol.owner_condition(value["when"]) is None:
                    value["when"] = 'row["expect"] == "NATIVE_SELECTOR_CANARY"'
        after, _ = protocol.derive(self.wire(rows))
        self.assertEqual(before, after)
        self.assertNotIn("CANARY", after.decode())

    def test_actual_native_shape_change_invalidates_old_public_derivation(self):
        rows = protocol.read_rows(self.data)
        before, _ = protocol.derive(self.data)
        row = next(row for row in rows if row["surface"].startswith("stand:"))
        row["surface"] += "-new-structural-command"
        changed = self.wire(rows)
        after, _ = protocol.derive(changed)
        self.assertNotEqual(before, after)
        with self.assertRaises(protocol.ProtocolError):
            protocol.check_consistency(changed, before)
        protocol.check_consistency(changed, after)


if __name__ == "__main__":
    unittest.main()
