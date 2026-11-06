"""Test lesson selection/paths (ADR-0125 addendum 5, item 2): remove --lesson from argv, then use environment/default; read lessons.tsv; reject unsupported lessons by name for P/01-only declarations. Explicit01-store must preserve default output byte for byte."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402

PY = sys.executable
# P/01-only norm/vector/frame declarations must reject another lesson.
DECLARED_P01 = ("gen_core.py", "gen_admin.py", "gen_launch.py", "gen_tests.py")


def run(args, env=None, cwd=HERE):
    e = dict(os.environ)
    e.pop(lesson.ENV, None)
    e.update(env or {})
    return subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True, env=e)


class Select(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.get(lesson.ENV)
        os.environ.pop(lesson.ENV, None)

    def tearDown(self):
        os.environ.pop(lesson.ENV, None)
        if self.saved is not None:
            os.environ[lesson.ENV] = self.saved

    def test_default_and_strip(self):
        argv = ["gen", "out-dir"]
        self.assertEqual(lesson.select(argv).key, "01-store")
        argv = ["gen", "--lesson", "02-installer", "out-dir"]
        self.assertEqual(lesson.select(argv).key, "02-installer")
        self.assertEqual(argv, ["gen", "out-dir"])                 # Preserve generator positional arguments.
        argv = ["gen", "--lesson=05-resource"]
        self.assertEqual(lesson.select(argv).key, "05-resource")
        self.assertEqual(argv, ["gen"])
        self.assertEqual(os.environ[lesson.ENV], "05-resource")   # Child processes inherit the same lesson.

    def test_env(self):
        os.environ[lesson.ENV] = "03-worker"
        self.assertEqual(lesson.select(["gen"]).key, "03-worker")

    def test_unknown(self):
        for bad in ("11-nope", "store", "1-store", "01_store"):
            with self.assertRaises(lesson.LessonError):
                lesson.select(["gen", "--lesson", bad])

    def test_paths(self):
        p01, p02 = lesson.get("01-store"), lesson.get("02-installer")
        self.assertEqual((p01.slug, p01.go_module, p01.module, p01.kit_dir), ("p01-1", "normgen/p01-1",
                                                                              "p01store/01-store", "01-store"))
        self.assertEqual((p02.slug, p02.go_module, p02.module), ("p02", "normgen/p02", "p02installer/02-installer"))
        self.assertEqual(p01.norms("3").name, "01.3-store.norms.md")
        self.assertTrue(p01.openapi.is_file())
        self.assertEqual(p01.chapters(), ["1", "2", "3"])
        self.assertEqual(lesson.get("08-domain").chapters()[:3], ["0", "1", "2"])
        self.assertEqual(lesson.get("10-domain-console").module, "p10domainconsole/10-domain-console")
        self.assertTrue(lesson.get("04-controller").norms().is_file())


class Generators(unittest.TestCase):
    def test_p01_same_bytes(self):
        """Explicit --lesson 01-store and NORMGEN_LESSON=01-store produce the same bytes as the default course output."""
        for gen, rel in (("gen_core.py", "core/coreadapter/core.go"), ("gen_admin.py", "go/admin/import.go"),
                         ("gen_launch.py", "go/launch/launch.go")):
            with tempfile.TemporaryDirectory() as t:
                done = run([gen, "--lesson", "01-store", t])
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual((Path(t) / rel).read_bytes(), (HERE / "out/p01-1" / rel).read_bytes(), gen)

    def test_other_lesson_refused_by_name(self):
        for gen in DECLARED_P01:
            with tempfile.TemporaryDirectory() as t:
                done = run([gen, t], env={lesson.ENV: "02-installer"})
                self.assertNotEqual(done.returncode, 0, gen)
                self.assertIn("no declaration for lesson 02-installer", done.stderr, gen)

    def test_unknown_lesson_exit_2(self):
        done = run(["gen_flags.py", "--lesson", "11-nope"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("not in Platform/lessons.tsv", done.stderr)

    def test_build_kit_lesson_default_module(self):
        with tempfile.TemporaryDirectory() as t:
            done = run(["kit/build_kit.py", t, "--lesson", "01-store"])
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("01-store/internal", done.stdout)
            self.assertIn('"module": "p01store/01-store"', (Path(t) / "kit.manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
