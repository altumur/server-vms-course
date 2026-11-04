"""Генератор № 3 ADR-0125: разбор флагов демона хранилища из `Platform/01-store/forms/daemon-flags.tsv` — без модели.

Читает таблицу (шапка `#var f`, `#var cmd`, `#fn`; колонки flag type default default_text required commands bad norm)
и строит пакет Go 1.22 только на стандартной библиотеке `<out>/go/flags/`:
- `flags.go` — построен по таблице: структура Flags (поле на флаг), Command, Parse, ParseArgs, Refusal;
- `flagtypes.go` — копия ручного словаря типов `tools/normgen/flags/go/flagtypes.go` (закрытый словарь шапки);
- `runtime.go`, `prims.go` — копии среды CEL и примитивов генератора № 1 (`required`, `bad` — CEL; `loopback` — примитив).

Генератор не читает прозу (ADR-0125 доп. (1) п. 4): позиционные слова подкоманд (`admit <id>`, `backup <file>`) — не
форма, Parse отдаёт их в Args как есть. Семантика разбора — в KIT_MD ниже (раздел KIT.md части `flags`).

Запуск: python tools/normgen/gen_flags.py [таблица.tsv [каталог_выхода]].
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import (FN_TYPES, GenError, Module, Parser, compile_expr, go_fn_wrapper,  # noqa: E402
                        go_function, go_str, gofmt, prims_present, camel)

DEFAULT_TABLE = ROOT / "Platform/01-store/forms/daemon-flags.tsv"
DEFAULT_OUT = HERE / "out/p01-1"
COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
FLAG = re.compile(r"-[a-z][a-z-]*|--[a-z][a-z-]*")
TYPE = re.compile(r"path|dir|file|addr|id|bool|duration|bytes:>0|list:id@addr(?:/addr)?"
                  r"|enum:[A-Za-z0-9_.-]+(?:\|[A-Za-z0-9_.-]+)*|int:(-?[0-9]+)\.\.(-?[0-9]*)")
INITIALISMS = {"id": "ID", "api": "API", "tls": "TLS"}
DURATION = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?(?:ns|us|µs|ms|s|m|h))+")
DURATION_NS = {"ns": 1, "us": 1000, "µs": 1000, "ms": 10 ** 6, "s": 10 ** 9, "m": 60 * 10 ** 9, "h": 3600 * 10 ** 9}
MEMBER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
INT64 = (-2 ** 63, 2 ** 63 - 1)


# ---------------------------------------------------------------- таблица

class Table:
    def __init__(self, text, name="daemon-flags.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.vars, self.fns, self.lims, self.rows = {}, {}, [], []
        lines = text.splitlines()
        for line in lines:
            if m := re.match(r"#var (\w+) (\S+) — ", line):
                self.vars[m[1]] = m[2]
            elif m := re.match(r"#fn ([a-z_]+)\(([^)]*)\) -> (\w+) — (.*)", line):
                args = [a.strip() for a in m[2].split(",") if a.strip()]
                for t in args + [m[3]]:
                    if t not in FN_TYPES:
                        raise GenError(f"{name}: #fn {m[1]}: type {t!r} — one of {sorted(FN_TYPES)}")
                self.fns[m[1]] = (args, m[3], m[4])
            elif re.match(r"#(var|lim|fn) ", line):
                raise GenError(f"{name}: header line out of form: {line}")
        if set(self.vars) != {"f", "cmd"}:
            raise GenError(f"{name}: #var must declare f and cmd (got {sorted(self.vars)})")
        body = [line for line in lines if not line.startswith("#")]
        if not body or body[0].split("\t") != COLUMNS:
            raise GenError(f"{name}: columns must be {COLUMNS}")
        seen, fields = set(), set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                raise GenError(f"{name}: row {k}: {len(cells)} cells, expected {len(COLUMNS)}")
            row = dict(zip(COLUMNS, cells))
            where = f"{name}: {row['flag']}"
            if not FLAG.fullmatch(row["flag"]) or row["flag"] in seen:
                raise GenError(f"{where}: the flag is not -name (--name) or repeats")
            seen.add(row["flag"])
            if not TYPE.fullmatch(row["type"]):
                raise GenError(f"{where}: type {row['type']!r} is not of the closed vocabulary")
            row["commands"] = row["commands"].split(",")
            if not all(re.fullmatch(r"[a-z]+", c) for c in row["commands"]) or \
                    len(set(row["commands"])) != len(row["commands"]):
                raise GenError(f"{where}: commands {row['commands']} — a comma list of names without repeats")
            if not row["required"]:
                raise GenError(f"{where}: required is empty (true, false or CEL)")
            row["field"] = field_name(row["flag"])
            if row["field"] in fields or row["field"] in ("Cmd", "Given", "Args"):
                raise GenError(f"{where}: the field name {row['field']} repeats")
            fields.add(row["field"])
            row["default_go"] = default_value(row, where)
            self.rows.append(row)
        by_flag = {r["flag"]: r for r in self.rows}
        for row in self.rows:
            if row["default"].startswith("="):
                other = by_flag.get(row["default"][1:])
                if not other or other["type"] != row["type"] or not set(row["commands"]) <= set(other["commands"]):
                    raise GenError(f"{self.name}: {row['flag']}: default {row['default']} — a flag of the same type "
                                   f"admitted at every command of this one")
        self.commands = []
        for row in self.rows:
            for c in row["commands"]:
                if c not in self.commands:
                    self.commands.append(c)
        if "daemon" not in self.commands:
            raise GenError(f"{self.name}: no flag of the command daemon")
        self.commands.remove("daemon")
        self.commands.insert(0, "daemon")


def field_name(flag):
    return "".join(INITIALISMS.get(p, p[:1].upper() + p[1:]) for p in flag.lstrip("-").split("-"))


def duration_ns(text):
    total = 0
    for num, unit in re.findall(r"([0-9]+(?:\.[0-9]+)?)(ns|us|µs|ms|s|m|h)", text):
        total += round(float(num) * DURATION_NS[unit])
    return total


def check_int(text, lo, hi):
    body = text[1:] if text.startswith("-") else text
    if not body.isdigit() or not body.isascii() or (len(body) > 1 and body[0] == "0"):
        return None
    n = int(text)
    return n if lo <= n <= hi and INT64[0] <= n <= INT64[1] else None


def default_value(row, where):
    """Умолчание как выражение Go для поля (None — нет умолчания или оно вычисляется при разборе: =флаг, $ПЕРЕМЕННАЯ)."""
    d, t = row["default"], row["type"]
    if d == "-" or d.startswith("="):
        return None
    if d.startswith("$"):
        if not re.fullmatch(r"\$[A-Z][A-Z0-9_]*", d):
            raise GenError(f"{where}: default {d!r} — $NAME of an environment variable")
        if t not in ("id", "path", "dir", "file", "addr"):
            raise GenError(f"{where}: default {d} from the environment for type {t}")
        return None
    bad = GenError(f"{where}: default {d!r} is not of type {t}")
    if t == "bool":
        if d != "false":
            raise bad
        return None
    if t in ("path", "dir", "file"):
        if not d:
            raise bad
        return go_str(d)
    if t == "id":
        if not MEMBER_ID.fullmatch(d):
            raise bad
        return go_str(d)
    if t == "duration":
        if not DURATION.fullmatch(d):
            raise bad
        return f"time.Duration({duration_ns(d)}) // {d}"
    if t == "bytes:>0":
        n = check_int(d, 1, INT64[1])
        if n is None:
            raise bad
        return f"int64({n})"
    if t.startswith("int:"):
        lo, hi = re.fullmatch(r"int:(-?[0-9]+)\.\.(-?[0-9]*)", t).groups()
        n = check_int(d, int(lo), int(hi) if hi else INT64[1])
        if n is None:
            raise bad
        return f"int64({n})"
    if t.startswith("enum:"):
        values = t[5:].split("|")
        if d not in values:
            raise bad
        return f"int64({d})" if enum_ints(t) else go_str(d)
    raise GenError(f"{where}: type {t} has no default form ({d!r})")


def enum_ints(t):
    return all(re.fullmatch(r"-?(0|[1-9][0-9]*)", v) for v in t[5:].split("|"))


def go_field_type(t):
    if t == "bool":
        return "bool"
    if t in ("bytes:>0",) or t.startswith("int:") or (t.startswith("enum:") and enum_ints(t)):
        return "int64"
    if t == "duration":
        return "time.Duration"
    if t.startswith("list:"):
        return "[]Member"
    return "string"


# ---------------------------------------------------------------- вывод: Go

def go_assign(row):
    """Операторы case флага: raw — слово значения; поле и f[name]."""
    t, fld = row["type"], f"fl.{row['field']}"
    if t in ("path", "dir", "file"):
        return [f"v, err := valNonEmpty(raw)", "if err != nil {", "\treturn nil, refuse(name, err.Error())", "}",
                f"{fld} = v", "f[name] = v"]
    if t in ("addr", "id"):
        fn = "valAddr" if t == "addr" else "valID"
        return [f"v, err := {fn}(raw)", "if err != nil {", "\treturn nil, refuse(name, err.Error())", "}",
                f"{fld} = v", "f[name] = v"]
    if t == "duration":
        return ["v, err := valDuration(raw)", "if err != nil {", "\treturn nil, refuse(name, err.Error())", "}",
                f"{fld} = v", "f[name] = raw"]
    if t == "bytes:>0":
        return ["v, err := valBytes(raw)", "if err != nil {", "\treturn nil, refuse(name, err.Error())", "}",
                f"{fld} = v", "f[name] = v"]
    if t.startswith("int:"):
        lo, hi = re.fullmatch(r"int:(-?[0-9]+)\.\.(-?[0-9]*)", t).groups()
        return [f"v, err := valInt(raw, {lo}, {hi or 0}, {'true' if hi else 'false'})", "if err != nil {",
                "\treturn nil, refuse(name, err.Error())", "}", f"{fld} = v", "f[name] = v"]
    if t.startswith("enum:"):
        values = "[]string{" + ", ".join(go_str(v) for v in t[5:].split("|")) + "}"
        ints = enum_ints(t)
        return [f"v, err := valEnum(raw, {values}, {'true' if ints else 'false'})", "if err != nil {",
                "\treturn nil, refuse(name, err.Error())", "}",
                f"{fld} = v.({'int64' if ints else 'string'})", "f[name] = v"]
    if t.startswith("list:"):
        addrs = 2 if t.endswith("/addr") else 1
        return [f"v, err := valList(raw, {addrs})", "if err != nil {", "\treturn nil, refuse(name, err.Error())",
                "}", f"{fld} = v", "f[name] = raw"]
    raise AssertionError(t)


def admits(row):
    return " || ".join(f"cmd == {go_str(c)}" for c in row["commands"])


def go_parse(table):
    out = ["func Parse(cmd string, args []string, getenv func(string) string) (*Flags, *Refusal) {",
           "\tif !isCommand(cmd) {",
           "\t\treturn nil, refuse(cmd, \"not a command (daemon or a subcommand of the table)\")",
           "\t}",
           "\tif getenv == nil {",
           "\t\tgetenv = os.Getenv",
           "\t}",
           "\tfl := &Flags{Cmd: cmd, Given: map[string]bool{}}",
           "\tf := map[string]any{}",
           "\tfor k := 0; k < len(args); k++ {",
           "\t\ttok := args[k]",
           "\t\tif tok == \"--\" {",
           "\t\t\tfl.Args = append(fl.Args, args[k+1:]...)",
           "\t\t\tbreak",
           "\t\t}",
           "\t\tif len(tok) < 2 || tok[0] != '-' {",
           "\t\t\tfl.Args = append(fl.Args, tok)",
           "\t\t\tcontinue",
           "\t\t}",
           "\t\tname, raw, eq := strings.Cut(tok, \"=\")",
           "\t\tif fl.Given[name] {",
           "\t\t\treturn nil, refuse(name, \"the flag is repeated\")",
           "\t\t}",
           "\t\tswitch name {"]
    for row in table.rows:
        out += [f"\t\tcase {go_str(row['flag'])}: // {row['type']}",
                f"\t\t\tif !({admits(row)}) {{",
                f"\t\t\t\treturn nil, refuse(name, \"not a flag of the command \"+cmd)",
                "\t\t\t}"]
        if row["type"] == "bool":
            out += ["\t\t\tif eq {", "\t\t\t\treturn nil, refuse(name, \"the flag takes no value\")", "\t\t\t}",
                    f"\t\t\tfl.{row['field']} = true", "\t\t\tf[name] = true"]
        else:
            out += ["\t\t\tif !eq {", "\t\t\t\tif k+1 >= len(args) {",
                    "\t\t\t\t\treturn nil, refuse(name, \"no value\")", "\t\t\t\t}",
                    "\t\t\t\tk++", "\t\t\t\traw = args[k]", "\t\t\t}"]
            out += [f"\t\t\t{s}" for s in go_assign(row)]
    out += ["\t\tdefault:",
            "\t\t\treturn nil, refuse(name, \"not a flag of the table «Daemon flags»\")",
            "\t\t}",
            "\t\tfl.Given[name] = true",
            "\t}",
            "\te := &env{f: f, cmd: cmd}",
            "\t_ = e // a table without CEL in required and bad does not read it"]
    for k, row in enumerate(table.rows, 1):
        if row["required"] == "false":
            continue
        test = "" if row["required"] == "true" else f" && isTrue(required{k}(e))"
        out += [f"\tif ({admits(row)}) && !fl.Given[{go_str(row['flag'])}]{test} {{",
                f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('the flag is required: ' + row['required'])})",
                "\t}"]
    for k, row in enumerate(table.rows, 1):
        if row["bad"]:
            out += [f"\tif fl.Given[{go_str(row['flag'])}] && isTrue(bad{k}(e)) {{",
                    f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('a start refusal: ' + row['bad'])})",
                    "\t}"]
    for row in table.rows:
        flag, fld = go_str(row["flag"]), f"fl.{row['field']}"
        if row["default_go"] is not None:
            out += [f"\tif ({admits(row)}) && !fl.Given[{flag}] {{", f"\t\t{fld} = {row['default_go']}", "\t}"]
        elif row["default"].startswith("$"):
            var = row["default"][1:]
            fn = {"id": "valID", "addr": "valAddr"}.get(row["type"], "valNonEmpty")
            out += [f"\tif ({admits(row)}) && !fl.Given[{flag}] && getenv({go_str(var)}) != \"\" {{",
                    f"\t\tv, err := {fn}(getenv({go_str(var)}))",
                    "\t\tif err != nil {",
                    f"\t\t\treturn nil, refuse({flag}, \"the default ${var}: \"+err.Error())",
                    "\t\t}",
                    f"\t\t{fld} = v",
                    "\t}"]
    for row in table.rows:
        if row["default"].startswith("="):
            other = next(r for r in table.rows if r["flag"] == row["default"][1:])
            out += [f"\tif ({admits(row)}) && !fl.Given[{go_str(row['flag'])}] {{",
                    f"\t\tfl.{row['field']} = fl.{other['field']}", "\t}"]
    out += ["\treturn fl, nil", "}"]
    return "\n".join(out)


GO_API = '''
// RefuseCode — код выхода отказа запуска (P/01.3 Н1.3 refuse_start; Н4 «start_flags»).
const RefuseCode = 2

// Refusal — отказ разбора: флаг (или слово), причина. Код — всегда RefuseCode; лог называет флаг.
type Refusal struct {
	Code   int
	Flag   string
	Reason string
}

func (r *Refusal) Error() string { return "flag " + r.Flag + ": " + r.Reason }

func refuse(flag, reason string) *Refusal { return &Refusal{Code: RefuseCode, Flag: flag, Reason: reason} }

// Commands — команды таблицы: daemon (запуск без подкоманды) и подкоманды по порядку появления в колонке commands.
var Commands = []string{%s}

func isCommand(cmd string) bool {
	for _, c := range Commands {
		if c == cmd {
			return true
		}
	}
	return false
}

// Command — первое слово args, если это подкоманда таблицы (не daemon), и остаток; иначе daemon и args целиком.
func Command(args []string) (string, []string) {
	if len(args) > 0 && args[0] != "daemon" && isCommand(args[0]) {
		return args[0], args[1:]
	}
	return "daemon", args
}

// ParseArgs — Command и Parse; первое слово — не флаг и не подкоманда — отказ (свою подкоманду, например vectors,
// реализация разбирает до вызова).
func ParseArgs(args []string, getenv func(string) string) (*Flags, *Refusal) {
	cmd, rest := Command(args)
	if cmd == "daemon" && len(args) > 0 && (len(args[0]) < 2 || args[0][0] != '-') {
		return nil, refuse(args[0], "not a subcommand of the table")
	}
	return Parse(cmd, rest, getenv)
}

// Flags — разобранная командная строка. Поле флага, которого команда не допускает, — нулевое.
type Flags struct {
	Cmd   string          // daemon или подкоманда
	Given map[string]bool // флаги, данные в командной строке (ключи f таблицы)
	Args  []string        // позиционные слова по порядку (admit <id>, backup <file>, leave [id]) — не форма таблицы
%s}

type env struct{ f, cmd any }
'''


def go_module(table, rel, module, compiled):
    fields = ""
    for row in table.rows:
        dflt = row["default_text"] if row["default"] != "-" else "none"
        fields += (f"\t// {row['flag']} — {row['type']}; default {dflt}; {','.join(row['commands'])}; {row['norm']}\n"
                   f"\t{row['field']} {go_field_type(row['type'])}\n")
    imports = ['"os"', '"strings"'] + (['"time"'] if any(r["type"] == "duration" for r in table.rows) else [])
    parts = [f"// Code generated by tools/normgen/gen_flags.py from {rel}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}.\n\n"
             "// Package flags — разбор командной строки демона хранилища по таблице «Daemon flags» (ADR-0125 № 3).\n"
             "package flags\n\n"
             f"import ({chr(10).join(imports)})",
             GO_API.strip("\n") % (", ".join(go_str(c) for c in table.commands), fields)]
    if module.regexes:
        raise GenError(f"{table.name}: matches() is not used by the flag form")
    for name, (args, result, doc) in table.fns.items():
        parts.append(go_fn_wrapper(name, args, result, doc, True))
    for k, row in enumerate(table.rows, 1):
        for column in ("required", "bad"):
            if (k, column) in compiled:
                parts.append(go_function(f"{column}{k}", [], compiled[k, column],
                                         f"{row['flag']} {column}: {row[column]}"))
    parts.append(go_parse(table))
    return "\n\n".join(parts) + "\n"


def build(table, rel="daemon-flags.tsv"):
    """→ исходник Go flags.go; GenError — таблица вне формы."""
    _, go_prims = prims_present()
    for name in table.fns:
        if camel(name) not in go_prims:
            raise GenError(f"{table.name}: #fn {name}: no primitive prim{camel(name)} in tools/normgen/prims/go")
    module, compiled = Module(), {}
    for k, row in enumerate(table.rows, 1):
        for column in ("required", "bad"):
            if row[column] and not (column == "required" and row[column] in ("true", "false")):
                compiled[k, column] = compile_expr(table, module, f"{table.name}: {row['flag']}: {column}",
                                                   row[column], {})
        Parser(row["required"], row["flag"]).parse()
    return go_module(table, rel, module, compiled)


COPIES = (("flagtypes.go", HERE / "flags/go/flagtypes.go"), ("runtime.go", HERE / "runtime/go/runtime.go"),
          ("prims.go", HERE / "prims/go/prims.go"))


def render(table_path=DEFAULT_TABLE):
    """→ {имя файла в go/flags: текст}."""
    table_path = Path(table_path).resolve()
    try:
        rel = table_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = table_path.name
    table = Table(table_path.read_text(encoding="utf-8"), table_path.name)
    files = {"flags.go": gofmt(build(table, rel))}
    for name, src in COPIES:
        text = src.read_text(encoding="utf-8")
        text = re.sub(r"^package \w+", "package flags", text, count=1, flags=re.M)
        head = (f"// Code generated by tools/normgen/gen_flags.py: copy of tools/normgen/{src.relative_to(HERE)}; "
                "DO NOT EDIT.\n\n")
        files[name] = gofmt(head + text)
    return files


def generate(table_path=DEFAULT_TABLE, out=DEFAULT_OUT):
    gdir = Path(out) / "go/flags"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in render(table_path).items():
        (gdir / name).write_text(text, encoding="utf-8")
    return gdir


KIT_DIRS = ("flags",)
JUDGE = HERE / "flag_judge.py"


def kit_files(out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник)]; GenError — out устарел."""
    fresh, files = render(), []
    for name in sorted(fresh):
        kept = Path(out) / "go/flags" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != fresh[name]:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_flags.py")
        origin = "generated" if name == "flags.go" else "handwritten"
        source = kept if name == "flags.go" else dict(COPIES)[name]
        files.append(("flags", name, kept.read_bytes(), origin, str(Path(source).relative_to(ROOT))))
    return files


def provenance():
    """Паспорт части (ADR-0125 доп. (1) п. 6 (а)): форма, генератор, судья — пути и sha256."""
    def entry(path):
        return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"form": entry(DEFAULT_TABLE), "generator": entry(Path(__file__).resolve()), "judge": entry(JUDGE)}


KIT_MD = """
## Part `flags`: the daemon command line (generated from `forms/daemon-flags.tsv`)

| Package | Import path | Origin |
|---|---|---|
| `flags` | `{module}/internal/flags` | generated from `Platform/01-store/forms/daemon-flags.tsv` (P/01.3 Н1.3 «Daemon flags») |

```go
func ParseArgs(args []string, getenv func(string) string) (*flags.Flags, *flags.Refusal) // os.Args[1:], os.Getenv
func Command(args []string) (cmd string, rest []string)        // a subcommand of the table first, else "daemon"
func Parse(cmd string, args []string, getenv func(string) string) (*flags.Flags, *flags.Refusal)

type Refusal struct { Code int; Flag string; Reason string } // Code is always 2 (flags.RefuseCode)
type Flags struct {
    Cmd   string          // "daemon" or a subcommand: status, join, leave, admit, backup, restore, import, recover, rights
    Given map[string]bool // the flags given on the command line
    Args  []string        // positional words in order: admit <id>, backup <file>, leave [id] — yours to check
    Dir, ID, Sockets, Rights, TLS, Raft, RaftBind, API, Join, From string
    Bootstrap, Force, Isolated, Door, Groups bool
    GroupSize, Upper, MaxValue, MaxBody, MaxConns, APIConns, APIPerAddress, IndexBase int64
    LeaderWait time.Duration
    Tuning string
    Voters, Peers []flags.Member // Member{ID string; Addrs []string}: -voters id@addr (1 address), -peers id@raft/api (2)
}
```

- On a `*Refusal`: log `r.Error()` (it names the flag) and exit with `r.Code` (2) — the start refusal of P/01.3 Н1.3
  for a flag outside the table, a flag of another command, a value outside its type, a missing required flag
  (`-dir`; `-id` with `-join`, `-door`, `-group-size 3|5`; `-voters` with `-door`; `--from` for restore and import;
  `-isolated`, `-peers` for recover), `-bootstrap` with `-join`, `-raft` or `-api` off the loopback without `-tls`.
  For a subcommand the same refusal is the non-zero code of the CLI.
- Every field of a flag the command admits holds its value or the table default (`-raft-bind` = `-raft`; `-id` =
  `$SERVER_NAME` unless required). Fields of flags the command does not admit stay zero.
- Syntax: `-flag value` or `-flag=value`; a flag without a value (bool) takes no `=`; a repeated flag is a refusal;
  `--` ends the flags (the rest are positional). `--from` is spelled with two hyphens, as in the norm.
- Types: `bytes` — a plain integer of bytes > 0 (no `KiB`); `duration` — Go syntax (`5s`, `250ms`), not negative;
  `addr` — `host:port` with a decimal port; `id` — the member id of P/01.3 Н2.
- Not done here (content, not the form of the table): the rights file and the TLS kit contents, `-id` against the door
  certificate, the FORMAT mark, the inherited sockets, the positional words of the subcommands. Your own subcommands
  (for example `vectors` of part `tests`) — dispatch them before `ParseArgs`.
"""


def main(argv):
    table = argv[1] if len(argv) > 1 else DEFAULT_TABLE
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        print(generate(table, out))
    except GenError as exc:
        print(f"gen_flags: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
