"""Bounded V11 checker readers and exact public byte-carrier controls; no SUT."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_cyrillic
from check_spec import Check, IDMAP, IDMAP_FIELDS, VMS_CATALOG_FIELDS, VMS_IDMAP
from vms_platform_pin import _git

SOURCE_COMMIT = "c8eafc05626112db4c2003b416f762055deaef65"
# Carriers the owner of the VMS Source re-approved with the learn norms, 2026-11-08.
LEARN_COMMIT = "48e001457141d1dee22b3757bc844e56c3dd9ee0"
LEARN_CARRIERS = {"VMS/11-backend/README.md", "VMS/11-backend/spec/11.7-backend.norms.md"}
SOURCE_METADATA = "decisions/inbox/2026-11-08-запрос-vms-v11-english-cb728a4.md"


class V11Readers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v11-checker-readers-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_history_map_is_required_without_active_map_fallback(self):
        self.assertEqual(VMS_IDMAP, Path("decisions/history/vms/id-map.tsv"))
        self.put("VMS/common/lessons.tsv", "# lesson\tdir\ttitle\tsubsystem\tstatus\n")
        self.put("VMS/common/data/catalog.tsv", "\t".join(VMS_CATALOG_FIELDS) + "\n")
        history = self.put(str(VMS_IDMAP), "\t".join(IDMAP_FIELDS) + "\n")
        check = Check(self.root)
        check.vms_module()
        self.assertEqual(check.errors, [])
        history.unlink()
        self.put("VMS/common/id-map.tsv", "\t".join(IDMAP_FIELDS) + "\n")
        check = Check(self.root)
        check.vms_module()
        self.assertTrue(any(str(VMS_IDMAP) in e and "missing" in e for e in check.errors))

    def test_map_audit_reads_history_not_active_bytes(self):
        self.put(str(VMS_IDMAP), "\t".join(IDMAP_FIELDS) + "\nold\tV/11.1-01\t11.1\tfixture\t-\n")
        self.put("VMS/common/id-map.tsv", "wrong active map\n")
        check = Check(self.root)
        rows = check.id_map_rows(VMS_IDMAP)
        self.assertEqual(rows[0][1]["new"], "V/11.1-01")
        self.assertEqual(check.errors, [])

    def added_after_move(self, value, table=VMS_IDMAP):
        rows = [(2, {"old": "М12A-01", "new": "V/11.1-01"}), (3, {"old": "V/11.1-05", "new": "V/11.1-07"})]
        check = Check(self.root)
        with patch.object(check, "id_map_rows", return_value=rows):
            check.id_map_chapter(Path("norms.md"), "V/11.1", {"V/11.1-01", "V/11.1-07", value}, table)
        return [e for e in check.errors if value in e and "column new" in e]

    def test_id_added_after_the_last_mapped_number_needs_no_map_row(self):
        self.assertEqual(self.added_after_move("V/11.1-08"), [])
        self.assertEqual(self.added_after_move("V/11.1-10"), [])

    def test_renumbering_and_former_ids_still_need_the_map(self):
        self.assertTrue(self.added_after_move("V/11.1-03"))  # not after the last mapped number
        self.assertTrue(self.added_after_move("V/11.1-05"))  # in the column old

    def test_platform_map_keeps_the_strict_rule(self):
        self.assertTrue(self.added_after_move("V/11.1-08", IDMAP))

    def test_v11_journals_use_moved_history_without_old_path_fallback(self):
        for chapter in ("4", "8"):
            with self.subTest(chapter=chapter):
                acceptance = self.root / "VMS/11-backend/acceptance" / chapter
                self.put(f"VMS/11-backend/ru/acceptance/{chapter}/README.md", "# Fixture\n")
                acceptance.mkdir(parents=True, exist_ok=True)
                name = f"decisions/journal/vms/11-backend/corrections-{chapter}.tsv"
                journal = self.put(name, "date\tsample\tfix\tlanguages\n")
                check = Check(self.root)
                with patch.object(check, "tsv", wraps=check.tsv) as tsv:
                    check.acceptance(acceptance, "V/11", chapter + "/")
                self.assertIn(journal, [call.args[0] for call in tsv.call_args_list])
                self.assertFalse(any("corrections" in e for e in check.errors), check.errors)
                journal.unlink()
                self.put(f"VMS/11-backend/journal/corrections-{chapter}.tsv", "date\tsample\tfix\tlanguages\n")
                check = Check(self.root)
                check.acceptance(acceptance, "V/11", chapter + "/")
                self.assertTrue(any(name in e for e in check.errors), check.errors)


class V11ExactCarriers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import re
        root = Path(__file__).resolve().parents[3]
        metadata = _git(root, "show", SOURCE_COMMIT + ":" + SOURCE_METADATA).decode()
        cls.named = {name for name in re.findall(
            r"^\| `([^`]+)` \| (?:literal_data|pinned_upstream_bytes) \| [0-9]+ \|$", metadata, re.M)}
        cls.data = {name: _git(root, "show", (LEARN_COMMIT if name in LEARN_CARRIERS else SOURCE_COMMIT) + ":" + name)
                    for name in sorted(cls.named)}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v11-checker-carriers-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.debt = self.root / "debt.tsv"
        self.debt.write_text(check_cyrillic.HEADER + "\n")
        for name, data in self.data.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def judge(self, **kwargs):
        return check_cyrillic.check(self.root, self.debt, **kwargs)

    def test_roster_is_exact_source_selected_31_with_two_explicit_pins(self):
        self.assertEqual(len(self.named), 31)
        self.assertEqual(set(check_cyrillic.EXACT_SOURCE_FILES), self.named)
        self.assertEqual(check_cyrillic.EXACT_SOURCE_FILES["VMS/11-backend/consolem.openapi.json"],
                         "200d203d4197776892e66a32126998bc8cf0b79a9986ef7ac144c6af230f7124")
        self.assertEqual(check_cyrillic.EXACT_SOURCE_FILES["VMS/11-backend/backend.shell.html"],
                         "90e9cd59cb70207a785e23da943fb0785c9f80d382afecfae4d94a0bce9a05ff")
        errors, stats = self.judge()
        self.assertEqual(errors, [])
        self.assertEqual(stats["cyrillic_exact_source_files"], 31)

    def test_every_named_carrier_rejects_any_changed_bytes(self):
        for name, data in self.data.items():
            for changed in (data + b"\n", b"English replacement", data + "Ж".encode()):
                with self.subTest(path=name, mutation=changed[-24:]):
                    path = self.root / name
                    path.write_bytes(changed)
                    self.assertIn("SHA256 mismatch", check_cyrillic.exact_source_file_error(self.root, name))
            (self.root / name).write_bytes(data)
        self.assertEqual(self.judge()[0], [])

    def test_missing_carrier_is_error_in_git_free_projected_source(self):
        name = "VMS/11-backend/backend.shell.html"
        (self.root / name).unlink()
        self.assertTrue(any(name in e and "cannot read exact source carrier" in e for e in self.judge()[0]))

    def test_symlink_and_fifo_are_rejected_before_reading(self):
        import os
        name = "VMS/11-backend/backend.shell.html"
        path = self.root / name
        path.unlink()
        outside = self.root / "outside.html"
        outside.write_bytes(self.data[name])
        path.symlink_to(outside)
        self.assertIn("regular file without symlinks", check_cyrillic.exact_source_file_error(self.root, name))
        path.unlink()
        os.mkfifo(path)
        self.assertIn("regular file without symlinks", check_cyrillic.exact_source_file_error(self.root, name))

    def test_no_v11_tree_exclusion_or_hash_fallback_or_locale_budget(self):
        extra = self.root / "VMS/11-backend/new-house/unlisted.txt"
        extra.parent.mkdir()
        extra.write_text("Ж")
        self.assertTrue(any(str(extra.relative_to(self.root)) in e and "new/increased" in e for e in self.judge()[0]))
        extra.unlink()
        # Identical named-carrier bytes at another path gain no exception.
        sibling = self.root / "VMS/11-backend/backend.shell.html.extra"
        sibling.write_bytes(self.data["VMS/11-backend/backend.shell.html"])
        self.assertTrue(any(sibling.name in e and "new/increased" in e for e in self.judge()[0]))
        sibling.unlink()
        old = self.root / "VMS/common/id-map.tsv"
        old.parent.mkdir()
        old.write_text("Ж")
        self.assertTrue(any("VMS/common/id-map.tsv" in e and "new/increased" in e for e in self.judge()[0]))
        old.unlink()
        self.assertEqual(self.judge()[0], [])
        for record in ("debt\tVMS/11-backend/backend.shell.html\t100000", "ready\tVMS/11-backend\t-"):
            self.debt.write_text(check_cyrillic.HEADER + "\n" + record + "\n")
            before = self.debt.read_bytes()
            self.assertTrue(self.judge()[0])
            self.assertEqual(self.debt.read_bytes(), before)

    def test_explicit_full_english_check_uses_exact_carrier_identity(self):
        import en_mirror
        self.assertEqual(en_mirror.full_english_errors(self.root, ("VMS/11-backend/",)), [])
        name = "VMS/11-backend/README.md"
        (self.root / name).write_bytes(self.data[name] + b"\n")
        self.assertTrue(any("SHA256 mismatch" in error for _, error in
                            en_mirror.full_english_errors(self.root, ("VMS/11-backend/",))))


if __name__ == "__main__":
    unittest.main()
