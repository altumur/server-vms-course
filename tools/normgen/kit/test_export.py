"""Test build_kit --export (Architect, 2026-11-05): Platform inputs come from the export Git commit, code from a clean course HEAD, both SHAs recorded without -dirty in the manifest and SOURCE.txt. Dirty tools/normgen refuses; the course tree stays unchanged. Temporary repositories contain tracked generator files and an owned current Platform snapshot; no experiment pin is selected."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kit  # noqa: E402

ROOT = build_kit.ROOT
MODULE = "p01store/01-store"
PARTS = ["door", "flags", "refusals", "launch", "vectors", "stagetests", "core", "families", "admin"]


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True).stdout.decode().strip()


def repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    return path


class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="kit-export-test-")
        t = Path(cls.tmp.name)
        cls.course = repo(t / "course")
        for rel in git(ROOT, "ls-files", "tools/normgen").split("\n"):
            src = ROOT / rel
            if src.is_file():
                (cls.course / rel).parent.mkdir(parents=True, exist_ok=True)
                (cls.course / rel).write_bytes(src.read_bytes())
        git(cls.course, "add", "--", *git(ROOT, "ls-files", "tools/normgen").splitlines())
        git(cls.course, "commit", "-q", "-m", "course")
        cls.course_sha = git(cls.course, "rev-parse", "HEAD")
        cls.specs = repo(t / "specs")
        # Owned current-source export fixture, independent of any experiment pin.
        shutil.copytree(ROOT / "Platform", cls.specs / "Platform")
        fixture_stage = cls.specs / "Platform/01-store/forms/stages.kit.tsv"
        fixture_stage.write_text("# Owned export fixture\n" + fixture_stage.read_text())
        git(cls.specs, "add", "--", *sorted(str(p.relative_to(cls.specs)) for p in (cls.specs / "Platform").rglob("*") if p.is_file()))
        git(cls.specs, "commit", "-q", "-m", "export")
        cls.export = git(cls.specs, "rev-parse", "HEAD")
        cls.before = git(ROOT, "status", "--porcelain")
        cls.dst = t / "kit"
        cls.manifest = build_kit.build_from_export(cls.dst, MODULE, PARTS, {}, cls.export, cls.specs, cls.course)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_both_sha_no_dirty(self):
        self.assertEqual(self.manifest["commit"], self.course_sha)
        self.assertEqual(self.manifest["export"], self.export)
        src = (self.dst / "SOURCE.txt").read_text(encoding="utf-8")
        self.assertIn(f"export {self.export}", src)
        self.assertIn(f"course {self.course_sha} (clean)", src)
        self.assertIn(f"--export {self.export}", src)
        self.assertNotIn("-dirty", src + json.dumps(self.manifest))

    def test_inputs_are_the_export(self):
        """The vectortests header must name the export's stages.tsv SHA, not the course's."""
        stages = (self.specs / "Platform/01-store/forms/stages.kit.tsv").read_bytes()
        doc = (self.dst / "01-store/internal/vectortests/doc.go").read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(stages).hexdigest(), doc)

    def test_legacy_optional_registries(self):
        import gen_tests
        consumers = gen_tests.common_vectors.CONSUMERS
        lessons = gen_tests.vector_consumers.LESSONS
        with tempfile.TemporaryDirectory(prefix="export-no-registries-") as tmp:
            root = Path(tmp)
            shutil.copytree(self.specs / "Platform", root / "Platform")
            (root / consumers).unlink(missing_ok=True)
            (root / lessons).unlink(missing_ok=True)
            paths = gen_tests.sources("vectors", root=root)
            self.assertIn(root / gen_tests.STAGES, paths)
            self.assertNotIn(root / consumers, paths)
            self.assertNotIn(root / lessons, paths)
            self.assertTrue(gen_tests.render(root), "legacy BEFORE_FORM still emits real vector tests")
            # A present consumers form still requires the lesson registry.
            (root / consumers).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / consumers, root / consumers)
            with self.assertRaisesRegex(gen_tests.common_vectors.CommonError, "no Platform/lessons.tsv"):
                gen_tests.sources("vectors", root=root)

    def test_kit_builds(self):
        store = self.dst / "01-store"
        (store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
        try:
            done = subprocess.run(["go", "vet", "./..."], cwd=store, capture_output=True, text=True)
        finally:
            (store / "go.mod").unlink()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.manifest["parts"], ["writecheck", *sorted(PARTS)])

    def test_course_tree_untouched(self):
        self.assertEqual(git(ROOT, "status", "--porcelain"), self.before)

    def test_dirty_refused(self):
        f = self.course / "tools/normgen/README.md"
        text = f.read_bytes()
        f.write_bytes(text + b"\nedit\n")
        try:
            with self.assertRaisesRegex(build_kit.KitError, "clean commit"):
                build_kit.build_from_export(Path(self.tmp.name) / "k2", MODULE, [], {}, self.export, self.specs,
                                            self.course)
        finally:
            f.write_bytes(text)

    def test_bad_export(self):
        with self.assertRaisesRegex(build_kit.KitError, "not a commit"):
            build_kit.build_from_export(Path(self.tmp.name) / "k3", MODULE, [], {}, "0" * 40, self.specs, self.course)


if __name__ == "__main__":
    unittest.main()
