"""Тесты build_kit --export (Архитектор 2026-11-05): входы — Platform/ выгрузки из git, код — чистый HEAD курса; оба sha
в манифесте и SOURCE.txt, без -dirty; правки в tools/normgen — отказ; дерево курса не меняется.

Курс и выгрузка — временные git-репозитории: tools/normgen рабочего дерева (файлы git ls-files) и Platform/ выгрузки
EXPORT из ~/cammeta-specs (или CAMMETA_SPECS)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kit  # noqa: E402

ROOT = build_kit.ROOT
EXPORT = "4c1015709945fd5dc9434a2aca4d554aeaaa1b65"
MODULE = "p01store/01-store"
PARTS = ["door", "flags", "refusals", "launch", "vectors", "stagetests", "core", "families"]


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True).stdout.decode().strip()


def repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    return path


@unittest.skipUnless((build_kit.SPECS / ".git").exists(), "no cammeta-specs")
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
        git(cls.course, "add", "-A")
        git(cls.course, "commit", "-q", "-m", "course")
        cls.course_sha = git(cls.course, "rev-parse", "HEAD")
        cls.specs = repo(t / "specs")
        build_kit.unpack(build_kit.SPECS, EXPORT, "Platform", cls.specs)
        git(cls.specs, "add", "-A")
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
        """Шапка vectortests называет sha256 stages.tsv выгрузки, не курса."""
        stages = (self.specs / "Platform/01-store/forms/stages.tsv").read_bytes()
        doc = (self.dst / "01-store/internal/vectortests/doc.go").read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(stages).hexdigest(), doc)

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
