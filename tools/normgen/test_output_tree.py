"""Prepared-output integrity controls; tiny fixtures are not generated-profile evidence."""
import copy
import hashlib
import json
import os
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import lesson

# Independent closed roster; a changed helper cannot silently omit a profile.
PROFILES = ("p01-1", "p02", "p03", "p04", "p05", "p06", "p08", "p09", "p10")


def snapshot(root):
    rows = []
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        rows.append((path.relative_to(root).as_posix(), mode,
                     path.read_bytes() if stat.S_ISREG(mode) else None))
    return rows


def records(root, scope=""):
    """Independent fixture metadata, not the producer's record_outputs/_scan."""
    start = root / scope
    paths = [start, *start.rglob("*")] if scope else list(root.rglob("*"))
    result = []
    for path in sorted(paths):
        if path.name == lesson.OUTPUT_MANIFEST:
            continue
        data = path.read_bytes() if path.is_file() else b""
        result.append({"path": path.relative_to(root).as_posix(),
                       "type": "file" if path.is_file() else "directory",
                       "mode": stat.S_IMODE(path.stat().st_mode), "bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest() if path.is_file() else None})
    return sorted(result, key=lambda row: row["path"])


class OutputIntegrityFixture(unittest.TestCase):
    """Hand-authored transport witnesses only, without profile/implementation claims."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="output-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.source, self.code, self.out = (self.home / n for n in ("source", "code", "output"))
        for path, data in ((self.source / "Platform/norm.tsv", b"a\t1\n"),
                           (self.code / "tools/normgen/runtime.go", b"package runtime\n")):
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
        self.out.mkdir()
        for slug in PROFILES:
            go = self.out / slug / "go"
            go.mkdir(parents=True)
            (go / "go.mod").write_text("module fixture/" + slug + "\n\ngo 1.22\n")
            (go / "fixture.txt").write_text("Transport fixture, not a generated implementation.\n")
        self.metadata = {"version": 1, "context": {"kind": "current"}, "profiles": list(PROFILES),
                         "parts": {s: ["vectors"] for s in PROFILES},
                         "inputs": {"source": records(self.source, "Platform"),
                                    "code": records(self.code, "tools/normgen")}, "files": records(self.out)}
        self.manifest = self.out / lesson.OUTPUT_MANIFEST
        self.write(self.metadata, creation=True)

    def write(self, value, *, creation=False):
        data = (json.dumps(value, sort_keys=True) + "\n").encode()
        if creation:
            # Held from our own serialization, before publishing fixture bytes.
            self.receipt = hashlib.sha256(data).hexdigest()
        self.manifest.write_bytes(data)
        self.manifest.chmod(0o600)

    def consume(self):
        return lesson.ready_outputs(output_root=self.out, source_root=self.source,
                                    code_root=self.code, profiles=PROFILES, expected_manifest_sha256=self.receipt)

    def refuses_unchanged(self):
        before = snapshot(self.home)
        with self.assertRaises((lesson.LessonError, OSError)):
            self.consume()
        self.assertEqual(snapshot(self.home), before, "consumption must not heal/regenerate")

    def test_closed_nine_and_absolute_mapping(self):
        self.assertEqual(tuple(lesson.PROFILES), PROFILES)
        before = snapshot(self.home)
        self.assertEqual(self.consume(), {s: self.out / s for s in PROFILES})
        self.assertTrue(all(p.is_absolute() for p in self.consume().values()))
        self.assertEqual(snapshot(self.home), before)

    def test_each_missing_profile_empty_unknown_and_duplicate_refuse(self):
        for omitted in PROFILES:
            changed = copy.deepcopy(self.metadata)
            changed["profiles"].remove(omitted)
            del changed["parts"][omitted]
            self.write(changed)
            with self.subTest(omitted=omitted):
                self.refuses_unchanged()
        for bad in ([], ["p07"], ["p01-1", "p01-1"], list(PROFILES) + ["p11"]):
            changed = copy.deepcopy(self.metadata)
            changed["profiles"] = bad
            self.write(changed)
            with self.subTest(profiles=bad):
                self.refuses_unchanged()

    def test_missing_empty_duplicate_and_typed_records_refuse(self):
        mutations = []
        for key in ("files", "inputs", "parts"):
            changed = copy.deepcopy(self.metadata)
            changed.pop(key)
            mutations.append(changed)
        for key in ("files", "source", "code"):
            changed = copy.deepcopy(self.metadata)
            container = changed if key == "files" else changed["inputs"]
            container[key] = []
            mutations.append(changed)
        for field, value in (("mode", True), ("bytes", True), ("sha256", "0" * 63),
                             ("path", "../escape"), ("type", "symlink")):
            changed = copy.deepcopy(self.metadata)
            next(r for r in changed["files"] if r["type"] == "file")[field] = value
            mutations.append(changed)
        changed = copy.deepcopy(self.metadata)
        changed["files"].append(copy.deepcopy(changed["files"][0]))
        mutations.append(changed)
        for index, changed in enumerate(mutations):
            with self.subTest(index=index):
                self.write(changed, creation=True)  # New malformed construction, not healed tampering.
                self.refuses_unchanged()

    def test_changed_missing_extra_and_mode_output_refuse_without_repair(self):
        path = self.out / "p06/go/fixture.txt"
        data = path.read_bytes()
        path.write_bytes(b"changed")
        self.refuses_unchanged()
        path.unlink()
        self.refuses_unchanged()
        path.write_bytes(data)
        path.chmod(0o600)
        self.refuses_unchanged()
        path.chmod(0o644)
        (self.out / "p06/go/.unlisted").write_text("extra")
        self.refuses_unchanged()

    def test_changed_source_code_runtime_and_new_input_refuse(self):
        for path in (self.source / "Platform/norm.tsv", self.code / "tools/normgen/runtime.go"):
            with self.subTest(path=path):
                data = path.read_bytes()
                path.write_bytes(data + b"\n")
                self.refuses_unchanged()
                path.write_bytes(data)
        (self.source / "Platform/.new-input").write_text("new source")
        self.refuses_unchanged()

    def test_bad_missing_duplicate_and_retyped_manifest_refuse(self):
        encoded = self.manifest.read_text()
        for bad in ("", "{}", encoded[:-2], encoded.replace('"version": 1', '"version": true'),
                    encoded.replace('"version": 1', '"version": 1, "version": 1'),
                    encoded.replace('"version": 1', '"version": NaN')):
            self.manifest.write_text(bad)
            with self.subTest(metadata=bad[:20]):
                self.refuses_unchanged()
        self.manifest.unlink()
        self.refuses_unchanged()

    def test_alias_and_fifo_refuse_without_opening_or_healing(self):
        path = self.out / "p06/go/fixture.txt"
        data = path.read_bytes()
        path.unlink()
        target = self.home / "external.txt"
        target.write_bytes(data)
        path.symlink_to(target)
        self.refuses_unchanged()
        path.unlink()
        os.mkfifo(path)
        self.refuses_unchanged()

    def test_partial_component_never_satisfies_full_nine(self):
        changed = copy.deepcopy(self.metadata)
        changed["context"] = {"kind": "component"}
        changed["profiles"] = ["p01-1"]
        changed["parts"] = {"p01-1": ["vectors"]}
        self.write(changed)
        self.refuses_unchanged()

    def test_coupled_payload_and_manifest_cannot_reseal_the_created_set(self):
        path = self.out / "p06/go/fixture.txt"
        data = path.read_bytes() + b"changed payload\n"
        path.write_bytes(data)
        changed = copy.deepcopy(self.metadata)
        row = next(r for r in changed["files"] if r["path"] == "p06/go/fixture.txt")
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.write(changed)
        self.refuses_unchanged()

    def test_omission_with_matching_roster_is_not_a_new_creation(self):
        path = self.out / "p06/go/fixture.txt"
        path.unlink()
        changed = copy.deepcopy(self.metadata)
        changed["files"] = [r for r in changed["files"] if r["path"] != "p06/go/fixture.txt"]
        self.write(changed)
        self.refuses_unchanged()

    def test_context_and_parts_changes_keep_the_original_receipt(self):
        for key, value in (("context", {"kind": "component"}),
                           ("parts", {slug: ["core"] for slug in PROFILES})):
            changed = copy.deepcopy(self.metadata)
            changed[key] = value
            self.write(changed)
            with self.subTest(key=key):
                self.refuses_unchanged()

    def test_explicit_receipt_priority_missing_wrong_and_malformed(self):
        args = dict(output_root=self.out, source_root=self.source, code_root=self.code, profiles=PROFILES)
        with mock.patch.dict(os.environ, {lesson.OUTPUT_RECEIPT_ENV: "0" * 64}):
            self.assertEqual(set(self.consume()), set(PROFILES))  # Explicit held receipt wins.
        with mock.patch.dict(os.environ, {lesson.OUTPUT_RECEIPT_ENV: self.receipt}):
            self.assertEqual(set(lesson.ready_outputs(**args)), set(PROFILES))
            for wrong in ("0" * 64, "", "A" * 64, "0" * 63, True, 1):
                with self.subTest(receipt=wrong), self.assertRaises(lesson.LessonError):
                    lesson.ready_outputs(**args, expected_manifest_sha256=wrong)
        before = snapshot(self.home)
        with mock.patch.dict(os.environ):
            os.environ.pop(lesson.OUTPUT_RECEIPT_ENV, None)
            with self.assertRaises(lesson.LessonError):
                lesson.ready_outputs(**args)
            with self.assertRaises(lesson.LessonError):
                lesson.output_manifest(self.out)
        self.assertEqual(snapshot(self.home), before)

    def test_interprocess_receipts_cannot_be_missing_ambiguous_or_from_another_creation(self):
        child = ("import sys;sys.path.insert(0,sys.argv[1]);import lesson;"
                 "lesson.ready_outputs(output_root=sys.argv[2],source_root=sys.argv[3],code_root=sys.argv[4],"
                 "profiles=lesson.PROFILES);print('complete-nine-transport-fixture')")
        args = [sys.executable, "-B", "-c", child, str(Path(lesson.__file__).parent), str(self.out),
                str(self.source), str(self.code)]
        for receipt, success in ((self.receipt, True), (None, False), ("0" * 64, False),
                                 (self.receipt + "\n", False), (self.receipt + "," + self.receipt, False)):
            env = dict(os.environ)
            env.pop(lesson.OUTPUT_RECEIPT_ENV, None)
            if receipt is not None:
                env[lesson.OUTPUT_RECEIPT_ENV] = receipt
            before = snapshot(self.home)
            done = subprocess.run(args, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode == 0, success, done.stdout + done.stderr)
            self.assertEqual(snapshot(self.home), before)
        # A new explicitly constructed set gets its own held creation identity.
        previous, original = self.receipt, snapshot(self.out)
        changed = copy.deepcopy(self.metadata)
        changed["context"] = {"kind": "component"}
        new_root = self.home / "second-creation"
        shutil.copytree(self.out, new_root)
        own_bytes = (json.dumps(changed, sort_keys=True) + "\n").encode()
        new_receipt = hashlib.sha256(own_bytes).hexdigest()
        (new_root / lesson.OUTPUT_MANIFEST).write_bytes(own_bytes)
        self.assertNotEqual(new_receipt, previous)
        args = dict(output_root=new_root, source_root=self.source, code_root=self.code, profiles=PROFILES)
        self.assertEqual(set(lesson.ready_outputs(**args, expected_manifest_sha256=new_receipt)), set(PROFILES))
        with self.assertRaises(lesson.LessonError):
            lesson.ready_outputs(**args, expected_manifest_sha256=previous)
        self.assertEqual(snapshot(self.out), original)

    def test_export_creator_stdout_receipt_is_strict_and_forwarded_without_rereading(self):
        from kit import build_kit
        receipt = self.receipt
        def git_fixture(*args, **kwargs):
            if args[0] == "status":
                return b""
            return ("1" * 40 + "\n").encode()
        cases = [(receipt, 0, True), (receipt + "\n", 0, True), (receipt, 1, False),
                 ("", 0, False), (receipt[:-1], 0, False), (receipt + "\n\n", 0, False),
                 (receipt + "\n" + receipt + "\n", 0, False), ("log " + receipt, 0, False)]
        for index, (stdout, exit_code, success) in enumerate(cases):
            dst = self.home / ("export-consumer-" + str(index))
            calls = []
            def run_fixture(command, **kwargs):
                calls.append((command, kwargs))
                if len(calls) == 1:
                    return subprocess.CompletedProcess(command, exit_code, stdout, "")
                self.assertEqual(kwargs["env"][lesson.OUTPUT_RECEIPT_ENV], receipt)
                dst.mkdir()
                (dst / "kit.manifest.json").write_text(json.dumps({"parts": [], "files": []}))
                return subprocess.CompletedProcess(command, 0, "", "")
            before = snapshot(self.out)
            with self.subTest(stdout=stdout[-8:], exit=exit_code), \
                    mock.patch.object(build_kit, "git", side_effect=git_fixture), \
                    mock.patch.object(build_kit, "unpack"), \
                    mock.patch.object(build_kit.subprocess, "run", side_effect=run_fixture):
                if success:
                    build_kit.build_from_export(dst, "fixture/mod", (), {}, "2" * 40,
                                               specs=self.home / "specs", root=self.code)
                    self.assertEqual(len(calls), 2)
                else:
                    with self.assertRaises(build_kit.KitError):
                        build_kit.build_from_export(dst, "fixture/mod", (), {}, "2" * 40,
                                                   specs=self.home / "specs", root=self.code)
                    self.assertEqual(len(calls), 1)
                    self.assertFalse(dst.exists())
            self.assertEqual(snapshot(self.out), before)

    def test_explicit_empty_prepare_profiles_refuse_before_input_access(self):
        from kit import build_kit
        with mock.patch.object(lesson, "output_inputs", side_effect=AssertionError("input access for empty profiles")) as read:
            try:
                build_kit.prepare(profiles=(), output_root=self.home / "new-output")
            except Exception as exc:
                self.assertIsInstance(exc, (lesson.LessonError, build_kit.KitError), str(exc))
            else:
                self.fail("explicit empty profiles accepted")
            read.assert_not_called()
        self.assertFalse((self.home / "new-output").exists())


class ActualPreparedProfiles(unittest.TestCase):
    """A full run cannot substitute a tiny transport fixture or component prepare."""
    def test_actual_nine_profile_set(self):
        ready = lesson.ready_outputs(profiles=PROFILES)
        self.assertEqual(lesson.output_manifest()["context"]["kind"], "current")
        self.assertEqual(tuple(ready), PROFILES)
        for slug, path in ready.items():
            self.assertTrue((path / "go/go.mod").is_file(), slug)
            self.assertTrue((path / "go/vectortests").is_dir(), slug)
        self.assertFalse((Path(__file__).resolve().parent / "out").exists(),
                         "old out must be absent in the final transition run")


if __name__ == "__main__":
    unittest.main()
