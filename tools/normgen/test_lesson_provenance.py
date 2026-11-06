"""Lesson provenance keeps physical TSV, proof/contract and the shared decoder pin."""
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROOF = "Platform/common/data/cell-json-sha256.tsv"
CONTRACT = "Platform/common/contracts/source-cells.md"
HELPER = "tools/normgen/tsv_input.py"
PARTS = {
    "01-store": [("gen_flags", None), ("gen_refusals", None), ("gen_core", None),
                 ("gen_box", None), ("gen_launch", None)],
    "02-installer": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                     ("gen_vectors", None), ("gen_manifest", None), ("gen_rollout", None)],
    "03-worker": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                  ("gen_vectors", None), ("gen_machine", "slot-capture")],
    "04-controller": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                      ("gen_vectors", None), ("gen_machine", "slot-fate"), ("gen_machine", "slot-release")],
    "05-resource": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                    ("gen_vectors", None), ("gen_door_lesson", None)],
    "06-console": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                   ("gen_vectors", None), ("gen_door_lesson", None)],
    "08-domain": [("gen_vectors", None), ("gen_door_lesson", None), ("gen_versioned_doors", None)],
    "09-agent": [("gen_flags", None), ("gen_refusals", None), ("gen_cmdtests", None),
                 ("gen_vectors", None), ("gen_door_lesson", None)],
    "10-domain-console": [("gen_vectors", None), ("gen_door_lesson", None)],
}


class LessonProvenance(unittest.TestCase):
    def test_physical_inputs_and_decoder_are_pinned(self):
        for lesson, parts in PARTS.items():
            with self.subTest(lesson=lesson):
                script = """import importlib,json
parts=json.loads(__import__('sys').argv[1])
out=[]
for name,arg in parts:
    module=importlib.import_module(name)
    out.append([name,module.provenance(arg) if arg else module.provenance()])
print(json.dumps(out))
"""
                done = subprocess.run([sys.executable, "-c", script, json.dumps(parts)], cwd=HERE,
                                      env=dict(os.environ, NORMGEN_LESSON=lesson), capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                for name, provenance in json.loads(done.stdout):
                    with self.subTest(generator=name):
                        forms = provenance["form"]
                        if isinstance(forms, dict):
                            forms = [forms]
                        by_path = {entry["path"]: entry["sha256"] for entry in forms}
                        self.assertEqual(len(by_path), len(forms), "duplicate input pointer")
                        if lesson == "06-console" and name == "gen_door_lesson":
                            self.assertTrue({"Platform/05-resource/spec/05-resource.api.openapi.yaml",
                                             "Platform/08-domain/spec/08-domain.api.openapi.yaml"} <= set(by_path))
                        for entry in forms:
                            data = (ROOT / entry["path"]).read_bytes()
                            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                            if entry["path"].endswith(".tsv"):
                                self.assertIn(PROOF, by_path)
                                if any(line.startswith(b"# cell-json:") for line in data.split(b"\n")):
                                    self.assertIn(CONTRACT, by_path)
                        generators = {entry["path"]: entry["sha256"] for entry in provenance["generators"]}
                        self.assertEqual(generators[HELPER], hashlib.sha256((ROOT / HELPER).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
