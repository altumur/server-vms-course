"""Тесты части `admin` (Архитектор 2026-11-05): out свежий, по YOURS-файлу на подкоманду формы с якорями норм, закрытый
admin.go, launch: App.Admin nil → admin.Run, own.go до разбора флагов; судья admin_judge — PASS на пакете как есть и
FAIL на мутантах (прежний «not implemented», код 2 вместо 1, own.go не подключён); --seed бережёт код модели."""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import admin_judge  # noqa: E402
import build_kit  # noqa: E402
import gen_admin  # noqa: E402

MOD = admin_judge.MODULE
PARTS = list(admin_judge.PARTS)
OUT = HERE / "out/p01-1/go"


def judge(kit):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = admin_judge.judge(kit)
    return code, buf.getvalue()


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
        self.assertIn("import: from an immutable copy", text["import"])
        self.assertIn("copy: the backup copy", text["backup"])
        self.assertIn("floor: (platform/epoch_floor {floor, generation_at}); generation:", text["restore"])
        self.assertIn("req: P/01.3-R020 — ", text["recover"])
        self.assertIn("| Isolation |", text["recover"])                # R026 — таблица фаз целиком, не первая строка
        self.assertIn("«recover the store (no majority)»", text["recover"])
        self.assertIn("recover — a refusal, code 2", text["recover"])
        self.assertIn("req: P/01.3-R018 — The CLI `backup`", text["backup"])
        self.assertIn("GET `/v1/status`: `{id, state", text["status"])
        self.assertIn("req: P/01.2-R014 — `GET /v1/rights` returns", text["rights"])
        self.assertIn("leave — 409 refused («the last voter»)", text["leave"])
        self.assertNotIn("join of its own id", text["recover"])          # box: только оговорки о своей подкоманде
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


if __name__ == "__main__":
    unittest.main()
