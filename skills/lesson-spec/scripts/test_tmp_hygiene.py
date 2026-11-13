"""Temporary-directory hygiene of the skill's own tests (OBSH.55).

Runs the modules that used to leave `check-spec-pin-control-*`, `vms-evidence-path-control-*`,
`check-spec-vms-*` and bare `tmp*` directories behind, in a child interpreter whose TMPDIR is a
fresh empty directory, and requires that directory to be empty afterwards. No network.
v7.test_spec (its check_spec children get their own TMPDIR) is left out: its module tree takes minutes.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
MODULES = (
    "test_vms_platform_pin",                          # fixture Git repositories and evidence-path controls
    "test_check_spec.CyrillicIntegrationTests",       # check_spec CLI child whose failing VMS phase keeps evidence
    "test_check_tables",
    "test_check_machines",
    "test_export_lists",
    "test_target_registry",
    "test_form_refs",                                 # synthetic lessons of the form references (OBSH.56)
    "test_code_rules_modules",                        # synthetic code rules and shared modules (OBSH.69)
)


class TmpHygiene(unittest.TestCase):
    def test_listed_modules_leave_their_tmpdir_empty(self):
        with tempfile.TemporaryDirectory(prefix="tmp-hygiene-") as scratch:
            env = {**os.environ, "TMPDIR": scratch}
            result = subprocess.run([sys.executable, "-B", "-m", "unittest", *MODULES], cwd=HERE, env=env,
                                    capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sorted(os.listdir(scratch)), [])


if __name__ == "__main__":
    unittest.main()
