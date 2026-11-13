"""Generate the admin kit part: a closed dispatcher and one YOURS scaffold per P/01.3 N1.3 admin_ops subcommand (Architect, 2026-11-05; MiniMax 30-32 needed explicit backup/import implementation files).

  python3 tools/normgen/gen_admin.py [<out>]
Default: tools/normgen/out/p01-1. Output: <out>/go/admin. admin.go is closed and defines Env, Run(f, env), and NotInStage. Run dispatches on f.Cmd; NotInStage prints `configstore <cmd>: not in this stage` and returns 1. Invalid flags return 2 in launch before Run.

Each <command>.go is YOURS, installed once and protected by --seed, with func <Name>(f *flags.Flags, env Env) int initially calling NotInStage. Its comments bind the command grammar, admin_ops clauses, KEYS-selected copy/import/floor/box/repeat clauses, relevant P/01.3-R018 sentences, the complete recover N3 procedure, the relevant HTTP door, command-specific flags and REFUSALS-selected rows. own.go provides the YOURS Own map for stand commands such as spoil-row, checked by launch.Main before parsing flags.

The ordered roster comes from daemon-flags.tsv commands, excluding daemon. It must agree with admin_ops and the generator declarations or generation refuses. Closed launch uses admin.Run when App.Admin is nil. Judges: admin_judge.py and test_gen_admin.py; unimplemented commands return 1, invalid flags return 2."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_core  # noqa: E402 -- norm parsing, comment wrapping and refusals.tsv rows
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
import tsv_input  # noqa: E402 — source cells before command interpretation
L = lesson.CURRENT

DEFAULT_OUT = L.out
NORMS_13 = L.norms("3")
NORMS_12 = L.norms("2")
NORMS_11 = L.norms("1")
FLAGS = L.form("daemon-flags.tsv")
REFUSALS = L.form("refusals.tsv")
COMMON = ROOT / "Platform/common/acceptance/README.md"
JUDGE = HERE / "admin_judge.py"
GO_MODULE = L.go_module
BLOCK_ANCHOR = "P/01.3-R006"            # N1.3 Store YAML block: daemon, copy, ..., admin_ops, floor, import, box, repeat.
CLI_ANCHOR = "P/01.3-R018"              # CLI backup, restore/import, recover, admit
RECOVER = "recover the store (no majority)"

# Subcommand -> N1.3 clauses: key plus all (whole clause) or word (semicolon clauses mentioning the command).
KEYS = {
    "recover": [("box", "all")],
    "restore": [("copy", "all"), ("floor", "all"), ("box", "all")],
    "import": [("copy", "all"), ("import", "all"), ("floor", "all"), ("box", "all")],
    "status": [("box", "all")],
    "join": [("repeat", "word"), ("box", "all")],
    "leave": [("repeat", "word"), ("box", "all")],
    "admit": [("repeat", "word"), ("box", "all")],
    "backup": [("copy", "all")],
    "rights": [],
}
# Subcommand -> HTTP door called through admin.sock: norm file, anchor and gen_core.STUBS-style selector.
DOORS = {
    "backup": [(NORMS_13, "P/01.3-R033", None)],
    "status": [(NORMS_13, "P/01.3-R016", "door:GET `/v1/status`")],
    "join": [(NORMS_13, "P/01.3-R016", "door:POST `/v1/join`")],
    "leave": [(NORMS_13, "P/01.3-R016", "door:POST `/v1/leave`")],
    "rights": [(NORMS_12, "P/01.2-R014", None)],
}
# Subcommand -> named forms/refusals.tsv rows.
REFUSAL_ROWS = {
    "recover": ("recover_box", "recover_isolated", "recover_upper", "recover_peers", "recovery_unsafe", "clock_early"),
    "restore": ("copy_input", "clock_early"),
    "import": ("copy_input", "import_repeated", "clock_early"),
    "status": (),
    "join": ("join_parity", "join_left"),
    "leave": ("box_last_voter",),
    "admit": ("box_admit",),
    "backup": ("backup_inside_dir", "copy_method", "copy_admin_only", "copy_snapshot_unavailable"),
    "rights": ("rights_not_loaded",),
}
# Stand-profile own commands: name -> (function, calling directive row in the common README).
OWN = {"spoil-row": ("SpoilRow", "| `@spoil row <key>` / `@spoil row-index <key>` |")}
LINE = gen_core.LINE


class GenError(Exception):
    pass


def go_name(cmd):
    return "".join(w[:1].upper() + w[1:] for w in cmd.split("-"))


def commands():
    """Return subcommands in first-appearance order from daemon-flags.tsv commands, excluding daemon, with their flags."""
    order, flags = [], {}
    try:
        table = tsv_input.read(FLAGS, root=ROOT)
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None
    for need in ("flag", "type", "required", "commands"):
        if need not in table.columns:
            raise GenError(f"{FLAGS.name}: no column {need!r}")
    for _, r in table.rows:
        for cmd in r["commands"].split(","):
            if cmd == "daemon":
                continue
            if cmd not in flags:
                order.append(cmd)
                flags[cmd] = []
            flags[cmd].append((r["flag"], r["type"], r["required"]))
    return order, flags


def block():
    """Read the N1.3 YAML block at BLOCK_ANCHOR as {top-level key: single-line clause text}."""
    text = NORMS_13.read_text(encoding="utf-8")
    m = re.search(r"<!-- req: " + re.escape(BLOCK_ANCHOR) + r" -->\n```yaml\n(.*?)\n```", text, re.S)
    if not m:
        raise GenError(f"{NORMS_13.name}: no yaml block under req {BLOCK_ANCHOR}")
    keys, cur = {}, None
    for line in m[1].split("\n"):
        k = re.match(r"^([a-z_]+):\s*(.*)$", line)
        sub = re.match(r"^  ([a-z_]+):\s+(.*)$", line)     # Label each subclause: floor generation, when, form, issue.
        if k:
            cur = k[1]
            head = re.sub(r"^#\s*(.*)$", r"(\1)", k[2].strip())  # '# platform/epoch_floor {...}' explains the clause.
            keys[cur] = [head] if head else []
        elif sub and cur:
            keys[cur].append(f"; {sub[1]}: {sub[2].strip()}" if keys[cur] else f"{sub[1]}: {sub[2].strip()}")
        elif cur:
            keys[cur].append(line.strip())
    return {k: re.sub(r"\s+;", ";", re.sub(r"\s+", " ", " ".join(v))).strip() for k, v in keys.items()}


def grammar(admin_ops):
    """Parse admin_ops into ({subcommand: grammar}, clauses following the grammar)."""
    m = re.match(r"((?:[a-z]+[^|]*?\|\s*)+rights \[-groups\])\s*(.*)$", admin_ops)
    if not m:
        raise GenError(f"{NORMS_13.name}: admin_ops — no grammar «status | … | rights [-groups]»")
    out = {}
    for alt in (a.strip() for a in m[1].split("|")):
        out[alt.split(" ", 1)[0]] = alt
    return out, m[2]


def mentions(text, cmd):
    """Select semicolon-separated clauses mentioning the subcommand as a word."""
    return [c.strip() for c in text.split(";") if re.search(r"(?<![\w-])" + re.escape(cmd) + r"(?![\w-])", c)]


def anchor_items(path):
    return {a: (h, t) for h, _, items in gen_core.sections(path.read_text(encoding="utf-8")) for a, t in items}


def has_http_copy():
    """The actual API selects the new copy documentation; legacy APIs have no such operation."""
    import gen_door

    try:
        _, doc = gen_door.load(L.openapi)
        return any(op.path == "/v1/copy" for op in gen_door.Spec(doc, str(L.openapi)).ops)
    except (OSError, gen_door.GenError) as exc:
        raise GenError(f"admin API: {exc}") from None


def stub_comment(cmd, gram, rest, keys, cli, recover, flags):
    name = go_name(cmd)
    copy_http = cmd == "backup" and has_http_copy()
    lines = [f'// {name} — the subcommand `configstore {gram}` (P/01.3 N1.3 admin_ops): exit 1 not in this stage until',
             "// your stage needs it; then replace the body (the signature stays: Run calls it). The flags are parsed",
             "// and checked by the form already (a flag out of form — code 2 before Run); f.Args — the positional words.",
             "// By the norms:", f'//   spec/{NORMS_13.name} N1.3 Store (req: {BLOCK_ANCHOR}):']
    lines += gen_core.wrap(f"admin_ops: {gram}", "//     ", "//       ")
    for clause in mentions(rest, cmd):
        lines += gen_core.wrap(f"admin_ops: {clause}", "//     ", "//       ")
    for key, how in KEYS[cmd]:
        if key not in keys:
            raise GenError(f'{NORMS_13.name}: N1.3 has no item {key!r} (gen_admin KEYS {cmd})')
        parts = [keys[key]] if how == "all" else mentions(keys[key], cmd)
        if not parts:
            raise GenError(f'{NORMS_13.name}: N1.3 {key!r} does not name {cmd!r} (gen_admin KEYS)')
        for p in parts:
            lines += gen_core.wrap(f"{key}: {p}", "//     ", "//       ")
    # The YAML is now a compact form; the rules following it retain their own
    # anchors. Include the clauses for the selected key and command, not only
    # the abbreviated form cell.
    for anchor, (_, paragraph) in anchor_items(NORMS_13).items():
        if re.match(r"^`(?:admin_ops|" + "|".join(re.escape(k) for k, _ in KEYS[cmd]) + r")(?:[.` ])", paragraph) and mentions(paragraph, cmd):
            lines += gen_core.wrap(f"req: {anchor} — {gen_core.plain(paragraph)}", "//     ", "//       ")
    said = [s.strip() for s in re.split(r"(?<=\.) ", cli) if re.search(r"`(?:[a-z]+/)?" + re.escape(cmd) + r"\b", s)]
    if said:
        lines.append(f'//   spec/{NORMS_13.name} N2 Doors (the CLI):')
        lines += gen_core.wrap(f"req: {CLI_ANCHOR} — " + gen_core.plain(" ".join(said)), "//     ", "//       ")
    if cmd == "recover":
        lines.append(f'//   spec/{NORMS_13.name} N3 Procedures: «{RECOVER}»:')
        for a, t in recover:                            # Keep the whole procedure: its phases define recover's body.
            if gen_core.plain(t) != "---":
                lines += gen_core.wrap(f"req: {a} — {gen_core.plain(t)}", "//     ", "//       ")
    for path, anchor, sel in DOORS.get(cmd, []):
        if cmd == "backup" and not copy_http:
            continue
        items = anchor_items(path)
        if anchor not in items:
            raise GenError(f"{path.name}: no req anchor {anchor} (gen_admin DOORS {cmd})")
        head, item = items[anchor]
        if sel:
            door = sel[5:]
            rows = re.findall(r"\| " + re.escape(door) + r" \| (.*?) \|(?= \||$)", item)
            if len(rows) != 1:
                raise GenError(f"{path.name}: {anchor} — {len(rows)} rows of the door {door}, want 1")
            item = f"{door}: {rows[0]}"
        lines.append(f"//   the door it calls on admin.sock — spec/{path.name} «{head}»:")
        lines += gen_core.wrap(f"req: {anchor} — {gen_core.plain(item)}", "//     ", "//       ")
    lines.append("//   the flags — forms/daemon-flags.tsv (commands ∋ " + cmd + "; f.<Field> of package flags):")
    lines += [f"//     {fl} {typ}" + ("" if req == "false" else f", required: {req}") for fl, typ, req in flags]
    refusals = REFUSAL_ROWS[cmd]
    if cmd == "backup" and not copy_http:
        refusals = ("backup_inside_dir",)
    if refusals:
        lines.append("//   the refusals — forms/refusals.tsv:")
        try:
            lines += gen_core.refusal_lines(refusals)
        except gen_core.GenError as exc:
            raise GenError(str(exc)) from None
    return lines


ADMIN = r'''// Code generated by tools/normgen/gen_admin.py (kit part admin) from forms/daemon-flags.tsv sha256 {flags_sha}; DO NOT EDIT.

// Package admin implements admin_ops subcommands (P/01.3 N1.3):Run dispatches f.Cmd, one file per
// subcommand ({files}: yours, the kit puts each once); own.go — your own commands of the stand profile, looked up by
// launch.Main before the flags are parsed. launch.Main calls Run when App.Admin is nil.
package admin

import (
	"fmt"
	"io"

	"{module}/flags"
)

// Env — what a subcommand gets besides its flags: the output streams and the environment.
type Env struct {
	Stdout io.Writer
	Stderr io.Writer
	Getenv func(string) string
	Copy CopyOps // optional: box.CopyControl over the actual host store/transport
}

// CopyOps is implemented by box.CopyControl. Connect it in launch.App.Admin's
// ordinary admin.Run environment. The host owns storage and transport. When Source
// declares admin-only HTTP copy, live backup must follow it rather than a private alias.
type CopyOps interface {
    Backup(file string) error
    Import(file string, indexBase uint64, force bool) error
    Restore(file string, force bool) error
}

func runCopy(cmd string, f *flags.Flags, env Env) int {
    log := env.Stderr
    if log == nil { log = io.Discard }
    want := 0
    if cmd == "backup" { want = 1 }
    if len(f.Args) != want {
        fmt.Fprintf(log, "configstore %s: want %d positional arguments\n", cmd, want)
        return 2
    }
    var err error
    switch cmd {
    case "backup": err = env.Copy.Backup(f.Args[0])
    case "import": err = env.Copy.Import(f.From, uint64(f.IndexBase), f.Force)
    case "restore": err = env.Copy.Restore(f.From, f.Force)
    }
    if err != nil {
        fmt.Fprintf(log, "configstore %s: %v\n", cmd, err)
        return 1
    }
    return 0
}

// NotInStageCode — the exit code of a subcommand without an implementation. Not 2: 2 is the start refusal of the flag
// form (P/01.3 N4), checked by launch before Run.
const NotInStageCode = 1

// NotInStage — «configstore <cmd>: not in this stage» on Stderr, exit NotInStageCode: the body of a subcommand
// before your stage writes it.
func NotInStage(cmd string, env Env) int {
	fmt.Fprintf(env.Stderr, "configstore %s: not in this stage\n", cmd)
	return NotInStageCode
}

// Run — the subcommand f.Cmd (flags.Commands except daemon) → your function; the flags are checked by the form already.
func Run(f *flags.Flags, env Env) int {
	switch f.Cmd {
{cases}
	}
	fmt.Fprintf(env.Stderr, "configstore %s: not a subcommand of admin_ops\n", f.Cmd)
	return 2
}
'''

STUB_HEAD = '''// Generated by tools/normgen/gen_admin.py (kit part admin). YOURS from here: the kit puts this file once and never
// overwrites it. One subcommand per file: this file is `{cmd}` only (the dispatch — admin.go, closed).

package admin

import "{module}/flags"

'''

OWN_GO = '''// Generated by tools/normgen/gen_admin.py (kit part admin). YOURS from here: the kit puts this file once and never
// overwrites it.

package admin

// Own — your own commands of the stand profile (acceptance.yaml «stand»: the commands the runner calls by name, such
// as spoil-row): launch.Main looks args[0] up here before the flags are parsed and gives the rest of the command line
// as is (parse it yourself). Only commands of the profile go here — never a flag of forms/daemon-flags.tsv and never
// a subcommand of admin_ops (those are Run's, one file each). Remove an entry your profile does not name.
var Own = map[string]func(args []string, env Env) int{
{entries}
}

{funcs}'''


def render():
    """Return ({go/-relative path: text}, [(subcommand, comment line count)])."""
    try:
        lesson.require(L, "gen_admin (KEYS, DOORS, REFUSAL_ROWS, OWN)")
    except lesson.LessonError as exc:
        raise GenError(str(exc)) from None
    for p in (NORMS_13, NORMS_12, NORMS_11, FLAGS, REFUSALS, COMMON):
        if not p.is_file():
            raise GenError(f"no {p}")
    cmds, flags = commands()
    keys = block()
    if "admin_ops" not in keys:
        raise GenError(f'{NORMS_13.name}: N1.3 has no admin_ops')
    gram, rest = grammar(keys["admin_ops"])
    if set(gram) != set(cmds):
        raise GenError(f"admin_ops grammar {sorted(gram)} != daemon-flags.tsv commands {sorted(cmds)}")
    for table, name in ((KEYS, "KEYS"), (REFUSAL_ROWS, "REFUSAL_ROWS")):
        if set(table) != set(cmds):
            raise GenError(f"gen_admin {name} {sorted(table)} != the subcommands {sorted(cmds)}")
    items = anchor_items(NORMS_13)
    if CLI_ANCHOR not in items:
        raise GenError(f"{NORMS_13.name}: no req anchor {CLI_ANCHOR}")
    cli = items[CLI_ANCHOR][1]
    rec = [s for s in gen_core.sections(NORMS_13.read_text(encoding="utf-8")) if s[0] == RECOVER]
    if len(rec) != 1 or not rec[0][2]:
        raise GenError(f'{NORMS_13.name}: N3 {RECOVER}» — {len(rec)} found or no req anchors')
    files, report = {}, []
    for cmd in cmds:
        if go_name(cmd) in ("Run", "NotInStage", "Env", "Own", "CopyOps"):
            raise GenError(f"subcommand {cmd!r}: its Go name clashes with admin.go")
        doc = stub_comment(cmd, gram[cmd], rest, keys, cli, rec[0][2], flags[cmd])
        delegate = (f'\tif env.Copy != nil {{ return runCopy("{cmd}", f, env) }}\n'
                    if cmd in ("backup", "import", "restore") else "")
        body = (STUB_HEAD.replace("{cmd}", cmd).replace("{module}", GO_MODULE) + "\n".join(doc)
                + f"\nfunc {go_name(cmd)}(f *flags.Flags, env Env) int {{\n{delegate}\treturn NotInStage({cmd!r}, env)\n}}\n"
                .replace("'", '"'))
        files[f"admin/{cmd}.go"] = gen_core.gofmt(body)
        report.append((cmd, len(doc)))
    common = COMMON.read_text(encoding="utf-8")
    entries, funcs = [], []
    for cmd, (fn, row) in OWN.items():
        labels = (row, row.replace("<key>", '<\u043a\u043b\u044e\u0447>'))
        line = next((ln for ln in common.split("\n") if ln.startswith(labels)), None)
        if line is None:
            raise GenError(f"{COMMON.relative_to(ROOT)}: no directive row {row!r} (gen_admin OWN {cmd})")
        what = gen_core.plain(line.split(" | ", 2)[1])
        entries.append(f'\t"{cmd}": {fn},')
        funcs.append("\n".join(
            [f"// {fn} — the stand command `{cmd}` of your profile: the runner calls it by the directive of",
             f"// {COMMON.relative_to(ROOT.joinpath('Platform'))} (the store stopped; your profile writes its arguments):"]
            + gen_core.wrap(what, "//   ", "//     ")
            + [f"func {fn}(args []string, env Env) int {{", f'\treturn NotInStage("{cmd}", env)', "}", ""]))
    files["admin/own.go"] = gen_core.gofmt(OWN_GO.replace("{entries}", "\n".join(entries)).replace("{funcs}", "\n".join(funcs)))
    cases = "\n".join(f'\tcase "{c}":\n\t\treturn {go_name(c)}(f, env)' for c in cmds)
    names = ", ".join(f"{c}.go" for c in cmds)
    files["admin/admin.go"] = gen_core.gofmt(ADMIN.replace("{flags_sha}", gen_core.sha(FLAGS)).replace("{module}", GO_MODULE)
                                             .replace("{cases}", cases).replace("{files}", names))
    return files, report




def own(rel):
    return rel != "admin/admin.go"


def generate(out=DEFAULT_OUT):
    gdir = Path(out) / "go"
    files, report = render()
    for rel, text in files.items():
        (gdir / rel).parent.mkdir(parents=True, exist_ok=True)
        (gdir / rel).write_text(text, encoding="utf-8")
    return gdir, report


def kit_files(module, out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source, editable)]; stale output raises GenError."""
    files = []
    for rel, text in sorted(render()[0].items()):
        kept = Path(out) / "go" / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_admin.py")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel.rsplit("/", 1)
        files.append((sub, name, data, "generated", L.output_source(kept, out), own(rel)))
    return files


def provenance():
    """Part provenance (ADR-0125 addendum (1), item 6(a)): forms, generator, no handwritten runtime, and judge."""
    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": gen_core.sha(path)}
    paths = [p for src in (FLAGS, NORMS_13, NORMS_12, REFUSALS, COMMON, L.openapi) for p in
             (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])]
    return {"form": [entry(p) for p in dict.fromkeys(paths)], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__)),
                           entry(HERE / "gen_door.py"), entry(HERE / "yamlsub.py")],
            "handwritten": [], "judge": entry(JUDGE)}


KIT_MD = """
## Part `admin`: the subcommands of admin_ops (generated, the files of subcommands are **yours**)

| File | Origin |
|---|---|
| `{module}/internal/admin/admin.go` | kit (closed): `Env`, `Run`, `NotInStage` — the dispatch of `f.Cmd` |
| `{module}/internal/admin/<subcommand>.go` | **yours**: one subcommand per file — the body to write, the anchors above it |
| `{module}/internal/admin/own.go` | **yours**: `Own` — the commands of your stand profile (`spoil-row` …) |

**Subcommands.** `configstore <subcommand> [flags] [words]` (P/01.3 N1.3 `admin_ops`): `launch.Main` parses the flags by
`forms/daemon-flags.tsv` first (a flag out of form, a flag of another command, a wrong positional word — code 2, your
code is not called), then — when `App.Admin` is nil, as in the generated `main.go` — `admin.Run(f, env)` calls your
function of `f.Cmd`. Until you write it, it answers `configstore <subcommand>: not in this stage` on stderr, exit 1.

```go
type Env struct { Stdout, Stderr io.Writer; Getenv func(string) string }
func Run(f *flags.Flags, env Env) int           // closed: f.Cmd → your function below
func NotInStage(cmd string, env Env) int        // stderr «configstore <cmd>: not in this stage», exit 1
const NotInStageCode = 1
{signatures}
var Own map[string]func(args []string, env Env) int   // own.go: your stand commands, before the flags are parsed
```

The flags are fields of `*flags.Flags` (`f.Dir`, `f.Sockets`, …; `f.Given["-force"]` — given on the line), the positional
words — `f.Args` (`admit <id>`, `backup <file>`, `leave [id]`). A subcommand that talks to a live daemon (status, join,
leave, admit, backup, rights; restore and import in a group) speaks HTTP to `<-sockets>/admin.sock`; restore and import
on a box, and recover, work on the directory of a stopped daemon (the anchors above each function say which). Edit one
file per subcommand; never delete a function (`Run` calls it).

**`own.go` — only the commands of your stand profile** (the `stand` keys of `acceptance.yaml` the runner calls by name,
such as `spoil-row` for `@spoil row`): `launch.Main` looks `args[0]` up in `Own` before parsing the flags and gives the
rest of the line as is. Never put a flag of `daemon-flags.tsv` or a subcommand of admin_ops there.
"""


def kit_md():
    cmds, _ = commands()
    sig = "\n".join(f"func {go_name(c)}(f *flags.Flags, env Env) int{' ' * (14 - len(go_name(c)))}// {c}.go — yours"
                    for c in cmds)
    return KIT_MD.replace("{signatures}", sig)


def main(argv):
    out = argv[1] if len(argv) > 1 else DEFAULT_OUT
    try:
        gdir, report = generate(out)
    except (GenError, gen_core.GenError) as exc:
        print(f"gen_admin: {exc}", file=sys.stderr)
        return 1
    print(gdir, " ".join(f"{c}:{n}" for c, n in report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
