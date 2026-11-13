"""Private Git-fixture controls for the Owner-only Platform pin binding.

No course VMS lessons, implementation, schema corpus or candidate is executed.
Fixture directories are retained for the task's evidence/release disposition.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from vms_platform_pin import PinError, read_pin, materialize_vms_view, verify_owner_pin, _selected_archive_member
from pathlib import PurePosixPath


class PlatformPinBinding(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="check-spec-pin-control-"))
        self.root = self.work / "course"
        self.root.mkdir()
        # This is the deliberately new fixture repository, not the shared course.
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.git("config", "user.email", "pin-control@example.invalid")
        self.git("config", "user.name", "Pin control")
        self.write("Platform/owner.txt", "promised one\n")
        self.write("VMS/norm.md", "current VMS\n")
        self.write("decisions/journal/platform/owner.tsv", "promised history\n")
        self.git("add", "Platform/owner.txt", "VMS/norm.md", "decisions/journal/platform/owner.tsv")
        self.git("commit", "-qm", "fixture promised platform")
        self.pin = self.git("rev-parse", "HEAD").decode().strip()
        self.write("VMS/PLATFORM_PIN", self.pin + "\n")
        self.git("add", "VMS/PLATFORM_PIN")
        self.git("commit", "-qm", "fixture Owner pin")

    def git(self, *args):
        top = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "--show-toplevel"])
        self.assertEqual(Path(top.decode().strip()), self.root)
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.STDOUT)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def view(self, name="view", **kwargs):
        owner = read_pin(self.root)
        out = self.work / name
        manifest = materialize_vms_view(self.root, owner, out, **kwargs)
        return out, manifest

    def test_owner_pin_selects_platform_and_current_vms(self):
        self.write("VMS/norm.md", "new current VMS\n")
        out, manifest = self.view()
        self.assertEqual((out / "Platform/owner.txt").read_text(), "promised one\n")
        self.assertEqual((out / "VMS/norm.md").read_text(), "new current VMS\n")
        self.assertEqual(manifest["platform_commit"], self.pin)
        self.assertFalse(manifest["candidate"])
        self.assertEqual((self.root / "VMS/PLATFORM_PIN").read_text(), self.pin + "\n")

    def test_only_live_platform_change_preserves_pinned_vms_input(self):
        first, a = self.view("before")
        self.write("Platform/owner.txt", "incompatible live main\n")
        self.git("add", "Platform/owner.txt")
        self.git("commit", "-qm", "fixture live platform change")
        second, b = self.view("after")
        for path in ("Platform/owner.txt", "VMS/norm.md", "decisions/journal/platform/owner.tsv"):
            self.assertEqual((first / path).read_bytes(), (second / path).read_bytes())
        self.assertNotEqual(a.pop("source_commit"), b.pop("source_commit"))
        self.assertEqual(a, b)

    def test_candidate_is_separate_and_never_changes_owner_pin(self):
        original = (self.root / "VMS/PLATFORM_PIN").read_bytes()
        self.write("Platform/owner.txt", "candidate two\n")
        self.git("add", "Platform/owner.txt")
        self.git("commit", "-qm", "fixture proposed repin")
        candidate = self.git("rev-parse", "HEAD").decode().strip()
        out, manifest = self.view(candidate=candidate)
        self.assertTrue(manifest["candidate"])
        self.assertEqual(manifest["owner_platform_commit"], self.pin)
        self.assertEqual((out / "Platform/owner.txt").read_text(), "candidate two\n")
        self.assertEqual((self.root / "VMS/PLATFORM_PIN").read_bytes(), original)

    def test_missing_pin_is_an_error_without_head_fallback(self):
        (self.root / "VMS/PLATFORM_PIN").unlink()
        with self.assertRaises(PinError):
            read_pin(self.root)

    def test_malformed_or_unknown_pin_is_an_error(self):
        for text in ("", "HEAD\n", self.pin[:12] + "\n", self.pin + "\n\n",
                     " " + self.pin, self.pin + "\r\n", "0" * 40 + "\n"):
            with self.subTest(text=text):
                self.write("VMS/PLATFORM_PIN", text)
                with self.assertRaises(PinError):
                    read_pin(self.root)

    def test_symlink_pin_does_not_read_external_file(self):
        path = self.root / "VMS/PLATFORM_PIN"
        path.unlink()
        external = self.work / "external"
        external.write_text(self.pin + "\n")
        path.symlink_to(external)
        with self.assertRaises(PinError):
            read_pin(self.root)

    def test_changed_pin_and_existing_or_source_destination_refuse(self):
        owner = read_pin(self.root)
        existing = self.work / "existing"
        existing.mkdir()
        for dest in (existing, self.root / "new-view"):
            with self.assertRaises(PinError):
                materialize_vms_view(self.root, owner, dest)
        self.assertFalse((self.root / "new-view").exists())
        self.write("VMS/PLATFORM_PIN", "0" * 40 + "\n")
        with self.assertRaises(PinError):
            verify_owner_pin(self.root, owner)

    def test_noncommit_object_is_rejected(self):
        blob = self.git("rev-parse", "HEAD:Platform/owner.txt").decode().strip()
        self.write("VMS/PLATFORM_PIN", blob + "\n")
        with self.assertRaisesRegex(PinError, "does not name a commit"):
            read_pin(self.root)

    def test_archive_ancestors_only_as_directories(self):
        homes = ("Platform", "decisions/journal/platform")
        for name in ("decisions", "decisions/journal"):
            self.assertTrue(_selected_archive_member(PurePosixPath(name), homes, directory=True))
            self.assertFalse(_selected_archive_member(PurePosixPath(name), homes))
        for name in ("decisions/other", "../Platform", "/Platform"):
            self.assertFalse(_selected_archive_member(PurePosixPath(name), homes, directory=True))

    def checker_args(self, **kwargs):
        import check_spec
        args = check_spec.arguments().parse_args(["--root", str(self.root), "--scope", "vms"])
        debt = self.work / "debt.tsv"
        debt.write_text("kind\tpath\tletters\n")
        args.cyrillic_debt = debt
        args.exceptions = self.work / "exceptions.tsv"
        args.exceptions.write_text("")
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    def test_real_vms_phase_pinned_dependency_failure_and_live_invariance(self):
        """Run the actual phase; an invalid pinned catalog is a genuine dependency error."""
        import check_spec
        # A syntactically bad Platform catalog is loaded by the actual VMS Check.
        self.write("Platform/common/data/catalog.tsv", "wrong\theader\n")
        self.write("VMS/common/lessons.tsv", "# lesson\tdir\ttitle\tsubsystem\tstatus\n")
        self.write("decisions/history/vms/id-map.tsv", "old\tnew\tchapter\tsubject\tnote\n")
        self.write("VMS/common/data/catalog.tsv", "key\tkind\towner\tops\treaders\twhen\tversion\tnorm\tplace\n")
        self.git("add", "Platform/common/data/catalog.tsv", "VMS/common/lessons.tsv", "decisions/history/vms/id-map.tsv", "VMS/common/data/catalog.tsv")
        self.git("commit", "-qm", "fixture broken promised dependency")
        bad_pin = self.git("rev-parse", "HEAD").decode().strip()
        self.write("VMS/PLATFORM_PIN", bad_pin + "\n")
        args = self.checker_args(vms_evidence=self.work / "report-before")
        with redirect_stdout(StringIO()):
            before = check_spec._vms_reports(args, [])
        self.assertEqual(before["canonical_status"], "FAIL")
        self.assertTrue(any("Platform/common/data/catalog.tsv" in e for e in before["phases"][0]["errors"]))
        self.write("Platform/common/data/catalog.tsv", "new live dependency\n")
        self.git("add", "Platform/common/data/catalog.tsv")
        self.git("commit", "-qm", "fixture change only live dependency")
        args.vms_evidence = self.work / "report-after"
        with redirect_stdout(StringIO()):
            after = check_spec._vms_reports(args, [])
        self.assertEqual(before["canonical_status"], after["canonical_status"])
        self.assertEqual(before["phases"][0]["errors"], after["phases"][0]["errors"])
        self.assertEqual(before["phases"][0]["counts"], after["phases"][0]["counts"])
        self.assertEqual(before["phases"][0]["inputs"]["view_files"], after["phases"][0]["inputs"]["view_files"])

    def test_temporary_evidence_kept_only_on_failure(self):
        """OBSH.54: without --vms-evidence a failing run keeps and names its temporary directory."""
        import check_spec
        import shutil as _shutil
        self.write("Platform/common/data/catalog.tsv", "wrong\theader\n")
        self.write("VMS/common/lessons.tsv", "# lesson\tdir\ttitle\tsubsystem\tstatus\n")
        self.write("decisions/history/vms/id-map.tsv", "old\tnew\tchapter\tsubject\tnote\n")
        self.write("VMS/common/data/catalog.tsv", "key\tkind\towner\tops\treaders\twhen\tversion\tnorm\tplace\n")
        self.git("add", "Platform/common/data/catalog.tsv", "VMS/common/lessons.tsv", "decisions/history/vms/id-map.tsv", "VMS/common/data/catalog.tsv")
        self.git("commit", "-qm", "fixture failing phase")
        self.write("VMS/PLATFORM_PIN", self.git("rev-parse", "HEAD").decode().strip() + "\n")
        args = self.checker_args(vms_evidence=None)
        out = StringIO()
        with redirect_stdout(out):
            report = check_spec._vms_reports(args, [])
        self.assertEqual(report["canonical_status"], "FAIL")
        line = next(l for l in out.getvalue().splitlines() if l.startswith("VMS_REPORT "))
        path = Path(line.split(" ", 1)[1])
        self.assertTrue(path.is_file())
        _shutil.rmtree(path.parent)

    def test_real_vms_openapi_keeps_pinned_schema_dependency_errors(self):
        import check_spec
        self.write("Platform/common/dependency.schema.json", '{"type":"not-a-json-schema-type"}')
        self.write("VMS/api.openapi.yaml", """openapi: 3.1.0
info: {title: Fixture, version: '1'}
paths:
  /fixture:
    get:
      responses:
        '200':
          description: fixture
          content:
            application/json:
              schema: {$ref: '../Platform/common/dependency.schema.json'}
""")
        self.git("add", "Platform/common/dependency.schema.json", "VMS/api.openapi.yaml")
        self.git("commit", "-qm", "fixture invalid schema dependency")
        pin = self.git("rev-parse", "HEAD").decode().strip()
        self.write("VMS/PLATFORM_PIN", pin + "\n")
        view, _ = self.view()
        check = check_spec.Check(view, scope="vms")
        self.assertFalse(check.contract(view / "VMS/api.openapi.yaml"))
        self.assertTrue(any("dependency.schema.json" in error for error in check.errors), check.errors)

    def test_report_canonical_pass_candidate_failure_live_failure_nonblocking(self):
        import check_spec
        args = self.checker_args(vms_evidence=self.work / "report", vms_candidate="0" * 40, vms_live=True)
        def phase(args, view, names):
            check = check_spec.Check(view, scope="vms")
            if "live" in view.name:
                check.error(view / "Platform/owner.txt", "fixture live incompatibility")
            return check
        original = (self.root / "VMS/PLATFORM_PIN").read_bytes()
        with patch.object(check_spec, "_vms_phase", side_effect=phase), redirect_stdout(StringIO()):
            report = check_spec._vms_reports(args, [])
        self.assertEqual([r["status"] for r in report["phases"]], ["PASS", "ERROR", "FAIL"])
        self.assertEqual(report["canonical_status"], "PASS")
        self.assertEqual(report["phases"][1]["candidate_commit"], "0" * 40)
        self.assertTrue(report["phases"][1]["nonblocking"])
        self.assertTrue(report["phases"][2]["nonblocking"])
        self.assertTrue(report["code_inputs"])
        self.assertEqual(report["owner_platform_commit"], self.pin)
        self.assertEqual(report, json.loads((args.vms_evidence / "report.json").read_text()))
        self.assertEqual((self.root / "VMS/PLATFORM_PIN").read_bytes(), original)

    def test_missing_pin_reports_error_without_running_any_phase(self):
        import check_spec
        (self.root / "VMS/PLATFORM_PIN").unlink()
        args = self.checker_args(vms_evidence=self.work / "missing-report", vms_live=True)
        with patch.object(check_spec, "_vms_phase") as phase, redirect_stdout(StringIO()):
            report = check_spec._vms_reports(args, [])
        self.assertEqual(report["canonical_status"], "ERROR")
        phase.assert_not_called()

    def test_phase_routing_avoids_platform_globals_in_vms(self):
        import check_spec
        args = self.checker_args()
        calls = []
        class PhaseCheck:
            def __init__(self, root, exceptions=None, strict_coverage=False, *, scope=None):
                calls.append(("init", scope, strict_coverage))
                self.stats = {}
            def __getattr__(self, name):
                return lambda *a: calls.append(name)
        with patch.object(check_spec, "Check", PhaseCheck), patch.object(check_spec, "environment", return_value=[]):
            check_spec._vms_phase(args, self.root, ["VMS/norm.md"])
        self.assertEqual(calls, [("init", "vms", True), "lesson", "vms_module", "vector_hashes", "vms_frozen",
                                 "vms_families", "english_mirrors", "check_cyrillic"])

    def test_scoped_cyrillic_debt_is_readonly_and_does_not_stale_other_phase(self):
        import check_cyrillic
        self.write("Platform/a.tsv", "я\n")
        self.write("VMS/a.tsv", "я\n")
        self.git("add", "Platform/a.tsv", "VMS/a.tsv")
        debt = self.work / "scoped-debt.tsv"
        debt.write_text("kind\tpath\tletters\ndebt\tPlatform/a.tsv\t1\ndebt\tVMS/a.tsv\t1\n")
        before = debt.read_bytes()
        errors, stats = check_cyrillic.check(self.root, debt, source_scopes=("VMS",))
        self.assertEqual(errors, [])
        self.assertEqual(stats["cyrillic_debt_letters"], 1)
        for kwargs in ({"shrink": True}, {"declare_ready": ("VMS",)}):
            with self.assertRaisesRegex(ValueError, "read-only"):
                check_cyrillic.check(self.root, debt, source_scopes=("VMS",), **kwargs)
        self.assertEqual(debt.read_bytes(), before)

    def test_cell_proof_scope_selects_module_before_complete_bijection(self):
        import source_cells
        paths = []
        proof = ["table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n"]
        sha = hashlib.sha256(b"x").hexdigest()
        for module in ("Platform", "VMS"):
            name = module + "/common/cells.tsv"
            self.write(name, '# cell-json: value\nvalue\n"x"\n')
            paths.append(self.root / name)
            proof.append(f"{name}\t3\tvalue\t{sha}\t{sha}\n")
        self.write("Platform/common/data/cell-json-sha256.tsv", "".join(proof))
        manifest = self.root / "Platform/common/data/cell-json-sha256.tsv"
        self.assertEqual(source_cells.errors(self.root, paths), [])
        self.assertTrue(source_cells.errors(self.root, [paths[1]]))  # default still whole-ledger
        self.assertEqual(source_cells.errors(self.root, [paths[1]], source_scopes=("VMS",)), [])
        paths[0].write_text("unrelated changed live Platform table\n")
        self.assertEqual(source_cells.errors(self.root, [paths[1]], source_scopes=("VMS",)), [])
        self.assertTrue(source_cells.errors(self.root, paths))
        for name, body in (
            ("missing", proof[0] + proof[1]),
            ("extra", "".join(proof) + proof[2].replace("\t3\t", "\t4\t")),
            ("duplicate", "".join(proof) + proof[2]),
            ("malformed-width", "".join(proof) + "VMS/bad.tsv\t3\n"),
            ("bad-digest", "".join(proof).replace(proof[2], proof[2].replace(sha, "0" * 64, 1))),
            ("unsafe", "".join(proof) + proof[1].replace("Platform/common/cells.tsv", "../Platform/cells.tsv")),
            ("unselected-duplicate", "".join(proof) + proof[1]),
            ("unselected-malformed-hash", "".join(proof) + proof[1].replace("\t3\t", "\t4\t").replace(sha, "bad", 1)),
        ):
            with self.subTest(control=name):
                manifest.write_text(body)
                self.assertTrue(source_cells.errors(self.root, [paths[1]], source_scopes=("VMS",)))
        manifest.write_text("".join(proof))
        paths[1].write_text('# cell-json: value\nvalue\n"changed"\n')
        self.assertTrue(source_cells.errors(self.root, [paths[1]], source_scopes=("VMS",)))
        with self.assertRaisesRegex(ValueError, "outside explicit"):
            source_cells.errors(self.root, paths, source_scopes=("VMS",))

    def test_platform_phase_source_inventory_never_reads_vms_scenarios(self):
        import source_cells
        self.write("VMS/01-example/acceptance/1/scenarios.tsv", "bad ignored inventory\n")
        self.write("Platform/01-example/acceptance/1/scenarios.tsv", "# scenario\tstep\trequest\texpect\n")
        forms = source_cells.wire_headers(self.root, source_scopes=("Platform",))
        self.assertFalse(any(path.parts[0] == "VMS" for path in forms))
        self.assertTrue(any(path.name == "scenarios.tsv" for path in forms))

    def test_main_vms_only_routes_and_diagnostic_results_do_not_control_exit(self):
        import check_spec
        args = ["check_spec", "--root", str(self.root), "--scope", "vms", "--vms-live"]
        report = {"canonical_status": "PASS", "phases": [{"status": "PASS"}, {"status": "FAIL"}]}
        with patch("sys.argv", args), patch.object(check_spec, "_platform_phase") as platform, \
                patch.object(check_spec, "_vms_reports", return_value=report) as vms, redirect_stdout(StringIO()):
            self.assertEqual(check_spec.main(), 0)
        platform.assert_not_called()
        vms.assert_called_once()
        with patch("sys.argv", ["check_spec", "--root", str(self.root), "VMS/norm.md"]), \
                patch.object(check_spec, "_platform_phase") as platform, \
                patch.object(check_spec, "_vms_reports", return_value=report) as vms, redirect_stdout(StringIO()):
            self.assertEqual(check_spec.main(), 0)
        platform.assert_not_called()
        self.assertEqual(vms.call_args.args[1], ["VMS/norm.md"])

    def test_phase_inventory_scopes_and_default_direct_api(self):
        import check_spec
        for module in ("Platform", "VMS"):
            name = module + "/01-example/vectors/cases/README.md"
            self.write(name, "| [bytes](data.json) | `" + "0" * 64 + "` |\n")
            self.write(module + "/01-example/vectors/cases/data.json", "{}")
        platform = check_spec.Check(self.root, scope="platform")
        platform.vector_hashes()
        self.assertEqual(len(platform.errors), 1)
        self.assertTrue(platform.errors[0].startswith("Platform/"))
        vms = check_spec.Check(self.root, scope="vms")
        vms.vector_hashes()
        self.assertEqual(len(vms.errors), 1)
        self.assertTrue(vms.errors[0].startswith("VMS/"))
        whole = check_spec.Check(self.root)
        whole.vector_hashes()
        self.assertEqual(len(whole.errors), 2)

    def test_real_candidate_and_live_reports_preserve_canonical_pass(self):
        import check_spec
        self.write("VMS/common/lessons.tsv", "# lesson\tdir\ttitle\tsubsystem\tstatus\n")
        self.write("decisions/history/vms/id-map.tsv", "\t".join(check_spec.IDMAP_FIELDS) + "\n")
        self.write("VMS/common/data/catalog.tsv", "\t".join(check_spec.VMS_CATALOG_FIELDS) + "\n")
        self.write("Platform/common/data/catalog.tsv", "broken proposed Platform dependency\n")
        self.git("add", "VMS/common/lessons.tsv", "decisions/history/vms/id-map.tsv", "VMS/common/data/catalog.tsv", "Platform/common/data/catalog.tsv")
        self.git("commit", "-qm", "fixture proposed incompatible Platform")
        candidate = self.git("rev-parse", "HEAD").decode().strip()
        args = self.checker_args(vms_evidence=self.work / "actual-repin-report", vms_candidate=candidate, vms_live=True)
        original = (self.root / "VMS/PLATFORM_PIN").read_bytes()
        with redirect_stdout(StringIO()):
            report = check_spec._vms_reports(args, [])
        self.assertEqual([r["status"] for r in report["phases"]], ["PASS", "FAIL", "FAIL"], report["phases"][0]["errors"])
        self.assertEqual(report["canonical_status"], "PASS")
        self.assertEqual(report["phases"][1]["inputs"]["platform_commit"], candidate)
        self.assertEqual(report["phases"][1]["inputs"]["owner_platform_commit"], self.pin)
        self.assertTrue(any("Platform/common/data/catalog.tsv" in e for e in report["phases"][1]["errors"]))
        self.assertEqual((self.root / "VMS/PLATFORM_PIN").read_bytes(), original)

    def test_raw_source_modes_and_archive_omission_are_explicit(self):
        self.write("Platform/owner.txt", "raw\r\nbytes\n")
        (self.root / "Platform/owner.txt").chmod(0o755)
        self.git("add", "Platform/owner.txt")
        self.git("commit", "-qm", "fixture executable raw source")
        candidate = self.git("rev-parse", "HEAD").decode().strip()
        view, manifest = self.view(candidate=candidate)
        self.assertEqual((view / "Platform/owner.txt").read_bytes(), b"raw\r\nbytes\n")
        self.assertEqual((view / "Platform/owner.txt").stat().st_mode & 0o777, 0o755)
        self.write("Platform/.gitattributes", "owner.txt export-ignore\n")
        self.git("add", "Platform/.gitattributes")
        self.git("commit", "-qm", "fixture refused archive omission")
        candidate = self.git("rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(PinError, "complete selected Git source inventory"):
            self.view("refused-export-ignore", candidate=candidate)


class VmsEvidencePaths(unittest.TestCase):
    """Filesystem-only report setup controls; no course lessons or VMS check run."""
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="vms-evidence-path-control-")).resolve()
        self.source = self.work / "source"
        self.source.mkdir()
        self.physical = self.work / "physical-temp"
        self.physical.mkdir()
        self.alias = self.work / "temp-alias"
        self.alias.symlink_to(self.physical, target_is_directory=True)

    def args(self, evidence=None):
        import check_spec
        args = check_spec.arguments().parse_args(["--root", str(self.source), "--scope", "vms"])
        args.vms_evidence = evidence
        return args

    def run_report(self, args):
        import check_spec
        from contextlib import ExitStack
        from vms_platform_pin import PlatformPin
        def materialize(root, owner, destination, **kwargs):
            destination.mkdir()
            return {"fixture_only": True}
        with ExitStack() as stack:
            stack.enter_context(patch("vms_platform_pin.read_pin", return_value=PlatformPin("1" * 40, "2" * 64)))
            stack.enter_context(patch("vms_platform_pin.verify_owner_pin"))
            stack.enter_context(patch("vms_platform_pin.materialize_vms_view", side_effect=materialize))
            phase = stack.enter_context(patch.object(check_spec, "_vms_phase", side_effect=lambda a, view, n: check_spec.Check(view)))
            stack.enter_context(redirect_stdout(StringIO()))
            report = check_spec._vms_reports(args, [])
        phase.assert_called_once()
        self.assertEqual(report["canonical_status"], "PASS")
        return report

    def test_default_generated_temp_under_symlink_parent_reaches_report_phase(self):
        generated = Path(tempfile.mkdtemp(prefix="generated-", dir=self.alias))
        self.assertNotEqual(generated.parent.absolute(), generated.parent.resolve())
        with patch("tempfile.mkdtemp", return_value=str(generated)) as create:
            report = self.run_report(self.args())
        create.assert_called_once_with(prefix="check-spec-vms-")
        self.assertEqual(Path(report["phases"][0]["view"]).parent, generated.resolve())
        self.assertFalse(generated.exists())   # OBSH.54: a passing run without --vms-evidence removes its temporary directory

    def test_explicit_symlink_parent_is_rejected_without_canonicalizing(self):
        import check_spec
        evidence = self.alias / "explicit-evidence"
        with patch("tempfile.mkdtemp") as create, patch.object(check_spec, "_vms_phase") as phase:
            with self.assertRaisesRegex(PinError, "without symlink parents"):
                check_spec._vms_reports(self.args(evidence), [])
        create.assert_not_called()
        phase.assert_not_called()
        self.assertFalse(evidence.exists())

    def test_explicit_source_root_and_descendant_are_rejected(self):
        import check_spec
        for evidence in (self.source, self.source / "evidence"):
            with self.subTest(path=evidence), patch("tempfile.mkdtemp") as create:
                with self.assertRaisesRegex(PinError, "outside source"):
                    check_spec._vms_reports(self.args(evidence), [])
                create.assert_not_called()
        self.assertEqual(list(self.source.iterdir()), [])

    def test_default_generated_temp_inside_source_is_still_rejected(self):
        import check_spec
        generated = self.source / "generated"
        generated.mkdir()
        with patch("tempfile.mkdtemp", return_value=str(generated)):
            with self.assertRaisesRegex(PinError, "outside source"):
                check_spec._vms_reports(self.args(), [])
        self.assertFalse((generated / "report.json").exists())

    def test_explicit_fresh_canonical_directory_preserves_report_behavior(self):
        evidence = self.physical / "explicit-evidence"
        with patch("tempfile.mkdtemp") as create:
            report = self.run_report(self.args(evidence))
        create.assert_not_called()
        self.assertEqual(Path(report["phases"][0]["view"]).parent, evidence)
        self.assertTrue((evidence / "report.json").is_file())


if __name__ == "__main__":
    unittest.main()
