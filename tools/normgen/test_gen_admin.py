"""Test admin freshness, one YOURS file per declared command with norm anchors, closed dispatcher, default launch dispatch and Own before flag parsing. Require the shipped kit to pass admin_judge and mutants to fail (old not implemented, exit 2 instead of1, unwired Own). --seed must preserve model code."""
import lesson as output_lesson
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import admin_judge  # noqa: E402
import build_kit  # noqa: E402
import gen_admin  # noqa: E402

MOD = admin_judge.MODULE
PARTS = list(admin_judge.PARTS)
OUT = output_lesson.output_root() / 'p01-1/go'


def judge(kit):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = admin_judge.judge(kit)
    return code, buf.getvalue()


class DirectiveLabels(unittest.TestCase):
    def render_with(self, label):
        with tempfile.TemporaryDirectory(prefix="admin-labels-") as tmp:
            root = Path(tmp)
            common = root / "Platform/common/acceptance/README.md"
            common.parent.mkdir(parents=True)
            common.write_text(f"| `@spoil row <{label}>` / `@spoil row-index <{label}>` | stopped store | command `spoil-row` |\n")
            with patch.object(gen_admin, "ROOT", root), patch.object(gen_admin, "COMMON", common):
                return gen_admin.render()[0]

    def test_old_and_new_labels_keep_dispatch_and_stub(self):
        old, new = self.render_with('\u043a\u043b\u044e\u0447'), self.render_with("key")
        self.assertEqual(old, new)
        self.assertIn('"spoil-row": SpoilRow,', new["admin/own.go"])
        self.assertIn('return NotInStage("spoil-row", env)', new["admin/own.go"])

    def test_unknown_label_is_not_a_directive(self):
        with self.assertRaisesRegex(gen_admin.GenError, "no directive row"):
            self.render_with("invented")

    def test_commands_receive_decoded_cells_and_validate_proof(self):
        import hashlib
        import tsv_input
        expected = gen_admin.commands()
        source = tsv_input.read(gen_admin.FLAGS, root=gen_admin.ROOT)
        with tempfile.TemporaryDirectory(prefix="admin-transport-") as tmp:
            root = Path(tmp)
            path = root / "Platform/01-store/forms/daemon-flags.tsv"
            path.parent.mkdir(parents=True)
            lines = ["# cell-json: flag", "\t".join(source.columns)]
            proofs = ["\t".join(tsv_input._PROOF_COLUMNS)]
            for no, (_, row) in enumerate(source.rows, 3):
                lines.append("\t".join(json.dumps(row[col], ensure_ascii=True) if col == "flag" else row[col]
                                       for col in source.columns))
                sha = hashlib.sha256(row["flag"].encode()).hexdigest()
                proofs.append("\t".join((path.relative_to(root).as_posix(), str(no), "flag", sha, sha)))
            path.write_text("\n".join(lines) + "\n")
            proof = root / tsv_input._PROOF
            proof.parent.mkdir(parents=True)
            proof.write_text("\n".join(proofs) + "\n")
            with patch.object(gen_admin, "ROOT", root), patch.object(gen_admin, "FLAGS", path):
                self.assertEqual(gen_admin.commands(), expected)
                proof.write_text("\n".join(proofs[:-1]) + "\n")
                with self.assertRaisesRegex(gen_admin.GenError, "byte proof"):
                    gen_admin.commands()


class Admin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="nadmin-")
        cls.kit = Path(cls.tmp.name) / "kit"
        cls.manifest = build_kit.build(cls.kit, MOD, PARTS)
        cls.pkg = cls.kit / "01-store/internal/admin"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_out_fresh(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        files, _ = gen_admin.render()
        for rel, text in files.items():
            self.assertEqual((OUT / rel).read_text(encoding="utf-8"), text, f"{rel}: run gen_admin.py")
        self.assertEqual(sorted(p.name for p in (OUT / "admin").glob("*.go")), sorted(Path(r).name for r in files))

    def test_one_file_per_subcommand(self):
        cmds, flags = gen_admin.commands()
        self.assertEqual(set(cmds), {"recover", "restore", "import", "status", "join", "leave", "admit", "backup", "rights"})
        admin = (self.pkg / "admin.go").read_text(encoding="utf-8")
        self.assertIn("DO NOT EDIT", admin)
        for cmd in cmds:
            text = (self.pkg / f"{cmd}.go").read_text(encoding="utf-8")
            name = gen_admin.go_name(cmd)
            self.assertEqual(re.findall(r"^func (\w+)\(", text, re.M), [name])
            self.assertIn(f"func {name}(f *flags.Flags, env Env) int {{", text)
            self.assertIn(f'return NotInStage("{cmd}", env)', text)
            if cmd in ("backup", "import", "restore"):
                self.assertIn("if env.Copy != nil", text)
                self.assertIn(f'return runCopy("{cmd}", f, env)', text)
            self.assertIn(f'case "{cmd}":\n\t\treturn {name}(f, env)', admin)
            self.assertNotIn("DO NOT EDIT", text)
            self.assertIn("(req: P/01.3-R006)", text)
            self.assertIn("admin_ops: " + cmd, text)
            for fl, _, _ in flags[cmd]:
                self.assertIn(f"//\t  {fl} ", text, (cmd, fl))
            for r in gen_admin.REFUSAL_ROWS[cmd]:
                self.assertIn(f" {r} — ", text, (cmd, r))

    def test_anchors_by_table(self):
        text = {c: (self.pkg / f"{c}.go").read_text(encoding="utf-8") for c in gen_admin.KEYS}
        self.assertIn("import: --from <copy>", text["import"])
        self.assertIn("req: P/01.3-R149", text["import"])
        self.assertIn("copy: JSON Lines", text["backup"])
        self.assertIn("floor: (platform/epoch_floor {floor, generation_at}); generation:", text["restore"])
        self.assertIn("req: P/01.3-R020 — ", text["recover"])
        self.assertIn("| Isolation |", text["recover"])                # R026 is the full phase table, not just its first row.
        self.assertIn("«recover the store (no majority)»", text["recover"])
        self.assertIn("`recover` MUST be a refusal, code 2", text["recover"])
        self.assertIn("req: P/01.3-R018 — The CLI `backup`", text["backup"])
        self.assertIn("GET `/v1/status`: status-fields.tsv", text["status"])
        self.assertIn("req: P/01.2-R014 — `GET /v1/rights` returns", text["rights"])
        self.assertIn("`leave` MUST give 409 `refused` («the last voter»)", text["leave"])
        self.assertIn("req: P/01.3-R169", text["recover"])          # box includes only clauses about the current subcommand.
        own = (self.pkg / "own.go").read_text(encoding="utf-8")
        self.assertIn('"spoil-row": SpoilRow,', own)
        self.assertIn("the command `spoil-row` of «Stand»", own)

    def test_manifest_editable_and_doc(self):
        own = {f["path"] for f in self.manifest["files"] if f.get("editable")}
        closed = {f["path"] for f in self.manifest["files"] if not f.get("editable")}
        self.assertIn("01-store/internal/admin/admin.go", closed)
        for name in ("own.go", "backup.go", "import.go", "recover.go"):
            self.assertIn(f"01-store/internal/admin/{name}", own)
        self.assertIn("admin", self.manifest["provenance"])
        doc = (self.kit / "KIT.md").read_text(encoding="utf-8")
        self.assertIn("## Part `admin`", doc)
        self.assertIn("**Subcommands.**", doc)
        self.assertIn("func Import(f *flags.Flags, env Env) int", doc)
        self.assertIn("Never put a flag of `daemon-flags.tsv` or a subcommand of admin_ops there.", doc)
        self.assertIn("### `admin`", doc)

    def test_judge_pass(self):
        code, out = judge(self.kit)
        self.assertEqual(code, 0, out)
        cmds, _ = gen_admin.commands()
        self.assertIn(f"admin: {3 * len(cmds) + len(admin_judge.OWN)}/{3 * len(cmds) + len(admin_judge.OWN)} PASS", out)

    def mutant(self, rel, old, new):
        t = tempfile.mkdtemp(prefix="nadmin-m-", dir=self.tmp.name)
        kit = Path(t) / "kit"
        shutil.copytree(self.kit, kit)
        f = kit / "01-store/internal" / rel
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text)
        f.write_text(text.replace(old, new), encoding="utf-8")
        return judge(kit)

    def test_mutants_killed(self):
        for rel, old, new, why in (
                ("launch/launch.go", "return admin.Run(f, env)",
                 'fmt.Fprintf(log, "configstore: %s: not implemented\\n", f.Cmd)\n\t\t\treturn 1', "old not implemented"),
                ("admin/admin.go", "const NotInStageCode = 1", "const NotInStageCode = 2", "code 2"),
                ("launch/launch.go", "if own, ok := admin.Own[args[0]]; ok {", "if own, ok := admin.Own[args[0]]; ok && false {",
                 "own.go not looked up"),
                ("admin/admin.go", 'case "import":\n\t\treturn Import(f, env)', 'case "import":\n\t\treturn 0', "dispatch")):
            code, out = self.mutant(rel, old, new)
            self.assertNotEqual(code, 0, f"mutant survived: {why}\n{out}")
            self.assertIn("FAIL", out, why)

    def test_seed_keeps_model_code(self):
        t = Path(tempfile.mkdtemp(prefix="nadmin-s-", dir=self.tmp.name))
        seed = t / "seed"
        shutil.copytree(self.kit, seed)
        backup = seed / "01-store/internal/admin/backup.go"
        backup.write_text(backup.read_text(encoding="utf-8").replace('return NotInStage("backup", env)', "return 0"),
                          encoding="utf-8")
        m = build_kit.build(t / "kit", MOD, PARTS, seed=seed)
        self.assertIn("01-store/internal/admin/backup.go", m["seed"]["kept"])
        self.assertIn("01-store/internal/admin/import.go", m["seed"]["refreshed"])
        self.assertFalse((t / "kit/01-store/internal/admin/backup.go").exists())
        self.assertTrue((t / "kit/01-store/internal/admin/admin.go").exists())

    def test_needs_parts(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(build_kit.KitError, "--part launch needs --part admin"):
                build_kit.build(t, MOD, ["door", "flags", "stagetests", "launch"])
            with self.assertRaisesRegex(build_kit.KitError, "--part admin needs --part flags"):
                build_kit.build(t, MOD, ["admin"])

    def test_tables_closed(self):
        saved = dict(gen_admin.KEYS)
        try:
            del gen_admin.KEYS["backup"]
            with self.assertRaisesRegex(gen_admin.GenError, "KEYS"):
                gen_admin.render()
        finally:
            gen_admin.KEYS.clear()
            gen_admin.KEYS.update(saved)
        saved = gen_admin.REFUSAL_ROWS["admit"]
        try:
            gen_admin.REFUSAL_ROWS["admit"] = ("no_such_row",)
            with self.assertRaises(gen_admin.GenError):
                gen_admin.render()
        finally:
            gen_admin.REFUSAL_ROWS["admit"] = saved


Z21_BACKUP_BINDING = r'''package admin
import (
    "bytes"
    "errors"
    "strings"
    "testing"
    "normgen/p01-1/flags"
)
type z21CopyPort struct{calls int;file string;err error}
func (p *z21CopyPort) Backup(file string) error {p.calls++;p.file=file;return p.err}
func (*z21CopyPort) Import(string,uint64,bool) error {panic("backup called import")}
func (*z21CopyPort) Restore(string,bool) error {panic("backup called restore")}
func TestZ21AdminBackupExistingPort(t *testing.T) {
    var out,log bytes.Buffer
    port:=&z21CopyPort{}
    f:=&flags.Flags{Cmd:"backup",Args:[]string{"the-output.copy"}}
    code:=Run(f,Env{Stdout:&out,Stderr:&log,Copy:port})
    if code!=0 || port.calls!=1 || port.file!="the-output.copy" || out.Len()!=0 || log.Len()!=0 {t.Fatalf("existing CLI binding: %d %+v %q %q",code,port,out.String(),log.String())}
}
func TestZ21AdminBackupFailureAndArguments(t *testing.T) {
    var out,log bytes.Buffer
    port:=&z21CopyPort{err:errors.New("controlled copy failure")}
    env:=Env{Stdout:&out,Stderr:&log,Copy:port}
    if code:=Run(&flags.Flags{Cmd:"backup",Args:[]string{"out"}},env);code!=1 || port.calls!=1 || !strings.Contains(log.String(),port.err.Error()) || out.Len()!=0 {t.Fatal("copy failure was hidden or became a machine stdout contract")}
    port.calls=0;log.Reset()
    if code:=Run(&flags.Flags{Cmd:"backup"},env);code!=2 || port.calls!=0 {t.Fatal("wrong positional arguments reached backup")}
}
'''


class Z21BackupSource(unittest.TestCase):
    source_root = HERE.parent.parent
    code_root = HERE.parent.parent

    @classmethod
    def setUpClass(cls):
        from test_gen_core import z21_ready_p01
        cls.output = output_lesson.output_root()
        cls.output_receipt = os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV)
        cls.ready = z21_ready_p01(cls.output, cls.source_root, cls.code_root,
                                 expected_manifest_sha256=cls.output_receipt)
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-admin-")

    @classmethod
    def tearDownClass(cls):
        from test_gen_core import z21_ready_p01
        cls.tmp.cleanup()
        z21_ready_p01(cls.output, cls.source_root, cls.code_root, expected_manifest_sha256=cls.output_receipt)

    def test_backup_comments_bind_actual_copy_contract_and_all_three_causes(self):
        import csv
        from test_gen_core import z21_assert_requirement_comment, z21_source_requirement
        text = (self.ready["p01-1"] / "go/admin/backup.go").read_text()
        source = z21_source_requirement(self.source_root, 3, "P/01.3-R033")
        z21_assert_requirement_comment(text, "P/01.3-R033", source)
        with self.assertRaises(AssertionError):
            z21_assert_requirement_comment(text.replace("P/01.3-R033", "P/00.0-R000"), "P/01.3-R033", source)
        raw = (self.source_root / "Platform/01-store/forms/refusals.tsv").read_text()
        rows = list(csv.DictReader([l for l in raw.splitlines() if l and not l.startswith("#")], delimiter="\t"))
        for name in ("copy_method", "copy_admin_only", "copy_snapshot_unavailable"):
            found = [r for r in rows if r["name"] == name]
            self.assertEqual(len(found), 1)
            row = found[0]
            expected = f'{row["chapter"]} row {row["row"]} {name} — {row["code"]} {row["kind"]}'
            self.assertIn(expected, text)
            self.assertNotIn(expected, text.replace(name, "removed_cause"))

    def test_compiled_backup_dispatch_keeps_existing_arguments_port_and_failure_exit(self):
        from test_gen_machine import CheckingError, complete_go_tests
        module = Path(self.tmp.name) / "normal"
        shutil.copytree(self.ready["p01-1"] / "go", module)
        (module / "admin/z21_copy_test.go").write_text(Z21_BACKUP_BINDING, encoding="utf-8")
        names = ["TestZ21AdminBackupExistingPort", "TestZ21AdminBackupFailureAndArguments"]
        try:
            done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^(" + "|".join(names) + ")$", "./admin"],
                                  cwd=module, capture_output=True, timeout=120)
            observed = SimpleNamespace(returncode=done.returncode, stdout=done.stdout.decode("utf-8", "strict"),
                                       stderr=done.stderr.decode("utf-8", "strict"))
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise CheckingError("cannot obtain complete admin component report") from exc
        self.assertEqual(complete_go_tests(observed, names, "normgen/p01-1/admin"), [])


if __name__ == "__main__":
    unittest.main()
