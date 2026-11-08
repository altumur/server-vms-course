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


def _admin_source_requirement(path, identity):
    text = Path(path).read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^<!-- req: " + re.escape(identity)
                         + r" -->\s*([\s\S]*?)(?=^<!-- req:|^#{2,4} |\Z)", text)
    if len(matches) != 1 or not matches[0].strip():
        raise AssertionError("missing/ambiguous Source admin requirement " + identity)
    return matches[0]


def _admin_source_contract(root):
    """Read command/flag/anchor facts from Source, independently of gen_admin's report."""
    import tsv_input
    root = Path(root)
    base = root / "Platform/01-store"
    flags = tsv_input.read(base / "forms/daemon-flags.tsv", root=root)
    if not {"flag", "type", "required", "commands"} <= set(flags.columns):
        raise AssertionError("incomplete Source command flags")
    commands, by_command, seen = [], {}, set()
    for _, row in flags.rows:
        if row["flag"] in seen:
            raise AssertionError("duplicate Source flag")
        seen.add(row["flag"])
        owners = row["commands"].split(",")
        if len(owners) != len(set(owners)) or any(not re.fullmatch(r"[a-z][a-z-]*", c) for c in owners):
            raise AssertionError("malformed Source command ownership")
        for command in owners:
            if command == "daemon":
                continue
            if command not in by_command:
                commands.append(command); by_command[command] = []
            by_command[command].append((row["flag"], row["type"], row["required"]))
    norms = base / "spec/01.3-store.norms.md"
    block = _admin_source_requirement(norms, "P/01.3-R006")
    yaml = re.findall(r"```yaml\n(.*?)\n```", block, re.S)
    if len(yaml) != 1:
        raise AssertionError("missing Source admin declaration block")
    clauses = dict(re.findall(r"(?m)^([a-z_]+):\s*([\s\S]*?)(?=^[a-z_]+:|\Z)", yaml[0]))
    grammar = clauses.get("admin_ops", "")
    roster = [re.match(r"\s*([a-z][a-z-]*)\b", part) for part in grammar.split("|")]
    if not roster or any(m is None for m in roster):
        raise AssertionError("malformed Source admin_ops")
    declared = [m[1] for m in roster]
    if len(set(declared)) != len(declared) or set(declared) != set(commands):
        raise AssertionError("Source flags/admin_ops command mismatch")
    # These are the accepted subcommand bindings; every target must still exist in full Source.
    keys = {"recover": [("box", "word")], "restore": [("copy", "all"), ("floor", "all"), ("box", "word")],
            "import": [("copy", "all"), ("import", "all"), ("floor", "all"), ("box", "word")],
            "status": [("box", "word")], "join": [("repeat", "word"), ("box", "word")],
            "leave": [("repeat", "word"), ("box", "word")], "admit": [("repeat", "word"), ("box", "word")],
            "backup": [("copy", "all")], "rights": []}
    refusals = {"recover": ("recover_box", "recover_isolated", "recover_upper", "recover_peers", "recovery_unsafe", "clock_early"),
                "restore": ("copy_input", "clock_early"), "import": ("copy_input", "import_repeated", "clock_early"),
                "status": (), "join": ("join_parity", "join_left"), "leave": ("box_last_voter",),
                "admit": ("box_admit",),
                "backup": ("backup_inside_dir", "copy_method", "copy_admin_only", "copy_snapshot_unavailable"),
                "rights": ("rights_not_loaded",)}
    doors = {"backup": [("01.3-store.norms.md", "P/01.3-R033", None)],
             "status": [("01.3-store.norms.md", "P/01.3-R016", "door:GET `/v1/status`")],
             "join": [("01.3-store.norms.md", "P/01.3-R016", "door:POST `/v1/join`")],
             "leave": [("01.3-store.norms.md", "P/01.3-R016", "door:POST `/v1/leave`")],
             "rights": [("01.2-store.norms.md", "P/01.2-R014", None)]}
    if set(commands) != set(keys):
        raise AssertionError("Source command binding roster changed")
    for command, selections in keys.items():
        for key, mode in selections:
            if key not in clauses or not clauses[key].strip() or (mode == "word" and
                    not re.search(r"(?<![\w-])" + command + r"(?![\w-])", clauses[key])):
                raise AssertionError("missing Source admin clause " + command + ":" + key)
    table = tsv_input.read(base / "forms/refusals.tsv", root=root)
    if not {"name", "code", "kind", "norm"} <= set(table.columns):
        raise AssertionError("incomplete Source refusal table")
    rows = {}
    for _, row in table.rows:
        if row["name"] in rows:
            raise AssertionError("duplicate Source refusal")
        rows[row["name"]] = row
    for values in refusals.values():
        for name in values:
            if name not in rows or not all(rows[name][field] for field in ("code", "kind", "norm")):
                raise AssertionError("missing Source refusal binding " + name)
    anchors = {"P/01.3-R006", "P/01.3-R018"}
    _admin_source_requirement(norms, "P/01.3-R018")
    for values in doors.values():
        for filename, anchor, selector in values:
            body = _admin_source_requirement(base / "spec" / filename, anchor)
            if selector and len(re.findall(r"\| " + re.escape(selector[5:]) + r" \|", body)) != 1:
                raise AssertionError("missing/ambiguous Source admin door " + selector)
            anchors.add(anchor)
    text = norms.read_text(encoding="utf-8")
    recovery = re.findall(r"(?m)^### recover the store \(no majority\)\n([\s\S]*?)(?=^#{2,4} |\Z)", text)
    if len(recovery) != 1:
        raise AssertionError("missing Source recover procedure")
    recovery_ids = re.findall(r"<!-- req: (P/01\.3-R[0-9]+) -->", recovery[0])
    if not recovery_ids or len(set(recovery_ids)) != len(recovery_ids):
        raise AssertionError("missing/duplicate Source recover anchors")
    for identity in recovery_ids:
        _admin_source_requirement(norms, identity)
        anchors.add(identity)
    own = (root / "Platform/common/acceptance/README.md").read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^\| `@spoil row <(?:key|ключ)>` / `@spoil row-index <(?:key|ключ)>` \|[^\n]*`spoil-row`", own)) != 1:
        raise AssertionError("missing/ambiguous Source stand command")
    return dict(root=str(root.resolve()), commands=commands, flags=by_command, keys=keys, refusals=refusals, doors=doors, anchors=anchors)


def _assert_admin_selectors(producer, source):
    if producer.commands() != (source["commands"], source["flags"]):
        raise AssertionError("Source command/flag metadata mismatch")
    root = Path(source["root"])
    doors = {cmd: [(str(path.resolve()), anchor, selector) for path, anchor, selector in values]
             for cmd, values in producer.DOORS.items()}
    expected_doors = {cmd: [(str((root / "Platform/01-store/spec" / filename).resolve()), anchor, selector)
                            for filename, anchor, selector in values] for cmd, values in source["doors"].items()}
    if producer.KEYS != source["keys"] or producer.REFUSAL_ROWS != source["refusals"] or doors != expected_doors:
        raise AssertionError("Source KEYS/DOORS/REFUSAL_ROWS binding mismatch")


def _admin_go_tokens(text):
    pattern = r'\s+|//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|`[^`]*`|[A-Za-z_][A-Za-z_0-9]*|[^\w\s]'
    tokens = [m[0] for m in re.finditer(pattern, text, re.S)
              if not m[0].isspace() and not m[0].startswith(("//", "/*"))]
    return tokens


def _admin_go_functions(text):
    tokens = _admin_go_tokens(text)
    functions, depth, at = {}, 0, 0
    while at < len(tokens):
        token = tokens[at]
        if token == "func" and depth == 0 and at + 2 < len(tokens) and tokens[at + 2] == "(":
            name, start = tokens[at + 1], at
            if name in functions:
                raise AssertionError("duplicate actual admin function " + name)
            while at < len(tokens) and tokens[at] != "{":
                at += 1
            header = tokens[start:at]
            end, nesting = at + 1, 1
            while end < len(tokens) and nesting:
                nesting += (tokens[end] == "{") - (tokens[end] == "}")
                end += 1
            if nesting:
                raise AssertionError("unclosed actual admin function")
            functions[name] = (header, tokens[at + 1:end - 1])
            at = end
            continue
        depth += (token == "{") - (token == "}")
        at += 1
    return functions


def _assert_admin_layout(pkg, manifest, commands):
    """Check actual declarations/delegation plus manifest ownership; comments carry no authority."""
    expected_files = {c + ".go" for c in commands} | {"admin.go", "own.go"}
    if {p.name for p in Path(pkg).glob("*.go")} != expected_files:
        raise AssertionError("incomplete/extra actual admin files")
    for filename in expected_files:
        tokens = _admin_go_tokens((Path(pkg) / filename).read_text())
        if tokens[:2] != ["package", "admin"] or tokens.count("package") != 1:
            raise AssertionError("actual admin package ownership " + filename)
    entries = {}
    for row in manifest["files"]:
        if row["path"] in entries:
            raise AssertionError("duplicate manifest path")
        entries[row["path"]] = row
    run = _admin_go_functions((Path(pkg) / "admin.go").read_text()).get("Run")
    if run is None:
        raise AssertionError("missing actual admin.Run")
    cases = [run[1][i + 1] for i, token in enumerate(run[1][:-1]) if token == "case"]
    if set(cases) != {'"' + c + '"' for c in commands} or len(cases) != len(commands):
        raise AssertionError("Source admin dispatcher roster mismatch")
    for filename in expected_files:
        row = entries.get("01-store/internal/admin/" + filename, {})
        if row.get("editable") is not (filename != "admin.go"):
            raise AssertionError("admin manifest ownership " + filename)
    for command in commands:
        name = "".join(part[:1].upper() + part[1:] for part in command.split("-"))
        functions = _admin_go_functions((Path(pkg) / (command + ".go")).read_text())
        if set(functions) != {name}:
            raise AssertionError("actual per-command function roster " + command)
        header, body = functions[name]
        signature = ['func', name, '(', 'f', '*', 'flags', '.', 'Flags', ',', 'env', 'Env', ')', 'int']
        want = ['return', 'NotInStage', '(', '"' + command + '"', ',', 'env', ')']
        if command in ("backup", "import", "restore"):
            want = ['if', 'env', '.', 'Copy', '!=', 'nil', '{', 'return', 'runCopy', '(',
                    '"' + command + '"', ',', 'f', ',', 'env', ')', '}', *want]
        # The lexical reader emits each punctuation character separately.
        want = [piece for token in want for piece in (['!', '='] if token == '!=' else [token])]
        dispatch = ['case', '"' + command + '"', ':', 'return', name, '(', 'f', ',', 'env', ')']
        if header != signature or body != want or not any(run[1][i:i + len(dispatch)] == dispatch
                                                         for i in range(len(run[1]))):
            raise AssertionError("actual admin signature/delegation " + command)
    own = _admin_go_functions((Path(pkg) / "own.go").read_text())
    if set(own) != {"SpoilRow"} or own["SpoilRow"][0] != ['func', 'SpoilRow', '(', 'args', '[', ']', 'string', ',', 'env', 'Env', ')', 'int']:
        raise AssertionError("actual stand command ownership/signature")
    tokens = _admin_go_tokens((Path(pkg) / "own.go").read_text())
    binding = ['var', 'Own', '=', 'map', '[', 'string', ']', 'func', '(', 'args', '[', ']', 'string',
               ',', 'env', 'Env', ')', 'int', '{', '"spoil-row"', ':', 'SpoilRow', ',', '}']
    if sum(tokens[i:i + len(binding)] == binding for i in range(len(tokens))) != 1:
        raise AssertionError("actual stand command dispatch binding")


class CosmeticAdminControls(unittest.TestCase):
    """Synthetic machine-only package and Source-selection controls, no build/setup."""
    def fixture(self, root):
        pkg = Path(root)
        (pkg / 'admin.go').write_text('package admin\nfunc Run(f *flags.Flags, env Env) int { switch f.Cmd { case "status": return Status(f, env) }; return 1 }\n')
        (pkg / 'status.go').write_text('package admin\nfunc Status(f *flags.Flags, env Env) int { return NotInStage("status", env) }\n')
        (pkg / 'own.go').write_text('package admin\nvar Own = map[string]func(args []string, env Env) int{"spoil-row": SpoilRow,}\nfunc SpoilRow(args []string, env Env) int { return NotInStage("spoil-row", env) }\n')
        return {'files': [dict(path='01-store/internal/admin/' + file, editable=file != 'admin.go')
                          for file in ('admin.go', 'status.go', 'own.go')]}

    def test_00_comment_free_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            _assert_admin_layout(Path(tmp), self.fixture(tmp), ['status'])

    def test_missing_wrong_signature_delegation_and_comment_only_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(tmp); path = Path(tmp) / 'status.go'; normal = path.read_text()
            for wrong in (normal.replace('Status(', 'Other('), normal.replace('return NotInStage("status", env)', 'return 0'),
                          normal.replace('flags.Flags', 'Other'), '/*' + normal + '*/'):
                path.write_text(wrong)
                with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                    _assert_admin_layout(Path(tmp), manifest, ['status'])

    def test_manifest_and_dispatch_ownership_are_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(tmp)
            manifest['files'][1]['editable'] = False
            with self.assertRaisesRegex(AssertionError, 'ownership'):
                _assert_admin_layout(Path(tmp), manifest, ['status'])
            manifest['files'][1]['editable'] = True
            p = Path(tmp) / 'admin.go'; p.write_text(p.read_text().replace('return Status(f, env)', 'return 0'))
            with self.assertRaisesRegex(AssertionError, 'delegation'):
                _assert_admin_layout(Path(tmp), manifest, ['status'])

    def test_comment_only_map_and_wrong_package_do_not_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(tmp); path = Path(tmp) / 'own.go'; normal = path.read_text()
            for wrong in (normal.replace('var Own =', '// var Own ='), normal.replace('package admin', 'package foreign')):
                path.write_text(wrong)
                with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                    _assert_admin_layout(Path(tmp), manifest, ['status'])

    def test_same_basename_foreign_source_is_not_a_binding(self):
        from types import SimpleNamespace
        source = dict(root='/synthetic', commands=['status'], flags={'status': []}, keys={}, refusals={},
                      doors={'status': [('01.3-store.norms.md', 'P/01.3-R016', None)]})
        producer = SimpleNamespace(commands=lambda: (['status'], {'status': []}), KEYS={}, REFUSAL_ROWS={},
                  DOORS={'status': [(Path('/synthetic/Platform/01-store/spec/01.3-store.norms.md'), 'P/01.3-R016', None)]})
        _assert_admin_selectors(producer, source)
        producer.DOORS['status'][0] = (Path('/foreign/01.3-store.norms.md'), 'P/01.3-R016', None)
        with self.assertRaisesRegex(AssertionError, 'binding'):
            _assert_admin_selectors(producer, source)

    def test_source_selectors_not_producer_report(self):
        from types import SimpleNamespace
        source = dict(root='/synthetic', commands=['status'], flags={'status': [('-x', 'bool', 'false')]}, keys={'status': []},
                      refusals={'status': ()}, doors={})
        producer = SimpleNamespace(commands=lambda: (['status'], source['flags']), KEYS={'status': []},
                                   REFUSAL_ROWS={'status': ()}, DOORS={})
        _assert_admin_selectors(producer, source)
        for name, value in [('KEYS', {}), ('REFUSAL_ROWS', {'status': ('invented',)}),
                            ('DOORS', {'status': [(Path('wrong'), 'P/01.3-R999', None)]}),
                            ('commands', lambda: (['status'], {'status': []}))]:
            old = getattr(producer, name); setattr(producer, name, value)
            with self.subTest(name=name), self.assertRaises(AssertionError):
                _assert_admin_selectors(producer, source)
            setattr(producer, name, old)

    def test_source_anchor_missing_duplicate_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'norms.md'
            normal = '<!-- req: P/01.3-R006 -->\nindependent body\n'
            path.write_text(normal)
            self.assertIn('independent body', _admin_source_requirement(path, 'P/01.3-R006'))
            for wrong in (normal.replace('R006', 'R999'), normal + normal, '<!-- req: P/01.3-R006 -->\n'):
                path.write_text(wrong)
                with self.subTest(wrong=wrong), self.assertRaises(AssertionError):
                    _admin_source_requirement(path, 'P/01.3-R006')


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
        source = _admin_source_contract(gen_admin.ROOT)
        _assert_admin_selectors(gen_admin, source)
        _assert_admin_layout(self.pkg, self.manifest, source["commands"])

    def test_anchors_by_table(self):
        source = _admin_source_contract(gen_admin.ROOT)
        _assert_admin_selectors(gen_admin, source)
        self.assertTrue(source["anchors"])
        own = (self.pkg / "own.go").read_text(encoding="utf-8")
        self.assertIn('"spoil-row": SpoilRow,', own)
        self.assertIn("SpoilRow", _admin_go_functions(own))

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
