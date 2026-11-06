"""Common source boundaries: transport versus semantic JSON and declared units."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import gen_checks
import gen_families as families
import tsv_input
import wire

ROOT = Path(__file__).resolve().parents[2]
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off")

UNIT_PROBE = r'''package families
import ("reflect"; "testing")
func TestDeclaredUnitPriority(t *testing.T) {
 f := &Family{Outcomes: []Outcome{
  {Path:"", Reader:"*", Priority:1, Unit:unitRow},
  {Path:"/x", Reader:"*", Priority:1, Unit:unitRow},
 }}
 if got:=f.OutcomesFor([]string{"/x"}, "console"); !reflect.DeepEqual(got, []string{"", "/x"}) {
  t.Fatalf("row-level covering outcomes: %v", got)
 }
 f.Outcomes[1].Unit=unitField
 if got:=f.OutcomesFor([]string{"/x"}, "console"); !reflect.DeepEqual(got, []string{"/x"}) {
  t.Fatalf("field outcome: %v", got)
 }
 if got:=f.OutcomesFor([]string{"/y"}, "console"); !reflect.DeepEqual(got, []string{""}) {
  t.Fatalf("row fallback: %v", got)
 }
}
'''


class SemanticBoundaries(unittest.TestCase):
    def test_objectclient_read_inner_quotes(self):
        table = tsv_input.parse('# cell-json: expect\nexpect\n"\\\"object\\\""\n')
        text = table.rows[0][1]["expect"]
        self.assertEqual(text, '"object"')
        self.assertEqual(wire.decode(text, "json", "ObjectClient/read"), "object")

    def test_valid_outer_keeps_invalid_inner_for_semantic_parser(self):
        table = tsv_input.parse('# cell-json: raw\nraw\n"{not-json"\n')
        text = table.rows[0][1]["raw"]
        self.assertEqual(wire.decode(text, "text", "negative input"), "{not-json")
        with self.assertRaises(wire.WireError):
            wire.decode(text, "json", "negative input")

    def test_cel_sees_decoded_source_and_sha_is_physical(self):
        path = ROOT / "Platform/01-store/forms/write-checks.tsv"
        original = path.read_bytes()
        raw = tsv_input.parse(original, names=gen_checks.COLUMNS)
        encoded = []
        for line in original.decode().split("\n"):
            if not line or line.startswith("#") or line.split("\t") == gen_checks.COLUMNS:
                encoded.append(line)
                continue
            cells = line.split("\t")
            i = gen_checks.COLUMNS.index("when")
            cells[i] = json.dumps(cells[i], ensure_ascii=True)
            encoded.append("\t".join(cells))
        text = "# cell-json: when\n" + "\n".join(encoded)
        decoded = tsv_input.parse(text, names=gen_checks.COLUMNS)
        self.assertEqual([r for _, r in decoded.rows], [r for _, r in raw.rows])
        base, marked = gen_checks.Table(original), gen_checks.Table(decoded)
        self.assertEqual(base.rows, marked.rows)
        self.assertEqual(marked.sha256, decoded.sha256)
        self.assertNotEqual(base.sha256, marked.sha256)


class DeclaredUnitPriority(unittest.TestCase):
    def test_flat_and_schema_runtime(self):
        if shutil.which("go") is None:
            self.skipTest("Go unavailable")
        for doc, runtime in ((False, families.RUNTIME_FLAT), (True, families.RUNTIME_DOC)):
            with self.subTest(schema_mode=doc), tempfile.TemporaryDirectory(prefix="family-unit-") as temp:
                dst = Path(temp)
                with patch.object(families, "DOC_MODE", doc), patch.object(families, "RUNTIME", runtime):
                    files = families.render("01")
                self.assertIn('const unitRow = "row"', files["families.go"])
                self.assertIn('const unitField = "field"', files["families.go"])
                for name, text in files.items():
                    (dst / name).write_text(text)
                (dst / "go.mod").write_text("module normgen/unitprobe\n\ngo 1.22\n")
                (dst / "units_test.go").write_text(UNIT_PROBE)
                done = subprocess.run(["go", "test", "-count=1", "."], cwd=dst, env=ENV,
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class Provenance(unittest.TestCase):
    def test_writecheck_pins_transport_and_physical_proofs(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent / "kit"))
        import build_kit
        prov = build_kit.provenance(["writecheck"], [], {})["writecheck"]
        self.assertIn("tools/normgen/tsv_input.py", {f["path"] for f in prov["generators"]})
        forms = {f["path"]: f["sha256"] for f in prov["form"]}
        proof = "Platform/common/data/cell-json-sha256.tsv"
        self.assertEqual(forms[proof], tsv_input.hashlib.sha256((ROOT / proof).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
