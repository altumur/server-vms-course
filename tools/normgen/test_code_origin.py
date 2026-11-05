"""Provenance judge: independent Git snapshots, adversarial origins and final contents.

No implementation-line source is copied into the fixtures or read by this test.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import code_origin as C


class Origin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "source"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Provenance fixture")
        self.files = {
            "module/derived.go": b"package fixture\nconst N = 1\n",  # no generated header
            "module/manual.go": b"// Code generated: DO NOT EDIT.\npackage fixture\n",  # handwritten
            "module/change.go": b"package fixture\n",
            "module/stub.go": b"package fixture\n",
            "module/handstub.go": b"package fixture\n",
            "module/delete.go": b"package fixture\n",
            "module/derived_test.go": b"package fixture\n// packaged test\n",
            "module/vendor/hidden.go": b"package hidden\n",
        }
        manifest = []
        for p, data in self.files.items():
            manifest.append({"path": p, "sha256": hashlib.sha256(data).hexdigest(), "lines": 123456,
                             "origin": "handwritten" if p.endswith(("manual.go", "handstub.go")) else "generated",
                             "editable": p.endswith(("change.go", "stub.go", "handstub.go"))})
        self.manifest = {"files": manifest, "commit": "course metadata", "export": "export metadata"}
        for p, data in self.files.items():
            self.put(p, data)
        self.write_manifest()
        self.package = self.commit()
        self.put("module/change.go", b"// DO NOT EDIT, but edited\npackage fixture\nconst Own = 2\n\n")
        self.put("module/own.go", b"// Code generated: a misleading header\npackage fixture\n// final line")
        self.put("module/own_test.go", b"package fixture\n// own test\n\n")
        self.put("module/vendor/own.go", b"package hidden\n")
        self.put("module/drop/ignored.go", b"package hidden\n")
        self.put("outside/ignored.go", b"package hidden\n")
        self.put("module/README.md", b"outside suffix scope\n")
        (self.repo / "module/delete.go").unlink()
        self.implementation = self.commit()
        self.config = {
            "version": 1, "implementation": {"repo": "trial", "commit": self.implementation},
            "include_dirs": ["module"], "exclude_dir_names": ["vendor"], "exclude_paths": ["module/drop"],
            "suffixes": [".go"], "test_suffixes": ["_test.go"],
            "packages": [{"id": "kit", "repo": "trial", "commit": self.package, "manifest": "kit.manifest.json",
                          "source_root": ".", "target_root": "."}],
        }

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.check_output(["git", *args], cwd=self.repo, env=env, stderr=subprocess.PIPE)

    def put(self, p, data):
        target = self.repo / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def write_manifest(self):
        self.put("kit.manifest.json", json.dumps(self.manifest).encode())

    def commit(self):
        # Explicit fixture paths; never stage the shared course tree.
        names = sorted(set(p.decode() for p in self.git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0") if p))
        self.git("add", "--", *names)
        self.git("commit", "-qm", "synthetic snapshot")
        return self.git("rev-parse", "HEAD").decode().strip()

    def count(self, config=None):
        return C.count(config or self.config, {"trial": self.repo})

    def test_three_origins_and_tests_use_final_lines(self):
        report = self.count()
        lines = {k: {o: t["lines"] for o, t in v.items()} for k, v in report["totals"].items()}
        self.assertEqual(lines, {"code": {"generated": 3, "handwritten": 3, "model": 7},
                                 "tests": {"generated": 2, "handwritten": 0, "model": 3}})
        rows = {r["path"]: r for r in report["files"]}
        self.assertEqual(rows["module/stub.go"]["reason"], "unchanged_editable")
        self.assertEqual(rows["module/handstub.go"]["origin"], "handwritten")
        self.assertEqual(rows["module/change.go"]["reason"], "changed_editable")
        self.assertEqual(rows["module/own.go"]["origin"], "model")
        self.assertEqual(report["missing_package_files"][0]["path"], "module/delete.go")
        self.assertEqual(len(rows), 8)
        self.assertNotIn(str(self.repo), json.dumps(report))

    def test_working_tree_and_head_do_not_change_result(self):
        report = self.count()
        self.put("module/derived.go", b"this is dirty and must not be read")
        self.put("module/untracked.go", b"not in the pinned tree")
        self.assertEqual(report, self.count())
        self.commit()
        self.assertEqual(report, self.count())

    def test_package_hash_is_checked_even_if_implementation_was_edited(self):
        self.put("module/change.go", b"tampered package import\n")
        self.config["packages"][0]["commit"] = self.commit()
        with self.assertRaisesRegex(C.CountError, "package bytes do not match"):
            self.count()

    def test_changed_closed_file_is_error(self):
        self.put("module/manual.go", b"model replaced the protected runtime\n")
        self.config["implementation"]["commit"] = self.commit()
        with self.assertRaisesRegex(C.CountError, "closed package file changed"):
            self.count()

    def test_duplicate_manifest_path_and_package_ownership_are_errors(self):
        self.config["packages"].append(dict(self.config["packages"][0], id="other"))
        with self.assertRaisesRegex(C.CountError, "overlapping package ownership"):
            self.count()
        self.config["packages"].pop()
        self.manifest["files"].insert(0, self.manifest["files"][0])
        self.write_manifest()
        self.config["packages"][0]["commit"] = self.commit()
        with self.assertRaisesRegex(C.CountError, "duplicate or invalid manifest path"):
            self.count()

    def test_unknown_origin_and_nonboolean_editable_are_errors(self):
        for field, value in (("origin", "from-the-banner"), ("editable", "false")):
            with self.subTest(field=field):
                original = self.manifest["files"][0].copy()
                self.manifest["files"][0][field] = value
                self.write_manifest()
                self.config["packages"][0]["commit"] = self.commit()
                with self.assertRaisesRegex(C.CountError, "invalid origin/editable"):
                    self.count()
                self.manifest["files"][0] = original

    def test_scope_and_pins_cannot_silently_expand_or_shrink(self):
        for field, value in (("include_dirs", ["module", "module/drop"]), ("include_dirs", ["missing"]),
                             ("exclude_dir_names", ["tmp"]), ("include_dirs", ["../module"]),
                             ("include_dirs", ["module/"])):
            with self.subTest(field=field, value=value):
                config = copy.deepcopy(self.config)
                config[field] = value
                with self.assertRaises(C.CountError):
                    self.count(config)
        for pin in ("HEAD", self.package[:8]):
            config = copy.deepcopy(self.config)
            config["implementation"]["commit"] = pin
            with self.assertRaisesRegex(C.CountError, "full lowercase Git commit SHA"):
                self.count(config)

    def test_symlinks_are_not_followed(self):
        (self.repo / "module/link.go").symlink_to("manual.go")
        self.config["implementation"]["commit"] = self.commit()
        with self.assertRaisesRegex(C.CountError, "not a regular Git file"):
            self.count()

    def test_mapping_package_paths(self):
        # Imported kit has module/...; final implementation uses moved/module/....
        self.git("mv", "module", "moved")
        self.config["implementation"]["commit"] = self.commit()
        self.config["include_dirs"] = ["moved"]
        self.config["exclude_paths"] = ["moved/drop"]
        # A second pinned package snapshot may use a different file root from its manifest.
        self.git("checkout", self.package, "--", "module")
        self.git("mv", "module", "pkg")
        for entry in self.manifest["files"]:
            entry["path"] = entry["path"].removeprefix("module/")
        self.write_manifest()
        package = self.config["packages"][0]
        package.update(commit=self.commit(), source_root="pkg", target_root="moved")
        report = self.count()
        self.assertEqual(report["totals"]["code"]["generated"]["lines"], 3)

    def test_json_duplicate_keys_and_line_boundaries(self):
        with self.assertRaisesRegex(C.CountError, "duplicate JSON key"):
            C.read_json(b'{"version": 1, "version": 2}')
        self.assertEqual([C.physical_lines(b) for b in (b"", b"\n", b"a", b"a\n", b"a\n\n", b"a\r\nb")],
                         [0, 1, 1, 1, 2, 2])

    def test_cli_json_and_markdown(self):
        config_path = Path(self.tmp.name) / "input.json"
        config_path.write_text(json.dumps(self.config))
        command = [sys.executable, str(Path(C.__file__)), "--config", str(config_path),
                   "--repo", f"trial={self.repo}"]
        raw = subprocess.check_output(command)
        self.assertEqual(json.loads(raw), self.count())
        self.assertEqual(subprocess.check_output(command + ["--format", "markdown"]).decode(), C.markdown(self.count()))
        bad = subprocess.run(command + ["--repo", f"trial={self.repo}"], capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(bad.stdout, b"")


if __name__ == "__main__":
    unittest.main()
