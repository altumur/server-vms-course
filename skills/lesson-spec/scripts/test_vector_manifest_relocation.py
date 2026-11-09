"""Focused checks for C08 manifest-SHA rows after a whole-file J relocation."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from check_spec import Check


class VectorManifestRelocationControls(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def carrier(self, name="README.cases.md", *, module="Platform", russian=False):
        folder = self.root / module / "08-domain"
        if russian:
            folder /= "ru"
        folder /= "vectors/assemble"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / name

    def row(self, carrier, manifest="m.yaml", *, valid=True):
        target = carrier.parent / manifest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic: manifest\n")
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if valid else "0" * 64
        return f"| [manifest]({manifest}) | `{digest}` |\n"

    def errors(self, scope="platform"):
        check = Check(self.root, scope=scope)
        check.vector_hashes()
        return check.errors

    def test_original_readme_sha_guard_preserved(self):
        carrier = self.carrier("README.md")
        carrier.write_text(self.row(carrier))
        self.assertEqual(self.errors(), [])
        carrier.write_text(self.row(carrier, valid=False))
        self.assertEqual(len(self.errors()), 1)
        self.assertIn("line 1: sha256 is not of m.yaml", self.errors()[0])

    def test_relocated_readme_cases_positive_and_incorrect_hash(self):
        carrier = self.carrier()
        carrier.write_text(self.row(carrier))
        self.assertEqual(self.errors(), [])
        carrier.write_text(self.row(carrier, valid=False))
        errors = self.errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("README.cases.md", errors[0])
        self.assertIn("line 1: sha256 is not of m.yaml", errors[0])

    def test_every_relocated_table_row_is_checked(self):
        carrier = self.carrier()
        carrier.write_text("# relocation\n" + self.row(carrier, "a.yaml") +
                           self.row(carrier, "b.yaml", valid=False) +
                           self.row(carrier, "c.yaml", valid=False))
        errors = self.errors()
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("line 3: sha256 is not of b.yaml" in error for error in errors))
        self.assertTrue(any("line 4: sha256 is not of c.yaml" in error for error in errors))

    def test_missing_relocated_target_refuses(self):
        carrier = self.carrier()
        carrier.write_text(self.row(carrier, "nested/m.yaml"))
        (carrier.parent / "nested/m.yaml").unlink()
        errors = self.errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("sha256 is not of nested/m.yaml", errors[0])

    def test_english_and_russian_relocation_paths_checked(self):
        for russian in (False, True):
            carrier = self.carrier(russian=russian)
            carrier.write_text(self.row(carrier, valid=False))
        errors = self.errors()
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("/ru/vectors/" in error for error in errors))
        self.assertTrue(any("08-domain/vectors/" in error for error in errors))

    def test_platform_vms_scope_selection_unchanged(self):
        for module in ("Platform", "VMS"):
            carrier = self.carrier(module=module)
            carrier.write_text(self.row(carrier, valid=False))
        platform, vms, both = self.errors("platform"), self.errors("vms"), self.errors(None)
        self.assertEqual((len(platform), len(vms), len(both)), (1, 1, 2))
        self.assertIn("Platform/", platform[0])
        self.assertIn("VMS/", vms[0])

    def test_unrelated_markdown_filename_not_admitted(self):
        for name in ("other.md", "README.cases.extra.md", "README.cases.md.bak"):
            carrier = self.carrier(name)
            carrier.write_text(self.row(carrier, valid=False))
        self.assertEqual(self.errors(), [])


if __name__ == "__main__":
    unittest.main()
