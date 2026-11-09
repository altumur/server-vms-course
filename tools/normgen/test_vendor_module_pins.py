"""Pinned module inputs and explicit vendor identities are immutable consumers."""
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import gen_manifest
import gen_policy_machines
import build_kit


class VendorModulePins(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="vendor-pins-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.versions = self.root / "Platform/common/versions"
        self.versions.mkdir(parents=True)
        self.output = self.root / "prepared"
        (self.output / "go/vendor").mkdir(parents=True)
        self.mod = b"module versions\n\ngo 1.22.0\n\nrequire (\n example.org/a v1.0.0\n example.org/b v2.0.0\n)\n"
        self.sum = b"example.org/a v1.0.0 h1:synthetic\n"
        (self.versions / "go.mod").write_bytes(self.mod)
        (self.versions / "go.sum").write_bytes(self.sum)
        self.ready(self.mod, self.sum)

    def ready(self, mod, sums, headers=None):
        (self.output / "go/go.mod").write_bytes(mod.replace(b"module versions", b"module normgen/p02"))
        (self.output / "go/go.sum").write_bytes(sums)
        (self.output / "go/vendor/modules.txt").write_text(headers or
            "# example.org/a v1.0.0\n## explicit; go 1.22\nexample.org/a\n"
            "# example.org/b v2.0.0\n## explicit\n")

    def consume(self):
        with patch.object(build_kit, "ROOT", self.root), \
             patch.object(build_kit, "L", SimpleNamespace(out=self.output)):
            return dict(build_kit.prepared_vendor("consumer/renamed"))

    def test_current_pins_rename_only_module_and_keep_explicit_empty_dependency(self):
        got = self.consume()
        self.assertEqual(got["go.mod"], self.mod.replace(b"module versions", b"module consumer/renamed"))
        self.assertEqual(got["go.sum"], self.sum)
        self.assertIn(b"# example.org/b v2.0.0\n## explicit", got["vendor/modules.txt"])

    def test_stale_mod_and_sum_refuse(self):
        for mod, sums in ((self.mod.replace(b"v2.0.0", b"v2.0.1"), self.sum), (self.mod, self.sum + b"changed\n")):
            with self.subTest(mod=mod, sums=sums):
                self.ready(mod, sums)
                with self.assertRaisesRegex(build_kit.KitError, "pinned module"):
                    self.consume()

    def test_missing_extra_wrong_version_and_duplicate_explicit_rosters_refuse(self):
        rows = (
            "# example.org/a v1.0.0\n## explicit\n",
            "# example.org/a v1.0.0\n## explicit\n# example.org/b v2.0.1\n## explicit\n",
            "# example.org/a v1.0.0\n## explicit\n# example.org/b v2.0.0\n## explicit\n# example.org/c v3.0.0\n## explicit\n",
            "# example.org/a v1.0.0\n## explicit\n# example.org/b v2.0.0\n## explicit\n# example.org/b v2.0.0\n## explicit\n",
        )
        for text in rows:
            with self.subTest(text=text):
                self.ready(self.mod, self.sum, text)
                with self.assertRaisesRegex(build_kit.KitError, "explicit"):
                    self.consume()

    def test_missing_vendor_and_multiple_module_lines_remain_refusals(self):
        (self.output / "go/vendor/modules.txt").unlink()
        with self.assertRaisesRegex(build_kit.KitError, "empty/incomplete"):
            self.consume()
        self.ready(self.mod + b"module twice\n", self.sum)
        with self.assertRaisesRegex(build_kit.KitError, "one module"):
            self.consume()

    def producer(self, producer, mutation=None):
        seen = []
        def command(argv, *, cwd, **kwargs):
            seen.append((argv, kwargs["env"]))
            cwd = Path(cwd)
            (cwd / "vendor").mkdir()
            (cwd / "vendor/modules.txt").write_text("# example.org/a v1.0.0\n## explicit\n")
            if mutation:
                target = cwd / mutation
                target.write_bytes(target.read_bytes() + b"changed\n")
            return SimpleNamespace(returncode=0, stderr="")
        if producer is gen_manifest:
            with patch.object(producer, "VERSIONS", self.versions), patch.object(producer, "render", return_value={}), \
                 patch("subprocess.run", command):
                result = producer.vendor("consumer/module")
        else:
            pinned = {"go.mod": self.mod.replace(b"module versions", b"module consumer/module"), "go.sum": self.sum}
            with patch.object(producer, "module_files", return_value=pinned), patch.object(producer, "build", return_value={}), \
                 patch.object(producer.subprocess, "run", command):
                result = producer.vendor("consumer/module")
        return result, seen

    def test_both_producers_use_offline_readonly_and_keep_pinned_inputs(self):
        for producer in (gen_manifest, gen_policy_machines):
            with self.subTest(producer=producer.__name__):
                files, calls = self.producer(producer)
                self.assertEqual(calls[0][0], ["go", "mod", "vendor"])
                self.assertEqual(calls[0][1]["GOFLAGS"], "-mod=readonly")
                self.assertEqual(calls[0][1]["GOPROXY"], "off")
                self.assertEqual(calls[0][1]["GOWORK"], "off")
                self.assertEqual(dict(files)["go.sum"], self.sum)

    def test_both_producers_refuse_any_go_mod_or_go_sum_mutation(self):
        for producer in (gen_manifest, gen_policy_machines):
            for mutation in ("go.mod", "go.sum"):
                with self.subTest(producer=producer.__name__, mutation=mutation):
                    with self.assertRaisesRegex(producer.GenError, "pinned module"):
                        self.producer(producer, mutation)

    def test_current_public_requirements_match_explicit_count_without_hardcode(self):
        source = HERE.parent.parent / "Platform/common/versions"
        actual_mod = (source / "go.mod").read_bytes()
        actual_sum = (source / "go.sum").read_bytes()
        requirements = re.findall(rb"(?m)^[ \t]*([A-Za-z0-9][^ \t\r\n]*)[ \t]+(v[0-9][^ \t\r\n]*)(?:[ \t]+//[^\n]*)?$", actual_mod)
        self.assertGreater(len(requirements), 0)
        (self.versions / "go.mod").write_bytes(actual_mod)
        (self.versions / "go.sum").write_bytes(actual_sum)
        text = b"".join(b"# " + name + b" " + version + b"\n## explicit\n" for name, version in requirements).decode()
        self.ready(actual_mod, actual_sum, text)
        got = self.consume()
        self.assertEqual(got["vendor/modules.txt"].count(b"## explicit"), len(requirements))
        self.assertEqual(got["go.sum"], actual_sum)


if __name__ == "__main__":
    unittest.main()
