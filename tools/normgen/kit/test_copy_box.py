"""The copy environment is a closed handwritten kit part, with explicit host connection."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class CopyBoxKit(unittest.TestCase):
    def test_copy_environment_origin_and_native_build(self):
        with tempfile.TemporaryDirectory(prefix="kit-copy-box-") as tmp:
            dst = Path(tmp) / "kit"
            parts = ("door", "flags", "refusals", "stagetests", "core", "admin", "launch", "box")
            command = [sys.executable, str(HERE / "build_kit.py"), str(dst)]
            command += [word for part in parts for word in ("--part", part)]
            env = dict(os.environ, NORMGEN_LESSON="01-store")
            done = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            manifest = json.loads((dst / "kit.manifest.json").read_bytes())
            box = [f for f in manifest["files"] if f["component"] == "box"]
            self.assertEqual(len(box), 6)
            manual = [f for f in box if f["origin"] == "handwritten"]
            self.assertEqual({Path(f["path"]).name for f in manual},
                             {"copy_storage.go", "copy_validation.go", "copy_import.go", "copy_control.go"})
            self.assertTrue(all(not f.get("editable") for f in box))
            self.assertTrue(all(f["source"].startswith("tools/normgen/copyrt/go/") for f in manual))
            provenance = manifest["provenance"]["box"]
            self.assertEqual(len(provenance["handwritten"]), 4)
            self.assertIn("tools/normgen/test_copy_storage.py", {f["path"] for f in provenance["judges"]})
            doc = (dst / "KIT.md").read_text()
            self.assertIn("CopyStorage", doc)
            self.assertIn("admin.Env.Copy", doc)
            self.assertIn("Backup has no -dir flag", doc)
            (dst / "01-store/go.mod").write_text(f"module {manifest['module']}\n\ngo 1.22\n")
            for args in (["go", "vet", "./internal/box"], ["go", "build", "./cmd/configstore"]):
                done = subprocess.run(args, cwd=dst / "01-store", env=env, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
