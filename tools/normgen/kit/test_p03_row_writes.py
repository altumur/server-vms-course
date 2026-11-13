"""P03 GEN01 overlay in the existing families part, using an owned export fixture."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GEN = HERE.parent
GOENV = dict(os.environ, GOFLAGS="-mod=vendor", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


class P03RowWritesKit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="p03-rowwrites-kit-")
        cls.kit = Path(cls.tmp.name) / "kit"
        cls.specs = Path(cls.tmp.name) / "specs"
        cls.specs.mkdir()
        shutil.copytree(ROOT / "Platform", cls.specs / "Platform")
        # This temporary Git export is test input, separate from experiment pins.
        def git(*args):
            return subprocess.check_output(["git", "-c", "user.name=normgen-fixture", "-c",
                                            "user.email=normgen-fixture@example.invalid", *args],
                                           cwd=cls.specs, stderr=subprocess.STDOUT, text=True).strip()
        git("init", "-q")
        files = sorted(str(p.relative_to(cls.specs)) for p in (cls.specs / "Platform").rglob("*") if p.is_file())
        git("add", "--", *files)
        git("commit", "-q", "-m", "Owned P03 normgen export fixture")
        cls.export = git("rev-parse", "HEAD")
        cls.command = [sys.executable, str(HERE / "build_kit.py"), str(cls.kit), "--lesson", "03-worker",
                       "--module", "p03worker/03-worker", "--part", "families", "--part", "stagetests",
                       "--export", cls.export, "--specs", str(cls.specs)]
        cls.build()
        cls.manifest = json.loads((cls.kit / "kit.manifest.json").read_bytes())
        cls.mod = cls.kit / "03-worker"
        cls.report = Path(os.environ["NORMGEN_ROW_WRITES_REPORT_DIR"]) if os.environ.get("NORMGEN_ROW_WRITES_REPORT_DIR") else None
        if cls.report:
            cls.report.mkdir(parents=True, exist_ok=True)
            for name in ("kit.manifest.json", "SOURCE.txt", "KIT.md"):
                (cls.report / name).write_bytes((cls.kit / name).read_bytes())

    @classmethod
    def build(cls):
        done = subprocess.run(cls.command, cwd=ROOT, capture_output=True, text=True)
        if done.returncode: raise AssertionError("owned export KIT build: " + done.stdout + done.stderr)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_private_inputs_closed_overlay_and_compilation(self):
        man = self.manifest
        self.assertEqual(man["export"], self.export)
        self.assertEqual(man["parts"], ["families", "stagetests"])
        paths = {f["path"]: f for f in man["files"]}
        for path, entry in paths.items():
            self.assertEqual(hashlib.sha256((self.kit / path).read_bytes()).hexdigest(), entry["sha256"], path)
        for name in ("row_writes.go", "row_write_runtime.go"):
            path = "03-worker/internal/families/" + name
            self.assertIn(path, paths)
            self.assertFalse(paths[path].get("editable"))
            self.assertEqual(paths[path]["component"], "families")
            self.assertEqual(hashlib.sha256((self.kit / path).read_bytes()).hexdigest(), paths[path]["sha256"])
        own = paths["03-worker/internal/lessonadapter/worker_state_write.go"]
        self.assertTrue(own.get("editable"), "the SDK adapter remains YOURS")
        prov = man["provenance"]["families"]
        forms = {e["path"]: e["sha256"] for e in prov["form"]}
        for path in ("Platform/03-worker/forms/row-write-bindings.tsv", "Platform/03-worker/forms/row-write-bindings.md",
                     "Platform/03-worker/data/state.schema.json", "Platform/common/data/codec.tsv",
                     "Platform/01-store/spec/01-store.api.openapi.yaml", "Platform/02-installer/spec/02.1-installer.schema.json"):
            raw = subprocess.check_output(["git", "show", self.export + ":" + path], cwd=self.specs)
            self.assertEqual(forms[path], hashlib.sha256(raw).hexdigest(), path)
        generators = {e["path"] for e in prov["generators"]}
        self.assertIn("tools/normgen/gen_row_writes.py", generators)
        self.assertIn("tools/normgen/tsv_input.py", generators)
        self.assertIn("tools/normgen/rowwritert/go/runtime.go", {e["path"] for e in prov["handwritten"]})
        for entry in prov["generators"] + prov["handwritten"]:
            self.assertEqual(entry["sha256"], hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry["path"])
        self.assertIn("GEN01", (self.kit / "KIT.md").read_text())
        self.assertIn("not an SDK or stage verdict", (self.kit / "KIT.md").read_text())
        for args in (["go", "vet", "./..."], ["go", "test", "-run", "^$", "./..."]):
            done = subprocess.run(args, cwd=self.mod, env=GOENV, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_rebuild_preserves_yours_refreshes_closed(self):
        own = self.mod / "internal/lessonadapter/worker_state_write.go"
        before = own.read_bytes()
        changed = before + b"\n// user marker: preserved across a second kit build\n"
        own.write_bytes(changed)
        closed = [self.mod / "internal/families/row_writes.go", self.mod / "internal/families/row_write_runtime.go",
                  self.mod / "internal/lessonadapter/lessonadapter.go", self.mod / "internal/stagetests/engine_test.go"]
        original = {p: p.read_bytes() for p in closed}
        for p in closed: p.write_bytes(p.read_bytes() + b"\n// stale closed content\n")
        self.build()
        self.assertEqual(own.read_bytes(), changed)
        for p, data in original.items(): self.assertEqual(p.read_bytes(), data, p)
        # No SDK solution was introduced by this rebuild/ownership probe.
        own.write_bytes(before)

    def test_s5_default_is_executed_failure_not_stage_green(self):
        source = "\n".join(p.read_text() for p in (self.mod / "internal/stagetests").glob("*_test.go"))
        names = re.findall(r"^func (Test\w*StateStartBorn)\(t \*testing.T\)", source, re.M)
        self.assertEqual(len(names), 1, "the ordinary s5 SDK seam must still exist")
        done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^" + names[0] + "$", "./internal/stagetests"],
                              cwd=self.mod, env=GOENV, capture_output=True, text=True)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        events = [json.loads(l) for l in done.stdout.split("\n") if l.startswith("{")]
        if self.report:
            (self.report / "default-s5.jsonl").write_text(done.stdout)
        results = [e["Action"] for e in events if e.get("Test") == names[0] and e["Action"] in ("pass", "fail", "skip")]
        self.assertEqual(results, ["fail"])
        self.assertNotIn("panic:", done.stdout + done.stderr)

    def test_other_lessons_have_no_row_write_generator(self):
        script = "import build_kit; print(','.join(build_kit.regen(['families'])))"
        for key, expected in (("03-worker", "gen_families.py,gen_row_writes.py"), ("04-controller", "gen_families.py"),
                              ("02-installer", "gen_families.py")):
            done = subprocess.run([sys.executable, "-c", script], cwd=HERE,
                                  env=dict(os.environ, NORMGEN_LESSON=key), capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout.strip(), expected)


if __name__ == "__main__": unittest.main()
