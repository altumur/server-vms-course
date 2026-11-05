"""Генератор части пакета `admin` (Архитектор 2026-11-05: MiniMax 30–32 на daemon_box не находит, куда писать
backup/import): подкоманды admin_ops P/01.3 Н1.3 — закрытый диспетчер и по YOURS-заготовке на подкоманду.

Запуск: python3 tools/normgen/gen_admin.py [<out>]   (по умолчанию tools/normgen/out/p01-1)

Выход <out>/go/admin (пакет admin модуля out/go):
- admin.go — закрыт (DO NOT EDIT): Env, Run(f, env) — по f.Cmd вызывает функцию подкоманды, NotInStage(cmd, env) —
  «configstore <cmd>: not in this stage», exit 1 (не 2: 2 — отказ формы флагов, его даёт launch до Run);
- <подкоманда>.go — YOURS, пакет кладёт один раз (как coreadapter/<метод>.go; --seed бережёт): func <Имя>(f *flags.Flags,
  env Env) int с телом NotInStage; над функцией — места норм: грамматика подкоманды и оговорки admin_ops (Н1.3), пункты
  блока Н1.3 по таблице KEYS (copy, import, floor, box, repeat), предложения P/01.3-R018 о подкоманде, процедура Н3
  «recover» (recover), дверь HTTP таблицы P/01.3-R016 или P/01.2 Н2 (status, join, leave, rights), флаги daemon-flags.tsv
  с колонкой commands ∋ подкоманда, строки refusals.tsv по таблице REFUSALS;
- own.go — YOURS: Own — карта своих команд профиля стенда (spoil-row …), launch.Main смотрит её до разбора флагов.
Список подкоманд — колонка commands формы daemon-flags.tsv (кроме daemon); он должен совпасть с грамматикой admin_ops
норм и с таблицами генератора — иначе отказ генератора. Подключение — в закрытом launch: App.Admin nil → admin.Run.
Судья — admin_judge.py (подкоманда без реализации → «not in this stage» exit 1; флаг не по форме → 2) и test_gen_admin.py.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_core  # noqa: E402 — разбор норм, обёртка комментария, строки refusals.tsv
import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
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
BLOCK_ANCHOR = "P/01.3-R006"            # Н1.3 Store — блок yaml: daemon, copy, …, admin_ops, floor, import, box, repeat
CLI_ANCHOR = "P/01.3-R018"              # CLI backup, restore/import, recover, admit
RECOVER = "recover the store (no majority)"

# Подкоманда → пункты блока Н1.3: (ключ, "all" — пункт целиком | "word" — только оговорки (через «;»), где названа подкоманда).
KEYS = {
    "recover": [("box", "word")],
    "restore": [("copy", "all"), ("floor", "all"), ("box", "word")],
    "import": [("copy", "all"), ("import", "all"), ("floor", "all"), ("box", "word")],
    "status": [("box", "word")],
    "join": [("repeat", "word"), ("box", "word")],
    "leave": [("repeat", "word"), ("box", "word")],
    "admit": [("repeat", "word"), ("box", "word")],
    "backup": [("copy", "all")],
    "rights": [],
}
# Подкоманда → дверь HTTP, к которой она обращается через admin.sock: (файл норм, якорь, отбор как gen_core.STUBS).
DOORS = {
    "status": [(NORMS_13, "P/01.3-R016", "door:GET `/v1/status`")],
    "join": [(NORMS_13, "P/01.3-R016", "door:POST `/v1/join`")],
    "leave": [(NORMS_13, "P/01.3-R016", "door:POST `/v1/leave`")],
    "rights": [(NORMS_12, "P/01.2-R014", None)],
}
# Подкоманда → строки forms/refusals.tsv (по имени).
REFUSAL_ROWS = {
    "recover": ("recover_box", "recover_isolated", "recover_upper", "recover_peers", "recovery_unsafe", "clock_early"),
    "restore": ("copy_input", "clock_early"),
    "import": ("copy_input", "import_repeated", "clock_early"),
    "status": (),
    "join": ("join_parity", "join_left"),
    "leave": ("box_last_voter",),
    "admit": ("box_admit",),
    "backup": ("backup_inside_dir",),
    "rights": ("rights_not_loaded",),
}
# Свои команды профиля стенда: имя → (функция, строка таблицы директив общего README, которая её зовёт).
OWN = {"spoil-row": ("SpoilRow", "| `@spoil row <ключ>` / `@spoil row-index <ключ>` |")}
LINE = gen_core.LINE


class GenError(Exception):
    pass


def go_name(cmd):
    return "".join(w[:1].upper() + w[1:] for w in cmd.split("-"))


def commands():
    """Подкоманды формы daemon-flags.tsv по порядку появления в колонке commands (кроме daemon) и флаги каждой."""
    order, flags = [], {}
    rows = [line.split("\t") for line in FLAGS.read_text(encoding="utf-8").split("\n") if line and not line.startswith("#")]
    head, rows = rows[0], rows[1:]
    col = {name: i for i, name in enumerate(head)}
    for need in ("flag", "type", "required", "commands"):
        if need not in col:
            raise GenError(f"{FLAGS.name}: no column {need!r}")
    for r in rows:
        for cmd in r[col["commands"]].split(","):
            if cmd == "daemon":
                continue
            if cmd not in flags:
                order.append(cmd)
                flags[cmd] = []
            flags[cmd].append((r[col["flag"]], r[col["type"]], r[col["required"]]))
    return order, flags


def block():
    """Блок yaml Н1.3 (якорь BLOCK_ANCHOR) → {ключ верхнего уровня: текст пункта одной строкой}."""
    text = NORMS_13.read_text(encoding="utf-8")
    m = re.search(r"<!-- req: " + re.escape(BLOCK_ANCHOR) + r" -->\n```yaml\n(.*?)\n```", text, re.S)
    if not m:
        raise GenError(f"{NORMS_13.name}: no yaml block under req {BLOCK_ANCHOR}")
    keys, cur = {}, None
    for line in m[1].split("\n"):
        k = re.match(r"^([a-z_]+):\s*(.*)$", line)
        sub = re.match(r"^  ([a-z_]+):\s+(.*)$", line)     # подпункт (floor: generation, when, form, issue) — с меткой
        if k:
            cur = k[1]
            head = re.sub(r"^#\s*(.*)$", r"(\1)", k[2].strip())  # «# platform/epoch_floor {…}» — пояснение пункта
            keys[cur] = [head] if head else []
        elif sub and cur:
            keys[cur].append(f"; {sub[1]}: {sub[2].strip()}" if keys[cur] else f"{sub[1]}: {sub[2].strip()}")
        elif cur:
            keys[cur].append(line.strip())
    return {k: re.sub(r"\s+;", ";", re.sub(r"\s+", " ", " ".join(v))).strip() for k, v in keys.items()}


def grammar(admin_ops):
    """admin_ops → ({подкоманда: её грамматика}, оговорки после грамматики)."""
    m = re.match(r"((?:[a-z]+[^|]*?\|\s*)+rights \[-groups\])\s*(.*)$", admin_ops)
    if not m:
        raise GenError(f"{NORMS_13.name}: admin_ops — no grammar «status | … | rights [-groups]»")
    out = {}
    for alt in (a.strip() for a in m[1].split("|")):
        out[alt.split(" ", 1)[0]] = alt
    return out, m[2]


def mentions(text, cmd):
    """Оговорки текста (через «;»), где подкоманда названа словом."""
    return [c.strip() for c in text.split(";") if re.search(r"(?<![\w-])" + re.escape(cmd) + r"(?![\w-])", c)]


def anchor_items(path):
    return {a: (h, t) for h, _, items in gen_core.sections(path.read_text(encoding="utf-8")) for a, t in items}


def stub_comment(cmd, gram, rest, keys, cli, recover, flags):
    name = go_name(cmd)
    lines = [f"// {name} — the subcommand `configstore {gram}` (P/01.3 Н1.3 admin_ops): exit 1 «not in this stage» until",
             "// your stage needs it; then replace the body (the signature stays: Run calls it). The flags are parsed",
             "// and checked by the form already (a flag out of form — code 2 before Run); f.Args — the positional words.",
             "// By the norms:", f"//   spec/{NORMS_13.name} «Н1.3 Store» (req: {BLOCK_ANCHOR}):"]
    lines += gen_core.wrap(f"admin_ops: {gram}", "//     ", "//       ")
    for clause in mentions(rest, cmd):
        lines += gen_core.wrap(f"admin_ops: {clause}", "//     ", "//       ")
    for key, how in KEYS[cmd]:
        if key not in keys:
            raise GenError(f"{NORMS_13.name}: Н1.3 has no item {key!r} (gen_admin KEYS {cmd})")
        parts = [keys[key]] if how == "all" else mentions(keys[key], cmd)
        if not parts:
            raise GenError(f"{NORMS_13.name}: Н1.3 {key!r} does not name {cmd!r} (gen_admin KEYS)")
        for p in parts:
            lines += gen_core.wrap(f"{key}: {p}", "//     ", "//       ")
    said = [s.strip() for s in re.split(r"(?<=\.) ", cli) if re.search(r"`(?:[a-z]+/)?" + re.escape(cmd) + r"\b", s)]
    if said:
        lines.append(f"//   spec/{NORMS_13.name} «Н2 Doors» (the CLI):")
        lines += gen_core.wrap(f"req: {CLI_ANCHOR} — " + gen_core.plain(" ".join(said)), "//     ", "//       ")
    if cmd == "recover":
        lines.append(f"//   spec/{NORMS_13.name} «Н3 Procedures» «{RECOVER}»:")
        for a, t in recover:                            # процедура целиком: её фазы и есть тело recover
            if gen_core.plain(t) != "---":
                lines += gen_core.wrap(f"req: {a} — {gen_core.plain(t)}", "//     ", "//       ")
    for path, anchor, sel in DOORS.get(cmd, []):
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
    if REFUSAL_ROWS[cmd]:
        lines.append("//   the refusals — forms/refusals.tsv:")
        try:
            lines += gen_core.refusal_lines(REFUSAL_ROWS[cmd])
        except gen_core.GenError as exc:
            raise GenError(str(exc)) from None
    return lines


ADMIN = '''// Code generated by tools/normgen/gen_admin.py (kit part admin) from forms/daemon-flags.tsv sha256 {flags_sha}; DO NOT EDIT.

// Package admin — the subcommands of admin_ops (P/01.3 Н1.3): Run calls your function of f.Cmd — one file per
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
// ordinary admin.Run environment. No storage format or socket protocol is assumed.
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
        fmt.Fprintf(log, "configstore %s: want %d positional arguments\\n", cmd, want)
        return 2
    }
    var err error
    switch cmd {
    case "backup": err = env.Copy.Backup(f.Args[0])
    case "import": err = env.Copy.Import(f.From, uint64(f.IndexBase), f.Force)
    case "restore": err = env.Copy.Restore(f.From, f.Force)
    }
    if err != nil {
        fmt.Fprintf(log, "configstore %s: %v\\n", cmd, err)
        return 1
    }
    return 0
}

// NotInStageCode — the exit code of a subcommand without an implementation. Not 2: 2 is the start refusal of the flag
// form (P/01.3 Н4), launch gives it before Run.
const NotInStageCode = 1

// NotInStage — «configstore <cmd>: not in this stage» on Stderr, exit NotInStageCode: the body of a subcommand
// before your stage writes it.
func NotInStage(cmd string, env Env) int {
	fmt.Fprintf(env.Stderr, "configstore %s: not in this stage\\n", cmd)
	return NotInStageCode
}

// Run — the subcommand f.Cmd (flags.Commands except daemon) → your function; the flags are checked by the form already.
func Run(f *flags.Flags, env Env) int {
	switch f.Cmd {
{cases}
	}
	fmt.Fprintf(env.Stderr, "configstore %s: not a subcommand of admin_ops\\n", f.Cmd)
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
    """→ ({путь от go/: текст}, [(подкоманда, число строк комментария)])."""
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
        raise GenError(f"{NORMS_13.name}: Н1.3 has no admin_ops")
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
        raise GenError(f"{NORMS_13.name}: Н3 «{RECOVER}» — {len(rec)} found or no req anchors")
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
        line = next((ln for ln in common.split("\n") if ln.startswith(row)), None)
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
    """→ [(каталог в internal, имя, байты, происхождение, источник, своё у реализации)]; GenError — out устарел."""
    files = []
    for rel, text in sorted(render()[0].items()):
        kept = Path(out) / "go" / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_admin.py")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel.rsplit("/", 1)
        files.append((sub, name, data, "generated", str(kept.relative_to(ROOT)), own(rel)))
    return files


def provenance():
    """Паспорт части (ADR-0125 доп. (1) п. 6 (а)): формы, генератор, ручная среда (нет), судья."""
    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": gen_core.sha(path)}
    return {"form": [entry(p) for p in (FLAGS, NORMS_13, NORMS_12, REFUSALS, COMMON)],
            "generator": entry(Path(__file__).resolve()), "handwritten": [], "judge": entry(JUDGE)}


KIT_MD = """
## Part `admin`: the subcommands of admin_ops (generated, the files of subcommands are **yours**)

| File | Origin |
|---|---|
| `{module}/internal/admin/admin.go` | kit (closed): `Env`, `Run`, `NotInStage` — the dispatch of `f.Cmd` |
| `{module}/internal/admin/<subcommand>.go` | **yours**: one subcommand per file — the body to write, the anchors above it |
| `{module}/internal/admin/own.go` | **yours**: `Own` — the commands of your stand profile (`spoil-row` …) |

**Subcommands.** `configstore <subcommand> [flags] [words]` (P/01.3 Н1.3 `admin_ops`): `launch.Main` parses the flags by
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
