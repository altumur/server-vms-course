"""P01 CALL adapter is YOURS; repeated kit builds preserve it and refresh closed files."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class P01Seams(unittest.TestCase):
    def test_owned_adapter_survives_rebuild(self):
        with tempfile.TemporaryDirectory(prefix="kit-p01-seams-") as tmp:
            target = Path(tmp) / "kit"
            cmd = [sys.executable, str(HERE / "build_kit.py"), str(target),
                   "--part", "door", "--part", "flags", "--part", "stagetests"]
            env = dict(os.environ, NORMGEN_LESSON="01-store")
            first = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            manifest = json.loads((target / "kit.manifest.json").read_bytes())
            rel = "01-store/internal/coreadapter/seams.go"
            entry = next(f for f in manifest["files"] if f["path"] == rel)
            self.assertIs(entry.get("editable"), True)
            self.assertTrue(entry["source"].endswith("/coreadapter/seams.go"))
            forms = {f["path"] for f in manifest["provenance"]["stagetests"]["form"]}
            self.assertIn("Platform/01-store/acceptance/3/seams.tsv", forms)
            owned = target / rel
            self.assertIn("YOURS", owned.read_text())
            self.assertIn("ErrNotImplemented", owned.read_text())
            mine = owned.read_bytes() + b"\n// User implementation connects its ordinary native paths here.\n"
            owned.write_bytes(mine)
            closed = [target / "01-store/internal/coreadapter/coreadapter.go",
                      target / "01-store/internal/stagetests/engine_test.go"]
            expected = [p.read_bytes() for p in closed]
            for p in closed:
                p.write_bytes(p.read_bytes() + b"\n// stale closed file\n")
            second = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(owned.read_bytes(), mine)
            self.assertEqual([p.read_bytes() for p in closed], expected)


if __name__ == "__main__":
    unittest.main()
