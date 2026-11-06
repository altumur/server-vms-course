"""Byte proofs for lesson vector TSV transport; semantic JSON stays downstream."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gen_vectors as g


class FallbackTransport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="vectors-transport-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def table(self, columns, rows, declared=(), positional=False):
        rel = Path("Platform/common/vectors/transport/cases.tsv")
        path = self.root / rel
        path.parent.mkdir(parents=True)
        lines = ["# reader fixture"]
        if declared:
            lines.append("# cell-json: " + ",".join(declared))
        lines.append(("# " if positional else "") + "\t".join(columns))
        proofs = []
        for row in rows:
            encoded = [json.dumps(row[n], ensure_ascii=True) if n in declared else row[n] for n in columns]
            lines.append("\t".join(encoded))
            for name in declared:
                sha = hashlib.sha256(row[name].encode("utf-8")).hexdigest()
                proofs.append(f"{rel.as_posix()}\t{len(lines)}\t{name}\t{sha}\t{sha}")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        registry = self.root / "Platform/common/data/cell-json-sha256.tsv"
        registry.parent.mkdir(parents=True)
        registry.write_text("table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n" + "\n".join(proofs) + "\n")
        decl = {"package": "common/transport", "table": path.name, "inputs": list(columns)}
        if positional:
            decl.update(header=None, fields=list(columns))
        return path, decl

    def test_actual_aad_ascii_and_unicode_bytes(self):
        decl = next(d for d in g.WIRE["03-worker"]
                    if d["package"] == "common/sealing" and d["table"] == "aad.tsv")
        _, _, rows = g.read_table(g.ROOT, decl)
        by_case = {row["case"]: (line, row) for line, row in rows}
        for name, key, physical in [("top", b"testsub2/tallies/t1", 4),
                                    ("unicode_row", bytes.fromhex("74657374737562322f74616c6c6965732fd0bad0b0d0bcd0b5d180d0b02d31"), 8)]:
            with self.subTest(case=name):
                line, row = by_case[name]
                self.assertEqual(line, physical)
                self.assertEqual(row["row_key"].encode("utf-8"), key)
                aad = key + b"\x00" + row["pointer"].encode("utf-8")
                self.assertEqual(aad.hex(), row["aad_hex"])
                self.assertEqual(row["path"], '["feed_secret"]')

    def test_transport_once_preserves_inner_json_and_unmarked_quotes(self):
        inner = json.dumps({"quoted": '"inner"', "escape": r"\u043a", "unicode": '\u043a\u0430\u043c\u0435\u0440\u0430'}, ensure_ascii=True)
        expected = {"case": "one", "raw": inner, "quoted": '"literal"'}
        _, decl = self.table(["case", "raw", "quoted"], [expected], declared=("raw",))
        _, _, rows = g.read_table(self.root, decl)
        self.assertEqual(rows, [(4, expected)])
        self.assertIsInstance(rows[0][1]["raw"], str)
        self.assertEqual(rows[0][1]["raw"].encode("utf-8"), inner.encode("utf-8"))
        self.assertEqual(json.loads(rows[0][1]["raw"])["escape"], r"\u043a")

    def test_objectclient_expectations_keep_semantic_quotes(self):
        decl = {"package": "common/object-client", "table": "read.tsv", "inputs": ["expect"]}
        _, _, rows = g.read_table(g.ROOT, decl)
        self.assertEqual(len(rows), 8)
        for _, row in rows:
            expected = row["expect"]
            self.assertTrue(expected.startswith('"') and expected.endswith('"'), expected)
            self.assertIn(json.loads(expected), {"object", "absent", "unknown", "refused"})

    def test_claims_expected_projection_uses_proven_original_json_bytes(self):
        decl = {"package": "common/door-token", "table": "verify.tsv", "inputs": ["claims", "expect"]}
        _, path, rows = g.read_table(g.ROOT, decl)
        rel = path.relative_to(g.ROOT).as_posix()
        registry = g.ROOT / "Platform/common/data/cell-json-sha256.tsv"
        proof_rows = [line.split("\t") for line in registry.read_text().split("\n") if line and not line.startswith("#")]
        proofs = {(r[0], int(r[1]), r[2]): r[3:] for r in proof_rows[1:]}
        for line, row in rows:
            before, decoded = proofs[rel, line, "claims"]
            self.assertEqual(hashlib.sha256(row["claims"].encode("utf-8")).hexdigest(), before)
            self.assertEqual(before, decoded)
            if row["expect"] == "ok":
                self.assertIsInstance(json.loads(row["claims"]), dict)

    def test_valid_transport_does_not_validate_or_repair_invalid_inner_json(self):
        inner = '{"unterminated":'
        _, decl = self.table(["case", "raw"], [{"case": "bad-semantic-json", "raw": inner}], declared=("raw",))
        _, _, rows = g.read_table(self.root, decl)
        self.assertEqual(rows[0][1]["raw"].encode("utf-8"), inner.encode("utf-8"))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(rows[0][1]["raw"])

    def test_positional_keeps_first_row_tabs_cr_and_unicode_separators(self):
        expected = [{"field": "first", "raw": 'a\tb\rc\n\u2028\u000b"x"'},
                    {"field": "second", "raw": r"\u043a"}]
        _, decl = self.table(["field", "raw"], expected, declared=("raw",), positional=True)
        _, _, rows = g.read_table(self.root, decl)
        self.assertEqual(rows, [(4, expected[0]), (5, expected[1])])

    def test_header_subset_validation_and_proof_errors(self):
        path, decl = self.table(["case", "raw", "extra"], [{"case": "one", "raw": "value", "extra": "x"}], declared=("raw",))
        _, _, rows = g.read_table(self.root, dict(decl, inputs=["raw"], input="case"))
        self.assertEqual(rows[0][0], 4)
        for missing in [dict(decl, inputs=["absent"]), dict(decl, input="absent")]:
            with self.assertRaises(g.GenError):
                g.read_table(self.root, missing)
        path.write_bytes(path.read_bytes().replace(b'"value"', b'"other"'))
        with self.assertRaises(g.GenError):
            g.read_table(self.root, decl)

    def test_unmarked_legacy_cells_are_literal_and_cr_is_data(self):
        expected = {"case": "first", "raw": '"quoted"\rraw\u2028\u000b'}
        _, decl = self.table(["case", "raw"], [expected])
        _, _, rows = g.read_table(self.root, decl)
        self.assertEqual(rows, [(3, expected)])

    def test_form_branch_uses_already_decoded_wire_rows(self):
        binding = SimpleNamespace(package="common/transport", table="cases.tsv")
        rows = [(12, {"raw": '"inner JSON string"'})]
        decl = {"_form": True, "_runs": [SimpleNamespace(binding=binding)]}
        with patch("wire.read_rows", return_value=rows) as read_rows, \
                patch("tsv_input.read", side_effect=AssertionError("form rows must not be decoded twice")):
            _, _, actual = g.read_table(self.root, decl)
        read_rows.assert_called_once_with(self.root, binding)
        self.assertIs(actual, rows)

    def test_actual_p02_exec_form_preserves_all_lexical_json_bytes(self):
        import wire

        runs, excluded = wire.expand(g.ROOT, "02-installer")
        selected = [run for run in runs if run.binding.package == "02-installer/exec"]
        self.assertEqual(len(selected), 19)
        self.assertFalse([row for row in excluded if row.binding.package == "02-installer/exec"])
        decl = {"_form": True, "_runs": selected}
        _, path, rows = g.read_table(g.ROOT, decl)
        self.assertEqual([line for line, _ in rows], list(range(4, 23)))
        self.assertEqual([run.lines for run in selected], [[line] for line, _ in rows])
        registry = g.ROOT / "Platform/common/data/cell-json-sha256.tsv"
        proofs = [line.split("\t") for line in registry.read_text().split("\n")
                  if line and not line.startswith("#")][1:]
        proofs = {(row[0], int(row[1]), row[2]): row[3:] for row in proofs}
        rel = path.relative_to(g.ROOT).as_posix()
        for run, (line, row) in zip(selected, rows):
            with self.subTest(case=row["case"]):
                before, decoded = proofs[rel, line, "exec"]
                raw = row["exec"].encode("utf-8")
                self.assertEqual(hashlib.sha256(raw).hexdigest(), before)
                self.assertEqual(before, decoded)
                self.assertEqual(run.arg, raw)
                self.assertEqual(run.value["result"], "refused" if row["expect"] == "@refuse" else "ok")
        by_case = {row["case"]: row["exec"] for _, row in rows}
        self.assertEqual(by_case["one-word"], '"/usr/lib/cam/worker"')
        self.assertEqual(by_case["non-ascii"].encode("utf-8"),
                         b'"/usr/lib/cam/' + bytes.fromhex("d0b2d0bed180d0bad0b5d180") + b'"')
        self.assertEqual(by_case["quote"], r'"/usr/lib/cam/worker \"a b\""')
        self.assertEqual(by_case["tab"], r'"/usr/lib/cam/worker\t-v"')
        self.assertEqual(by_case["newline"], r'"/usr/lib/cam/worker\n-v"')

    def test_actual_p03_creates_key_preserves_stand_and_cells_bytes(self):
        decls = [d for d in g.WIRE["03-worker"] if d["package"] == "03-worker/creates-key"]
        self.assertEqual({d["surface"] for d in decls}, {"stand:creates-key", "vectors"})
        registry = g.ROOT / "Platform/common/data/cell-json-sha256.tsv"
        proof_rows = [line.split("\t") for line in registry.read_text().split("\n")
                      if line and not line.startswith("#")][1:]
        proofs = {(r[0], int(r[1]), r[2]): r[3:] for r in proof_rows}
        surfaces = {}
        for decl in decls:
            pdir, path, rows = g.read_table(g.ROOT, decl)
            self.assertEqual([line for line, _ in rows], list(range(4, 20)))
            self.assertEqual(decl["compare"], "raw")
            rel = path.relative_to(g.ROOT).as_posix()
            for line, row in rows:
                with self.subTest(surface=decl["surface"], case=row["case"]):
                    before, decoded = proofs[rel, line, "input"]
                    self.assertEqual(hashlib.sha256(row["input"].encode("utf-8")).hexdigest(), before)
                    self.assertEqual(before, decoded)
            frames = g.frames_of(decl, rows, pdir)
            self.assertEqual(len(frames), 16)
            for _, row, _, _, (code, value, raw), _ in frames:
                self.assertEqual((code, value, raw), (0, None, row["expect"].encode("utf-8")))
            surfaces[decl["surface"]] = rows
        self.assertEqual(surfaces["stand:creates-key"], surfaces["vectors"])
        by_case = {row["case"]: row for _, row in surfaces["vectors"]}
        unicode = by_case["upper-hex"]
        self.assertIn(bytes.fromhex("d0bad0b0d0bc"), unicode["input"].encode("utf-8"))
        self.assertEqual(unicode["expect"], "testsub-%D0%BA%D0%B0%D0%BC")
        self.assertEqual(json.loads(by_case["percent"]["input"])["fields"]["cam"]["value"], "a b/c%")
        self.assertEqual(by_case["percent"]["expect"], "testsub-a%20b%2Fc%25")
        self.assertEqual(by_case["hyphen-a"]["expect"], "testsub-7-1%2Dx")
        self.assertEqual(by_case["hyphen-b"]["expect"], "testsub-7%2D1-x")
        # Valid outer transport must still fail when its recorded byte proof is wrong.
        sample = by_case["upper-hex"]["input"]
        _, decl = self.table(["case", "input"], [{"case": "upper-hex", "input": sample}], declared=("input",))
        self.assertEqual(g.read_table(self.root, decl)[2][0][1]["input"], sample)
        proof = self.root / "Platform/common/data/cell-json-sha256.tsv"
        sha = hashlib.sha256(sample.encode("utf-8")).hexdigest()
        proof.write_text(proof.read_text().replace(sha, "0" * 64))
        with self.assertRaises(g.GenError):
            g.read_table(self.root, decl)


if __name__ == "__main__":
    unittest.main()
