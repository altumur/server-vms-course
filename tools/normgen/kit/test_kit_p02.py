"""Build non-HTTP P/02 flags, refusals, stagetests, rollout-poll without writecheck. Check module/directory, YOURS lessonadapter scaffolds, vet and failing tests without panic. Reject rollout-poll without stagetests or parts lacking a lesson producer."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ENV = dict(os.environ, NORMGEN_LESSON="02-installer")
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
PARTS = ["flags", "refusals", "stagetests", "rollout-poll"]


def build(dst, parts):
    return subprocess.run([sys.executable, str(HERE / "build_kit.py"), str(dst), *sum((["--part", p] for p in parts), [])],
                          capture_output=True, text=True, env=ENV)


@unittest.skipUnless((ROOT / "Platform/02-installer/forms/operator-commands.tsv").is_file(), "no P/02 forms")
class KitP02(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="kitp02-")
        cls.dst = Path(cls.tmp.name) / "kit"
        done = build(cls.dst, PARTS)
        assert done.returncode == 0, done.stderr
        cls.m = json.loads((cls.dst / "kit.manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest(self):
        self.assertEqual(self.m["module"], "p02installer/02-installer")
        self.assertEqual(self.m["parts"], sorted(PARTS))
        self.assertIsNone(self.m["table"])
        own = sorted(Path(f["path"]).name for f in self.m["files"] if f.get("editable"))
        self.assertEqual(own, ["catalogue.go", "command.go", "installer_role_unit_groups.go", "load.go", "poll.go", "secrets_walk.go"])
        self.assertTrue(all(f["path"].startswith("02-installer/internal/") for f in self.m["files"]))
        for part in PARTS:
            self.assertIn(part, self.m["provenance"])

    def test_vet_and_red(self):
        store = self.dst / "02-installer"
        (store / "go.mod").write_text("module p02installer/02-installer\n\ngo 1.22\n", encoding="utf-8")
        try:
            vet = subprocess.run(["go", "vet", "./..."], cwd=store, capture_output=True, text=True, env=GOENV)
            self.assertEqual(vet.returncode, 0, vet.stderr)
            t = subprocess.run(["go", "test", "-count=1", "./..."], cwd=store, capture_output=True, text=True, env=GOENV)
            self.assertNotEqual(t.returncode, 0)
            self.assertNotIn("panic:", t.stdout)
            self.assertIn("--- FAIL: TestManifestLoad_Verdicts", t.stdout)
            self.assertIn("--- FAIL: TestRolloutPoll_Trace_", t.stdout)
        finally:
            (store / "go.mod").unlink()

    def test_doc(self):
        doc = (self.dst / "KIT.md").read_text(encoding="utf-8")
        self.assertIn("# Kit: the generated parts of P/02 (Go)", doc)
        for head in ("## Part `stagetests`", "## Part `rollout-poll`", "## Part `flags`", "## Part `refusals`"):
            self.assertIn(head, doc)
        self.assertNotIn("writecheck.Check", doc)

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as t:
            done = build(Path(t) / "a", ["flags", "rollout-poll"])
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("--part rollout-poll needs --part stagetests", done.stderr)
            done = build(Path(t) / "b", ["core"])
            self.assertNotEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
