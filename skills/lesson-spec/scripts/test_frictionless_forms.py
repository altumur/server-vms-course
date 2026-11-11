import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import frictionless_forms
import check_forms

ROOT = Path(__file__).resolve().parents[3]


class StandardFormControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="standard-form-controls-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        names = [frictionless_forms.PACKAGE]
        for relative in frictionless_forms.RESOURCES.values():
            names.extend(["Platform/" + relative, "Platform/" + relative + ".schema.json"])
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())

    def package(self, update):
        path = self.root / frictionless_forms.PACKAGE
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        update(descriptor)
        path.write_text(json.dumps(descriptor), encoding="utf-8")

    def cell(self, resource, column, value, row=0):
        path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        columns = lines[header].split("\t")
        cells = lines[header + 1 + row].split("\t")
        cells[columns.index(column)] = value
        lines[header + 1 + row] = "\t".join(cells)
        path.write_text("\n".join(lines), encoding="utf-8")

    def duplicate_row(self, resource):
        path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        lines.insert(header + 2, lines[header + 1])
        path.write_text("\n".join(lines), encoding="utf-8")

    def errors(self):
        return frictionless_forms.check(self.root)[0]

    def test_actual_selected_source_passes_without_cell_coercion(self):
        tables = {}
        errors, stats = frictionless_forms.check(ROOT, tables=tables)
        self.assertEqual(errors, [])
        self.assertEqual(stats["standard_form_tables"], len(frictionless_forms.RESOURCES))
        self.assertEqual(len(tables), len(frictionless_forms.RESOURCES))
        for path, table in tables.items():
            self.assertTrue(all(isinstance(value, str) for row in table["rows"] for value in row))
            self.assertEqual(path.read_bytes().decode("utf-8").split("\n")[table["header"] - 1].split("\t"),
                             table["columns"])

    def test_optional_empty_when_is_legal_and_raw_cache_stays_empty_string(self):
        self.cell("stages_p01", "when", "")
        cache = {}
        errors, _ = frictionless_forms.check(self.root, tables=cache)
        self.assertEqual(errors, [])
        path = self.root / "Platform/01-store/forms/stages.tsv"
        table = cache[path]
        self.assertEqual(table["rows"][0][table["columns"].index("when")], "")

    def test_required_empty_stage_id_and_gate_refuse(self):
        for resource, column in [("stages_p01", "stage"),
                                 ("code_rules_p01", "id"),
                                 ("stages_p01", "gate")]:
            with self.subTest(resource=resource, column=column):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
                saved = path.read_bytes()
                self.cell(resource, column, "")
                self.assertTrue(any("constraint-error" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_unknown_kind_and_stage_are_foreign_key_errors(self):
        for column, value in [("stage", "absent_stage"), ("kind", "absent_kind")]:
            with self.subTest(column=column):
                path = self.root / "Platform/01-store/forms/code-rules.tsv"
                saved = path.read_bytes()
                self.cell("code_rules_p01", column, value)
                self.assertTrue(any("foreign-key" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_stage_rule_and_kind_primary_keys_refuse_duplicates(self):
        for resource in ("stages_p01", "code_rules_p01", "code_kinds"):
            with self.subTest(resource=resource):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
                saved = path.read_bytes()
                self.duplicate_row(resource)
                self.assertTrue(any("primary-key" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_public_gate_vocabulary_and_dictionary_name_enum_refuse(self):
        for resource, column, value in [
            ("stages_p01", "gate", "code:model"),
            ("stages_p01", "gate", "tests:1.1:*"),
            ("code_kinds", "name", "command"),
        ]:
            with self.subTest(resource=resource, column=column):
                path = self.root / "Platform" / frictionless_forms.RESOURCES[resource]
                saved = path.read_bytes()
                self.cell(resource, column, value)
                self.assertTrue(any("constraint-error" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_header_order_and_extra_column_are_framework_errors(self):
        path = self.root / "Platform/01-store/forms/stages.tsv"
        saved = path.read_bytes()
        for extra in (False, True):
            with self.subTest(extra=extra):
                path.write_bytes(saved)
                lines = path.read_text(encoding="utf-8").split("\n")
                header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
                cells = lines[header].split("\t")
                if extra:
                    cells.append("undeclared")
                else:
                    cells[0], cells[1] = cells[1], cells[0]
                lines[header] = "\t".join(cells)
                path.write_text("\n".join(lines), encoding="utf-8")
                self.assertTrue(self.errors())

    def test_literal_quoted_tab_is_not_csv_escaped_into_one_cell(self):
        self.cell("stages_p01", "goal", '"raw\tTAB"')
        self.assertTrue(any("extra-cell" in error for error in self.errors()))

    def test_short_row_refuses_and_long_row_refuses(self):
        path = self.root / "Platform/01-store/forms/code-rules.tsv"
        saved = path.read_bytes()
        for extra in (False, True):
            with self.subTest(extra=extra):
                path.write_bytes(saved)
                lines = path.read_text(encoding="utf-8").split("\n")
                header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
                cells = lines[header + 1].split("\t")
                if extra:
                    cells.append("extra")
                else:
                    cells.pop()
                lines[header + 1] = "\t".join(cells)
                path.write_text("\n".join(lines), encoding="utf-8")
                self.assertTrue(self.errors())

    def test_unicode_line_separator_and_quotes_remain_raw_cell_bytes(self):
        value = '"quoted"\u2028tail'
        self.cell("stages_p01", "goal", value)
        tables = {}
        errors, _ = frictionless_forms.check(self.root, tables=tables)
        self.assertEqual(errors, [])
        table = tables[self.root / "Platform/01-store/forms/stages.tsv"]
        self.assertEqual(table["rows"][0][table["columns"].index("goal")], value)

    def test_comment_change_requires_source_header_row_update(self):
        path = self.root / "Platform/01-store/forms/stages.tsv"
        path.write_bytes(b"# inserted physical comment\n" + path.read_bytes())
        self.assertTrue(any("headerRows must equal physical header" in error for error in self.errors()))

    def test_wrong_header_row_is_not_repaired_or_inferred(self):
        self.package(lambda descriptor: descriptor["resources"][0]["dialect"].update(
            {"headerRows": [1]}))
        self.assertTrue(any("headerRows must equal physical header" in error for error in self.errors()))

    def test_missing_manifest_schema_and_form_are_errors_not_fallback(self):
        for name in [
            frictionless_forms.PACKAGE,
            "Platform/01-store/forms/stages.tsv.schema.json",
            "Platform/01-store/forms/stages.tsv",
        ]:
            with self.subTest(name=name):
                path = self.root / name
                saved = path.read_bytes()
                path.unlink()
                self.assertTrue(any("ordinary form Source file" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_resource_registry_does_not_admit_extra_missing_or_duplicate_names(self):
        path = self.root / frictionless_forms.PACKAGE
        saved = path.read_bytes()
        for change in (
            lambda data: data["resources"].pop(),
            lambda data: data["resources"].append(copy.deepcopy(data["resources"][0])),
            lambda data: data["resources"][0].update({"name": "other"}),
        ):
            with self.subTest(change=change):
                path.write_bytes(saved)
                self.package(change)
                self.assertTrue(any("selected form group" in error for error in self.errors()))

    def test_resource_and_schema_paths_are_exact_source_owned_inputs(self):
        for key, value in [
            ("path", "../outside.tsv"), ("path", "https://example.invalid/data.tsv"),
            ("schema", "../schema.json"), ("schema", ["schema.json"]),
        ]:
            with self.subTest(key=key, value=value):
                path = self.root / frictionless_forms.PACKAGE
                saved = path.read_bytes()
                self.package(lambda data: data["resources"][0].update({key: value}))
                self.assertTrue(any("wrong Source path or schema" in error for error in self.errors()))
                path.write_bytes(saved)

    def test_symlink_metadata_or_form_refuses(self):
        for name in [frictionless_forms.PACKAGE, "Platform/01-store/forms/stages.tsv"]:
            with self.subTest(name=name):
                path = self.root / name
                saved = path.with_name(path.name + ".saved")
                path.rename(saved)
                path.symlink_to(saved)
                self.assertTrue(any("symbolic link" in error for error in self.errors()))
                path.unlink()
                saved.rename(path)

    def test_duplicate_json_metadata_keys_are_not_last_value_wins(self):
        path = self.root / frictionless_forms.PACKAGE
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("{", '{"resources": [],', 1), encoding="utf-8")
        self.assertTrue(any("duplicate JSON metadata key" in error for error in self.errors()))

    def test_kit_stage_names_do_not_become_current_public_fk_targets(self):
        self.cell("stages_kit_p01", "stage", "kit_only")
        self.assertEqual(self.errors(), [])
        self.cell("code_rules_p01", "stage", "kit_only")
        self.assertTrue(any("foreign-key" in error for error in self.errors()))

    def simple_gates(self):
        path = self.root / "Platform/01-store/forms/stages.tsv"
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        columns = lines[header].split("\t")
        for i in range(header + 1, len(lines)):
            if lines[i] and not lines[i].startswith("#"):
                cells = lines[i].split("\t")
                cells[columns.index("gate")] = "build;code:*"
                lines[i] = "\t".join(cells)
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_actual_cached_rows_feed_existing_stage_semantics_without_reparse(self):
        tables = {}
        errors, _ = frictionless_forms.check(ROOT, tables=tables)
        self.assertEqual(errors, [])
        for name in ("stages.tsv", "stages.kit.tsv"):
            with self.subTest(name=name):
                path = ROOT / "Platform/01-store/forms" / name
                errors, stats = check_forms.check_stage_parts(path, validated=tables[path])
                self.assertEqual(errors, [])
                self.assertEqual(stats["stage_rows"], len(tables[path]["rows"]))

    def test_physical_n_order_and_depends_remain_existing_semantic_guards(self):
        self.simple_gates()
        path = self.root / "Platform/01-store/forms/stages.tsv"
        saved = path.read_bytes()
        for kind in ("n", "depends"):
            with self.subTest(kind=kind):
                path.write_bytes(saved)
                if kind == "n":
                    self.cell("stages_p01", "n", "2")
                    self.cell("stages_p01", "n", "1", row=1)
                else:
                    self.cell("stages_p01", "depends", "2")
                tables = {}
                errors, _ = frictionless_forms.check(self.root, tables=tables)
                self.assertEqual(errors, [])
                errors, _ = check_forms.check_stage_parts(path, validated=tables[path])
                self.assertTrue(any("expected" in e if kind == "n" else "former stages" in e
                                    for e in errors), errors)

    def test_code_coverage_and_duplicate_gate_remain_existing_semantic_guards(self):
        self.simple_gates()
        path = self.root / "Platform/01-store/forms/stages.tsv"
        saved = path.read_bytes()
        for kind in ("coverage", "duplicate"):
            with self.subTest(kind=kind):
                path.write_bytes(saved)
                if kind == "coverage":
                    text = path.read_text(encoding="utf-8").replace("build;code:*", "build")
                    path.write_text(text, encoding="utf-8")
                else:
                    self.cell("stages_p01", "gate", "build;build")
                tables = {}
                errors, _ = frictionless_forms.check(self.root, tables=tables)
                self.assertEqual(errors, [])
                errors, _ = check_forms.check_stage_parts(path, validated=tables[path])
                phrase = "no code:* gate" if kind == "coverage" else "duplicate gate checks"
                self.assertTrue(any(phrase in e for e in errors), errors)

    def test_unselected_stage_api_keeps_legacy_shape_checks(self):
        path = self.root / "Platform/02-installer/forms/stages.tsv"
        path.parent.mkdir(parents=True)
        path.write_text("n\tstage\tgate\tdepends\n1\ts1\tbuild\t-\n", encoding="utf-8")
        self.assertEqual(check_forms.check_stage_parts(path)[0], [])
        path.write_text("n\tstage\tgate\tdepends\n1\ts1\tbuild\t-\textra\n", encoding="utf-8")
        self.assertTrue(any("cells, expected" in e for e in check_forms.check_stage_parts(path)[0]))

    def test_duplicate_or_missing_form_header_is_a_framework_error(self):
        path = self.root / "Platform/01-store/forms/stages.tsv"
        saved = path.read_bytes()
        for kind in ("duplicate", "missing"):
            with self.subTest(kind=kind):
                path.write_bytes(saved)
                lines = path.read_text(encoding="utf-8").split("\n")
                header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
                cells = lines[header].split("\t")
                if kind == "duplicate":
                    cells[1] = cells[0]
                else:
                    cells.pop()
                lines[header] = "\t".join(cells)
                path.write_text("\n".join(lines), encoding="utf-8")
                self.assertTrue(self.errors())

    def test_kit_part_vocabulary_is_standard_and_duplicates_stay_semantic(self):
        path = self.root / "Platform/01-store/forms/stages.kit.tsv"
        saved = path.read_bytes()
        self.cell("stages_kit_p01", "parts", "unknown_piece")
        self.assertTrue(any("constraint-error" in e for e in self.errors()))
        path.write_bytes(saved)
        lines = path.read_text(encoding="utf-8").split("\n")
        header = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        columns = lines[header].split("\t")
        for i in range(header + 1, len(lines)):
            if lines[i] and not lines[i].startswith("#"):
                cells = lines[i].split("\t")
                cells[columns.index("gate")] = "build"
                lines[i] = "\t".join(cells)
        path.write_text("\n".join(lines), encoding="utf-8")
        self.cell("stages_kit_p01", "parts", "door,door")
        tables = {}
        errors, _ = frictionless_forms.check(self.root, tables=tables)
        self.assertEqual(errors, [])
        errors, _ = check_forms.check_stage_parts(path, validated=tables[path])
        self.assertTrue(any("not a list" in e for e in errors), errors)

    def test_validation_never_changes_source_tables_or_metadata_bytes(self):
        paths = [path for path in self.root.rglob("*") if path.is_file()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        self.assertEqual(self.errors(), [])
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in paths})

    def test_file_resource_type_cannot_bypass_table_validation(self):
        self.package(lambda descriptor: descriptor["resources"][0].update({"type": "file"}))
        self.assertTrue(any("declared physical UTF-8 TSV resource" in e for e in self.errors()))

    def test_invalid_schema_metadata_is_not_silently_inferred(self):
        path = self.root / "Platform/01-store/forms/stages.tsv.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema["fields"][0]["constraints"]["pattern"] = "["
        path.write_text(json.dumps(schema), encoding="utf-8")
        self.assertTrue(self.errors())

    def test_nonstring_resource_identity_is_a_metadata_error_not_a_crash(self):
        self.package(lambda descriptor: descriptor["resources"][0].update({"name": []}))
        self.assertTrue(any("selected form group" in e for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
