"""P/01 keeps scenario wire bytes through the common source transport."""
import hashlib
from pathlib import Path
import re
import tempfile
import unittest

import gen_stagetests as stages
import tsv_input

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = "Platform/01-store/acceptance/1/scenarios.tsv"


class P01Source(unittest.TestCase):
    def test_all_request_proofs_and_first_row(self):
        source = tsv_input.read(ROOT / SCENARIOS, names=stages.SCENARIO_COLUMNS, positional=True, root=ROOT)
        self.assertEqual(source.declared, ("request",))
        self.assertEqual(len(source.rows), 346)
        proofs = tsv_input.parse((ROOT / tsv_input._PROOF).read_bytes(), names=tsv_input._PROOF_COLUMNS)
        own = [r for _, r in proofs.rows if r["table"] == SCENARIOS]
        self.assertEqual(len(own), 346)
        for (line, row), proof in zip(source.rows, own):
            self.assertEqual((proof["line"], proof["column"]), (str(line), "request"))
            self.assertEqual(hashlib.sha256(row["request"].encode()).hexdigest(), proof["before_sha256"])
        got, rel, sha = stages.read_scenarios(ROOT, "1.1")
        first_line, first = source.rows[0]
        self.assertEqual(got[first["scenario"]][0],
                         (first["step"], first["request"], first["expect"], first_line))
        self.assertEqual(sum(map(len, got.values())), 346)
        self.assertEqual(rel, SCENARIOS)
        self.assertEqual(sha, source.sha256)

    def test_headerless_and_headered_legacy_do_not_rewrite_cells(self):
        request = 'POST /v1/write {"raw":"\\u0436"}\r\v\u2028'
        row = "s1\t1\t" + request + "\t400 {}\n"
        for header in ("# scenario\tstep\trequest\texpect\n", "scenario\tstep\trequest\texpect\n"):
            with self.subTest(header=header), tempfile.TemporaryDirectory(prefix="p01-source-") as temp:
                root = Path(temp)
                path = root / SCENARIOS
                path.parent.mkdir(parents=True)
                path.write_bytes((header + row).encode())
                got, _, _ = stages.read_scenarios(root, "1.1")
                self.assertEqual(got, {"s1": [("1", request, "400 {}", 2)]})

    def test_wrong_width_is_a_form_error(self):
        with tempfile.TemporaryDirectory(prefix="p01-width-") as temp:
            root = Path(temp)
            path = root / SCENARIOS
            path.parent.mkdir(parents=True)
            for text in ("s1\t1\tGET /\n", "s1\t1\tGET /\t200 {}\textra\n"):
                path.write_text(text)
                with self.assertRaisesRegex(stages.GenError, "cells, expected 4"):
                    stages.read_scenarios(root, "1.1")

    def test_p01_stage_provenance_pins_helper_and_proof(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent / "kit"))
        import build_kit
        p = build_kit.provenance(["stagetests"], [], {})["stagetests"]
        self.assertIn("tools/normgen/tsv_input.py", {r["path"] for r in p["generators"]})
        forms = {r["path"]: r["sha256"] for r in p["form"]}
        self.assertEqual(forms[SCENARIOS], hashlib.sha256((ROOT / SCENARIOS).read_bytes()).hexdigest())
        self.assertIn(tsv_input._PROOF.as_posix(), forms)
        self.assertIn(tsv_input._CONTRACT.as_posix(), forms)

    def test_model_facing_kit_text_uses_english_source_references(self):
        import gen_admin, gen_box, gen_core, gen_flags, gen_launch, gen_refusals, gen_tests
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent / "kit"))
        import build_kit
        text = "\n".join(getattr(m, name) for m, name in (
            (build_kit, "KIT_MD"), (build_kit, "KIT_DOOR_MD"), (gen_admin, "KIT_MD"),
            (gen_box, "KIT_MD"), (gen_core, "KIT_MD"), (gen_flags, "KIT_MD"),
            (gen_launch, "KIT_MD"), (gen_refusals, "KIT_MD"), (gen_tests, "KIT_MD"),
            (gen_tests, "KIT_MD_STAGETESTS")))
        text += "\n".join(p.read_text() for p in sorted(build_kit.EXAMPLES.glob("*.go")))
        self.assertIsNone(re.search('[\u0410-\u042f\u0430-\u044f\u0401\u0451]', text))
        self.assertIn('P/01.2 N3 «check»', text)


if __name__ == "__main__":
    unittest.main()
