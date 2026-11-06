"""Independent source fixtures and byte-preserving TSV transport boundaries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import tsv_input as t

ROOT = Path(__file__).resolve().parents[2]


class SourceFixtures(unittest.TestCase):
    def test_column_names_are_a_sequence(self):
        for names in ("raw", b"raw"):
            with self.subTest(names=names), self.assertRaises(t.TSVError):
                t.parse("x\n", names=names, positional=True)

    def test_author_cases(self):
        path = ROOT / "Platform/common/vectors/source-cells/cases.json"
        fixtures = json.loads(path.read_bytes())
        self.assertGreaterEqual(len(fixtures), 29)
        for f in fixtures:
            with self.subTest(case=f["case"]):
                args = dict(names=f["columns"], positional=f["positional"], where=f["case"])
                if f["valid"]:
                    got = t.parse(f["text"], **args)
                    self.assertEqual(list(got.declared), f["declared"])
                    self.assertEqual([[n, r] for n, r in got.rows], f["rows"])
                else:
                    with self.assertRaises(t.TSVError):
                        t.parse(f["text"], **args)

    def test_lf_only_and_unmarked_cells(self):
        for value in ("a\u2028b", "a\vb", "a\rb", '"object"', r'\u0436', "\u0430a", "\u00e9e\u0301"):
            with self.subTest(value=value):
                data = ("raw\n" + value + "\n").encode("utf-8")
                got = t.parse(data)
                self.assertEqual(got.rows, [(2, {"raw": value})])
                self.assertEqual(got.raw, data)
                self.assertEqual(got.sha256, hashlib.sha256(data).hexdigest())
                with tempfile.TemporaryDirectory(prefix="tsv-io-") as temp:
                    path = Path(temp) / "data.tsv"
                    path.write_bytes(data)
                    self.assertEqual(t.read(path).raw, data)
                    self.assertEqual(t.read(path).rows, got.rows)

    def test_positional_comment_header_and_first_row(self):
        source = '# cell-json: request\n# scenario\tstep\trequest\texpect\ns1\t1\t"\\u0436"\tok\ns1\t2\t"\\\\u0436"\tok\n'
        got = t.parse(source, names=["scenario", "step", "request", "expect"], positional=True)
        self.assertEqual([n for n, r in got.rows], [3, 4])
        self.assertEqual([r["request"] for n, r in got.rows], ["\u0436", r"\u0436"])

    def test_logical_row_is_not_resplit_or_dropped(self):
        values = ["", "# a comment", "raw", "a\tb\nc\vd\u2028e", r'"\u0436"']
        source = '# cell-json: raw\n' + "\n".join(json.dumps(x, ensure_ascii=True) for x in values) + "\n"
        got = t.parse(source, names=["raw"], positional=True)
        self.assertEqual([r["raw"] for n, r in got.rows], values)
        self.assertEqual([n for n, r in got.rows], list(range(2, len(values) + 2)))
        with self.assertRaises(t.TSVError):
            t.parse(got)

    def test_outer_transport_is_not_inner_semantic_json(self):
        for value in ('"object"', '{not-json', '{"a":1,"a":2}', r'"\ud800"'):
            with self.subTest(value=value):
                source = '# cell-json: raw\nraw\n' + json.dumps(value) + "\n"
                self.assertEqual(t.parse(source).rows, [(3, {"raw": value})])

    def test_all_frozen_cells_match_author_proofs(self):
        proof = t.parse((ROOT / t._PROOF).read_bytes(), names=t._PROOF_COLUMNS)
        layouts = {}
        for _, binding in t.parse((ROOT / "Platform/common/vectors/wire.tsv").read_bytes()).rows:
            fields = binding["header"].split(",")
            owner, package = binding["package"].split("/", 1)
            layouts[f"Platform/{owner}/vectors/{package}/{binding['table']}"] = fields
        tables = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "Platform/common/vectors").rglob("*.tsv")
                        if any(line.startswith(b"# cell-json") for line in p.read_bytes().split(b"\n")))
        count = 0
        for rel in tables:
            fields = layouts.get(rel)
            positional = fields is not None and fields[0] == "-"
            got = t.read(ROOT / rel, names=fields[1:] if positional else fields,
                         positional=positional, root=ROOT)
            count += len(got.rows) * len(got.declared)
            self.assertIn(ROOT / t._PROOF, got.sources)
        self.assertEqual(len(tables), 6)
        self.assertEqual(count, 351)
        self.assertEqual(sum(row["table"].startswith("Platform/common/") for _, row in proof.rows), count)


class ProofErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tsv-proof-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "Platform/common/vectors/x/cases.tsv"
        self.path.parent.mkdir(parents=True)
        self.path.write_text('# cell-json: raw\nraw\n"\\u0436"\n')
        self.proof = self.root / t._PROOF
        self.proof.parent.mkdir(parents=True)
        sha = hashlib.sha256("\u0436".encode()).hexdigest()
        self.entry = f"{self.path.relative_to(self.root)}\t3\traw\t{sha}\t{sha}\n"
        self.header = "\t".join(t._PROOF_COLUMNS) + "\n"

    def test_missing_duplicate_extra_and_changed_proof(self):
        for body in ("", self.entry * 2, self.entry + self.entry.replace("\t3\t", "\t4\t"),
                     self.entry.replace("raw", "other"), self.entry.replace("\t3\t", "\t2\t")):
            with self.subTest(body=body):
                self.proof.write_text(self.header + body)
                with self.assertRaises(t.TSVError):
                    t.read(self.path, root=self.root)
        self.proof.write_text(self.header + self.entry)
        self.assertEqual(t.read(self.path, root=self.root).rows, [(3, {"raw": "\u0436"})])
        self.path.write_text('# cell-json: raw\nraw\n"x"\n')
        with self.assertRaises(t.TSVError):
            t.read(self.path, root=self.root)

    def test_marked_file_requires_root_and_proof(self):
        with self.assertRaises(t.TSVError):
            t.read(self.path)
        with self.assertRaises(t.TSVError):
            t.read(self.path, root=self.root)


if __name__ == "__main__":
    unittest.main()
