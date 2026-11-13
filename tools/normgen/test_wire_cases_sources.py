"""The public and judge wire carriers share grammar, identity and source locations."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_forms
import source_cells
import wire
from check_spec import Check

MOVED = {
    ("common/events-merge", "cases.tsv", "vectors"),
    ("common/row-check", "cases.tsv", "vectors"),
    ("common/secret-in", "cases.tsv", "vectors"),
}


def records(path):
    data = [(no, line.split("\t")) for no, line in enumerate(path.read_text().split("\n"), 1)
            if line and not line.startswith("#")]
    return [(no, dict(zip(data[0][1], row))) for no, row in data[1:]]


class ActualWireSources(unittest.TestCase):
    def test_both_actual_carriers_are_selected(self):
        self.assertEqual([p.name for p in check_forms.wire_forms(ROOT)],
                         ["wire.tsv", "wire.cases.tsv"])

    def test_three_relocated_bindings_are_parsed(self):
        selected = {key[:2] for key in MOVED}
        bindings = wire.parse(ROOT, keys=selected)
        self.assertEqual({b.key for b in bindings}, MOVED)

    def test_actual_pair_closed_grammar_and_source_locations(self):
        seen, total = set(), 0
        for path in check_forms.wire_forms(ROOT):
            errors, stats = check_forms.check_wire(path, seen=seen)
            self.assertEqual(errors, [])
            total += stats["wire_bindings"]
        self.assertEqual(total, 97)
        bindings = wire.parse(ROOT)
        self.assertEqual(len(bindings), 97)
        self.assertEqual({(b.source, b.line) for b in bindings if b.key in MOVED},
                         {(wire.CASE_FORM, n) for n in (4, 5, 6)})

    def test_vector_provenance_names_both_actual_physical_inputs(self):
        import gen_vectors
        for owner in ("02-installer", "06-console", "08-domain"):
            with self.subTest(owner=owner):
                decls = [] if owner in ("02-installer", "06-console") else [
                    {"_form": True, "package": "common/probe"}]
                with patch.object(gen_vectors, "L", SimpleNamespace(key=owner)), \
                     patch.object(gen_vectors, "plan", return_value=(decls, [])), \
                     patch.object(wire, "expand", return_value=([], [])), \
                     patch.object(gen_vectors, "read_table", return_value=([], ROOT / wire.FORM)):
                    provenance = gen_vectors.provenance()
                forms = {item["path"] for item in provenance["form"]}
                self.assertIn(wire.FORM, forms)
                self.assertIn(wire.CASE_FORM, forms)

    def test_three_relocated_positional_headers_remain_bound(self):
        headers = source_cells.wire_headers(ROOT, source_scopes=("Platform",))
        for _, row in records(ROOT / "Platform/common/vectors/wire.cases.tsv"):
            owner, name = row["package"].split("/", 1)
            path = Path("Platform") / owner / "vectors" / name / row["table"]
            columns = row["header"].split(",")
            self.assertEqual(headers[path],
                             (columns[1:] if columns[0] == "-" else columns, columns[0] == "-"))


class SyntheticWireSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "Platform/common/vectors"
        pkg = self.base / "probe"
        pkg.mkdir(parents=True)
        (self.root / "Platform/lessons.tsv").write_bytes((ROOT / "Platform/lessons.tsv").read_bytes())
        (pkg / "README.md").write_text("# Probe\n")
        for name in ("a", "b"):
            (pkg / f"{name}.tsv").write_text('case\tinput\texpect\nx\t{}\t{"ok":true}\n')
        (self.base / "consumers.tsv").write_text(
            "package\ttable\tlesson\tnorm\n" +
            "".join(f"common/probe\t{x}.tsv\t01-store\tcommon/vectors/probe/README.md\n" for x in ("a", "b")))
        self.public, self.cases = self.base / "wire.tsv", self.base / "wire.cases.tsv"
        self.write(self.public, self.row("a"))
        self.write(self.cases, self.row("b"))

    def row(self, name):
        return ["common/probe", name + ".tsv", "vectors", "case,input,expect",
                json.dumps([{"variant": "", "cells": {"input": {"column": "input"}}}]),
                "{}", json.dumps([{"variant": "", "code": 0, "value": {"column": "expect", "decode": "json"}}]),
                "value", "[]", '{"type":"object","frame":"json-lf"}', "common/vectors/probe/README.md#probe"]

    def write(self, path, *rows):
        path.write_text("\t".join(check_forms.WIRE_COLUMNS) + "\n" +
                        "".join("\t".join(row) + "\n" for row in rows), encoding="utf-8")

    def checker_errors(self):
        seen, errors, stats = set(), [], {}
        for path in check_forms.wire_forms(self.root):
            found, counts = check_forms.check_wire(path, seen=seen)
            errors.extend(found)
            for name, value in counts.items():
                stats[name] = stats.get(name, 0) + value
        return errors, stats

    def test_both_carriers_same_grammar_coordinates_and_additive_counts(self):
        self.assertEqual([b.key for b in wire.parse(self.root)],
                         [("common/probe", "a.tsv", "vectors"), ("common/probe", "b.tsv", "vectors")])
        self.assertEqual([(b.source, b.line) for b in wire.parse(self.root)],
                         [(wire.FORM, 2), (wire.CASE_FORM, 2)])
        errors, stats = self.checker_errors()
        self.assertEqual(errors, [])
        self.assertEqual(stats["wire_bindings"], 2)
        self.assertEqual(stats["wire_calls"], 2)
        headers = source_cells.wire_headers(self.root)
        self.assertEqual(headers[Path("Platform/common/vectors/probe/a.tsv")],
                         headers[Path("Platform/common/vectors/probe/b.tsv")])

    def test_checker_wire_loop_shares_identity_and_sums_statistics(self):
        checker = Check(self.root, scope="platform")
        checker.check_forms()
        self.assertEqual(checker.errors, [])
        self.assertEqual(checker.stats["wire_bindings"], 2)
        self.assertEqual(checker.stats["wire_calls"], 2)
        self.write(self.cases, self.row("a"))
        checker = Check(self.root, scope="platform")
        checker.check_forms()
        self.assertTrue(any("triple" in str(error) for error in checker.errors))

    def test_cross_file_duplicate_is_rejected_even_outside_selection(self):
        self.write(self.cases, self.row("a"))
        self.assertTrue(any("triple" in e for e in self.checker_errors()[0]))
        with self.assertRaisesRegex(wire.WireError, "wire.cases.tsv:2: second row"):
            wire.parse(self.root, keys=set())
        with self.assertRaisesRegex(ValueError, "wire.cases.tsv:2:.*triple"):
            source_cells.wire_headers(self.root)

    def test_same_file_duplicate_remains_rejected(self):
        self.write(self.cases, self.row("b"), self.row("b"))
        self.assertTrue(any("triple" in e for e in self.checker_errors()[0]))
        with self.assertRaisesRegex(wire.WireError, "second row"):
            wire.parse(self.root)
        with self.assertRaisesRegex(ValueError, "triple"):
            source_cells.wire_headers(self.root)

    def test_conflicting_positional_header_is_still_rejected(self):
        row = self.row("a")
        row[2] = "layout"
        row[3] = "case,different,expect"
        self.write(self.cases, row)
        with self.assertRaisesRegex(ValueError, "conflicting wire column"):
            source_cells.wire_headers(self.root)

    def test_companion_absence_is_legacy_or_m_only_not_full_source_coverage(self):
        self.cases.unlink()
        self.assertEqual([p.name for p in check_forms.wire_forms(self.root)], ["wire.tsv"])
        self.assertEqual(len(wire.parse(self.root)), 1)
        self.assertEqual(self.checker_errors()[0], [])
        self.assertNotIn(Path("Platform/common/vectors/probe/b.tsv"), source_cells.wire_headers(self.root))

    def test_missing_canonical_is_not_replaced_by_companion(self):
        self.public.unlink()
        self.assertTrue(self.checker_errors()[0])
        with self.assertRaises(wire.WireError):
            wire.parse(self.root)
        with self.assertRaises(ValueError):
            source_cells.wire_headers(self.root)

    def test_malformed_companion_header_and_row_width(self):
        for content in ("wrong\theader\n", "\t".join(check_forms.WIRE_COLUMNS) + "\nx\ty\n"):
            with self.subTest(content=content[:12]):
                self.cases.write_text(content)
                self.assertTrue(self.checker_errors()[0])
                with self.assertRaises(wire.WireError):
                    wire.parse(self.root)
                with self.assertRaises(ValueError):
                    source_cells.wire_headers(self.root)

    def test_companion_json_uses_same_closed_grammar(self):
        for column, value in (("inputs", '{"unknown":1}'), ("native", '{"type":"object","extra":true}'),
                              ("files", '{"x":NaN}')):
            with self.subTest(column=column):
                row = self.row("b")
                row[check_forms.WIRE_COLUMNS.index(column)] = value
                self.write(self.cases, row)
                self.assertTrue(self.checker_errors()[0])
                with self.assertRaises(wire.WireError):
                    wire.parse(self.root)

    def test_companion_encoding_and_line_endings_are_not_normalized(self):
        good = self.cases.read_bytes()
        for bad in (b"\xef\xbb\xbf" + good, good.replace(b"\n", b"\r\n"), b"\xff"):
            with self.subTest(prefix=bad[:3]):
                self.cases.write_bytes(bad)
                self.assertTrue(self.checker_errors()[0])
                with self.assertRaises(wire.WireError):
                    wire.parse(self.root)
                with self.assertRaises(ValueError):
                    source_cells.wire_headers(self.root)

    def test_nonfile_and_broken_companion_are_not_silently_dropped(self):
        self.cases.unlink()
        for broken in (False, True):
            with self.subTest(broken=broken):
                if broken:
                    self.cases.symlink_to(self.base / "absent")
                else:
                    self.cases.mkdir()
                self.assertIn(self.cases, check_forms.wire_forms(self.root))
                self.assertTrue(self.checker_errors()[0])
                with self.assertRaises(wire.WireError):
                    wire.parse(self.root)
                with self.assertRaises(ValueError):
                    source_cells.wire_headers(self.root)
                if broken:
                    self.cases.unlink()
                else:
                    self.cases.rmdir()

    def test_binding_error_reports_companion_source(self):
        binding = wire.parse(self.root)[1]
        (self.base / "probe/b.tsv").unlink()
        with self.assertRaisesRegex(wire.WireError, "wire.cases.tsv:2:"):
            wire.read_rows(self.root, binding)


if __name__ == "__main__":
    unittest.main()
