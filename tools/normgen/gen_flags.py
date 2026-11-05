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
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import (FN_TYPES, GenError, Module, Parser, compile_expr, go_fn_wrapper,  # noqa: E402
                        go_function, go_str, gofmt, prims_present, camel)

import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT
DEFAULT_TABLE = L.form("daemon-flags.tsv")
DEFAULT_OUT = L.out
COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
FLAG = re.compile(r"-[a-z][a-z0-9-]*|--[a-z][a-z0-9-]*")
INPUT = re.compile(r"\$[A-Z][A-Z0-9_]*|<[a-z][a-z0-9_-]*>")    # входы процесса (P/03, P/04): $ОКРУЖЕНИЕ, <позиционный>
TYPE = re.compile(r"path|dir|file|addr|id|bool|duration|bytes:>0|list:id@addr(?:/addr)?|string|number"
                  r"|enum:[A-Za-z0-9_.-]+(?:\|[A-Za-z0-9_.-]+)*|int:(-?[0-9]+)\.\.(-?[0-9]*)")
INITIALISMS = {"id": "ID", "api": "API", "tls": "TLS"}
DURATION = re.compile(r"[1-9][0-9]*(?:ms|s|m|h)")          # шапка формы (P/01.3-R031)
DURATION_NS = {"ns": 1, "us": 1000, "µs": 1000, "ms": 10 ** 6, "s": 10 ** 9, "m": 60 * 10 ** 9, "h": 3600 * 10 ** 9}
MEMBER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
INT64 = (-2 ** 63, 2 ** 63 - 1)
NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")       # number: конечная десятичная запись (P/02 forms README)
COMMANDS_FORM = "operator-commands.tsv"                      # команды урока с префиксом argv (P/02); нет — команды P/01
COMMAND_COLUMNS = ["command", "process", "prefix", "positionals", "norm"]
COMMAND_ID = re.compile(r"[a-z][a-z0-9-]*")
WORD = re.compile(r"[a-z][a-z0-9-]*")


# ---------------------------------------------------------------- таблица

class Commands:
    """operator-commands.tsv: команда (id), процесс, префикс argv (JSON-массив слов), позиционные (JSON Schema массива
    строк с minItems/maxItems — другой схемы генератор не исполняет), норма."""

    def __init__(self, text, name=COMMANDS_FORM):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if line and not line.startswith("#")]
        if not body or body[0].split("\t") != COMMAND_COLUMNS:
            raise GenError(f"{name}: columns must be {COMMAND_COLUMNS}")
        self.rows, seen, prefixes = [], set(), set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(COMMAND_COLUMNS):
                raise GenError(f"{name}: row {k}: {len(cells)} cells, expected {len(COMMAND_COLUMNS)}")
            row = dict(zip(COMMAND_COLUMNS, cells))
            where = f"{name}: {row['command']}"
            if not COMMAND_ID.fullmatch(row["command"]) or row["command"] in seen:
                raise GenError(f"{where}: the command id is not [a-z][a-z0-9-]* or repeats")
            seen.add(row["command"])
            if not re.fullmatch(r"[a-z][a-z0-9.-]*", row["process"]):
                raise GenError(f"{where}: process {row['process']!r}")
            try:
                prefix, schema = json.loads(row["prefix"]), json.loads(row["positionals"])
            except ValueError as exc:
                raise GenError(f"{where}: prefix or positionals is not JSON: {exc}") from None
            if not isinstance(prefix, list) or not prefix or not all(isinstance(w, str) and WORD.fullmatch(w)
                                                                   for w in prefix):
                raise GenError(f"{where}: prefix — a non-empty JSON array of words [a-z][a-z0-9-]*")
            if (row["process"], tuple(prefix)) in prefixes:
                raise GenError(f"{where}: the prefix {prefix} of {row['process']} repeats")
            prefixes.add((row["process"], tuple(prefix)))
            if not isinstance(schema, dict) or set(schema) - {"type", "items", "minItems", "maxItems"} or \
                    schema.get("type") != "array" or schema.get("items") != {"type": "string"}:
                raise GenError(f"{where}: positionals — only {{type: array, items: {{type: string}}, minItems, "
                               f"maxItems}} is executed by the generator")
            lo, hi = schema.get("minItems", 0), schema.get("maxItems")
            if not isinstance(lo, int) or lo < 0 or (hi is not None and (not isinstance(hi, int) or hi < lo)):
                raise GenError(f"{where}: minItems/maxItems out of form")
            row.update(prefix=prefix, min=lo, max=hi)
            self.rows.append(row)
        self.ids = [r["command"] for r in self.rows]


class Table:
    def __init__(self, text, name="daemon-flags.tsv", commands=None):
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
        if commands is not None and not self.vars:              # P/02: f и cmd названы в шапке прозой
            self.vars = {"f": "map<string,dyn>", "cmd": "string"}
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
            if not (FLAG.fullmatch(row["flag"]) or INPUT.fullmatch(row["flag"])) or row["flag"] in seen:
                raise GenError(f"{where}: the flag is not -name (--name) or repeats")
            seen.add(row["flag"])
            if not TYPE.fullmatch(row["type"]):
                raise GenError(f"{where}: type {row['type']!r} is not of the closed vocabulary")
            row["commands"] = row["commands"].split(",")
            known = (lambda c: re.fullmatch(r"[a-z]+", c)) if commands is None else (lambda c: c in commands.ids)
            if not all(known(c) for c in row["commands"]) or \
                    len(set(row["commands"])) != len(row["commands"]):
                raise GenError(f"{where}: commands {row['commands']} — a comma list of names without repeats")
            if not row["required"]:
                raise GenError(f"{where}: required is empty (true, false or CEL)")
            row["field"] = input_field(row["flag"]) if INPUT.fullmatch(row["flag"]) else field_name(row["flag"])
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
        self.command_table = commands
        kinds = {bool(INPUT.fullmatch(r["flag"])) for r in self.rows}
        if kinds == {True, False}:
            raise GenError(f"{self.name}: flags and process inputs ($NAME, <arg>) in one form")
        self.inputs = kinds == {True}
        if self.inputs:
            if commands is not None:
                raise GenError(f"{self.name}: process inputs with {COMMANDS_FORM}")
            for row in self.rows:
                if row["default"].startswith(("=", "$")):
                    raise GenError(f"{self.name}: {row['flag']}: default {row['default']} — a literal or - for a process input")
                if row["type"] == "bool" or row["type"].startswith("list:"):
                    raise GenError(f"{self.name}: {row['flag']}: type {row['type']} for a process input")
            self.commands = []
            for row in self.rows:
                for c in row["commands"]:
                    if c not in self.commands:
                        self.commands.append(c)
            return
        if commands is not None:
            self.commands = list(commands.ids)
            return
        self.commands = []
        for row in self.rows:
            for c in row["commands"]:
                if c not in self.commands:
                    self.commands.append(c)
        if "daemon" not in self.commands:
            raise GenError(f"{self.name}: no flag of the command daemon")
        self.commands.remove("daemon")
        self.commands.insert(0, "daemon")


def input_field(name):
    """$BOX_ID → BoxID, $W2C_TLS_DIR → W2CTLSDir, <name> → Name."""
    words = re.split(r"[_-]", name.strip("$<>").lower())
    return "".join(INITIALISMS.get(w, w[:1].upper() + w[1:]) for w in words)


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
    if t in ("path", "dir", "file", "string"):
        if not d:
            raise bad
        return go_str(d)
    if t == "number":
        if not NUMBER.fullmatch(d):
            raise bad
        return f"float64({d})"
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
    if t == "number":
        return "float64"
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
    if t == "string":
        return ["v := raw", f"{fld} = v", "f[name] = v"]
    if t == "number":
        return ["v, err := valNumber(raw)", "if err != nil {", "\treturn nil, refuse(name, err.Error())", "}",
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
           "\t\t\tif cmd == \"daemon\" && k+1 < len(args) {",
           "\t\t\t\treturn nil, refuse(args[k+1], \"the daemon takes no positional words\")",
           "\t\t\t}",
           "\t\t\tfl.Args = append(fl.Args, args[k+1:]...)",
           "\t\t\tbreak",
           "\t\t}",
           "\t\tif len(tok) < 2 || tok[0] != '-' {",
           "\t\t\tif cmd == \"daemon\" {",
           "\t\t\t\treturn nil, refuse(tok, \"the daemon takes no positional words\")",
           "\t\t\t}",
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
            out += [f"\tif ({admits(row)}) && !fl.Given[{flag}] && getenv({go_str(var)}) == \"\" {{",
                    f"\t\treturn nil, refuse({flag}, {go_str('no ' + row['flag'] + ' and no $' + var)})",
                    "\t}",
                    f"\tif ({admits(row)}) && !fl.Given[{flag}] {{",
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


# ---------------------------------------------------------------- режим команд (P/02: operator-commands.tsv)

GO_API_CMD = """
// Refusal — a refusal of the option form of a command: the option (or the word) and the reason. The forms set no exit
// code for it: your command chooses it by its rows of forms/refusals.tsv; the message names the option.
type Refusal struct {
	Flag   string
	Reason string
}

func (r *Refusal) Error() string { return "option " + r.Flag + ": " + r.Reason }

func refuse(flag, reason string) *Refusal { return &Refusal{Flag: flag, Reason: reason} }

// Command — a row of forms/operator-commands.tsv: the id, the process, the fixed argv words (prefix), the count of the
// positional words after the options (Max -1 — no maximum).
type Command struct {
	ID      string
	Process string
	Prefix  []string
	Min     int
	Max     int
}

// Commands — the rows of operator-commands.tsv in order.
var Commands = []Command{
%s}

func isCommand(cmd string) bool {
	for _, c := range Commands {
		if c.ID == cmd {
			return true
		}
	}
	return false
}

// Lookup — the command of process whose prefix is the longest prefix of argv (argv without the process name) and the
// rest of argv; nil — no command of process starts argv.
func Lookup(process string, argv []string) (*Command, []string) {
	var best *Command
	for i := range Commands {
		c := &Commands[i]
		if c.Process != process || len(c.Prefix) > len(argv) || (best != nil && len(c.Prefix) <= len(best.Prefix)) {
			continue
		}
		ok := true
		for k, w := range c.Prefix {
			if argv[k] != w {
				ok = false
				break
			}
		}
		if ok {
			best = c
		}
	}
	if best == nil {
		return nil, argv
	}
	return best, argv[len(best.Prefix):]
}

// ParseArgv — Lookup and Parse: argv is the command line without the process name.
func ParseArgv(process string, argv []string) (*Flags, *Refusal) {
	c, rest := Lookup(process, argv)
	if c == nil {
		word := ""
		if len(argv) > 0 {
			word = argv[0]
		}
		return nil, refuse(word, "not a command of "+process+" (forms/operator-commands.tsv)")
	}
	return Parse(c.ID, rest)
}

// Flags — a parsed command line. A field of an option the command does not admit is zero.
type Flags struct {
	Cmd   string          // the command id of operator-commands.tsv
	Given map[string]bool // the options given on the line (the keys of f of the table)
	Args  []string        // the positional words in order (their count — the command's Min..Max)
%s}

type env struct{ f, cmd any }

var numberRE = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\\.[0-9]+)?$`)

// valNumber — the type number: a finite decimal number (forms/README.md «Command options»).
func valNumber(raw string) (float64, error) {
	if !numberRE.MatchString(raw) {
		return 0, errors.New("not a finite decimal number")
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsInf(v, 0) || math.IsNaN(v) {
		return 0, errors.New("not a finite decimal number")
	}
	return v, nil
}
"""


def go_parse_cmd(table):
    out = ["// Parse — the options and the positional words of the command cmd (an id of operator-commands.tsv): -name value",
           "// or -name=value, a bool without a value, -- ends the options (the kit's writing; the forms fix none).",
           "func Parse(cmd string, args []string) (*Flags, *Refusal) {",
           "\tif !isCommand(cmd) {",
           "\t\treturn nil, refuse(cmd, \"not a command of forms/operator-commands.tsv\")",
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
           "\t\t\treturn nil, refuse(name, \"the option is repeated\")",
           "\t\t}",
           "\t\tswitch name {"]
    for row in table.rows:
        out += [f"\t\tcase {go_str(row['flag'])}: // {row['type']}",
                f"\t\t\tif !({admits(row)}) {{",
                f"\t\t\t\treturn nil, refuse(name, \"not an option of the command \"+cmd)",
                "\t\t\t}"]
        if row["type"] == "bool":
            out += ["\t\t\tif eq {", "\t\t\t\treturn nil, refuse(name, \"the option takes no value\")", "\t\t\t}",
                    f"\t\t\tfl.{row['field']} = true", "\t\t\tf[name] = true"]
        else:
            out += ["\t\t\tif !eq {", "\t\t\t\tif k+1 >= len(args) {",
                    "\t\t\t\t\treturn nil, refuse(name, \"no value\")", "\t\t\t\t}",
                    "\t\t\t\tk++", "\t\t\t\traw = args[k]", "\t\t\t}"]
            out += [f"\t\t\t{s}" for s in go_assign(row)]
    out += ["\t\tdefault:",
            "\t\t\treturn nil, refuse(name, \"not an option of forms/daemon-flags.tsv\")",
            "\t\t}",
            "\t\tfl.Given[name] = true",
            "\t}",
            "\tfor _, c := range Commands {",
            "\t\tif c.ID == cmd && (len(fl.Args) < c.Min || (c.Max >= 0 && len(fl.Args) > c.Max)) {",
            "\t\t\treturn nil, refuse(cmd, fmt.Sprintf(\"%d positional words, the command takes %d..%d (-1: no maximum)\", "
            "len(fl.Args), c.Min, c.Max))",
            "\t\t}",
            "\t}",
            "\te := &env{f: f, cmd: cmd}",
            "\t_ = e // a table without CEL in required and bad does not read it"]
    for k, row in enumerate(table.rows, 1):
        if row["required"] == "false":
            continue
        test = "" if row["required"] == "true" else f" && isTrue(required{k}(e))"
        out += [f"\tif ({admits(row)}) && !fl.Given[{go_str(row['flag'])}]{test} {{",
                f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('the option is required: ' + row['required'])})",
                "\t}"]
    for k, row in enumerate(table.rows, 1):
        if row["bad"]:
            out += [f"\tif fl.Given[{go_str(row['flag'])}] && isTrue(bad{k}(e)) {{",
                    f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('a refusal of the option form: ' + row['bad'])})",
                    "\t}"]
    for row in table.rows:
        if row["default_go"] is not None:
            out += [f"\tif ({admits(row)}) && !fl.Given[{go_str(row['flag'])}] {{",
                    f"\t\tfl.{row['field']} = {row['default_go']}", "\t}"]
        elif row["default"].startswith("="):
            other = next(r for r in table.rows if r["flag"] == row["default"][1:])
            out += [f"\tif ({admits(row)}) && !fl.Given[{go_str(row['flag'])}] {{",
                    f"\t\tfl.{row['field']} = fl.{other['field']}", "\t}"]
    out += ["\treturn fl, nil", "}"]
    return "\n".join(out)


def go_module_cmd(table, rel, module, compiled):
    cmds = table.command_table
    for row in table.rows:
        if row["default"].startswith("$"):
            raise GenError(f"{table.name}: {row['flag']}: an environment default in the command form")
    fields = ""
    for row in table.rows:
        dflt = row["default_text"] if row["default"] != "-" else "none"
        fields += (f"\t// {row['flag']} — {row['type']}; default {dflt}; {','.join(row['commands'])}; {row['norm']}\n"
                   f"\t{row['field']} {go_field_type(row['type'])}\n")
    rows = "".join(f"\t{{ID: {go_str(r['command'])}, Process: {go_str(r['process'])}, Prefix: []string{{"
                   + ", ".join(go_str(w) for w in r["prefix"]) + f"}}, Min: {r['min']}, "
                   f"Max: {-1 if r['max'] is None else r['max']}}}, // {r['norm']}\n" for r in cmds.rows)
    imports = ['"errors"', '"fmt"', '"math"', '"regexp"', '"strconv"', '"strings"']
    parts = [f"// Code generated by tools/normgen/gen_flags.py from {rel} and {cmds.name}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}; команды sha256 {cmds.sha256}.\n\n"
             "// Package flags — the command line of the operator commands of the lesson (ADR-0125 № 3, addendum (5)):\n"
             "// the commands of forms/operator-commands.tsv, their options of forms/daemon-flags.tsv.\n"
             "package flags\n\n"
             f"import ({chr(10).join(imports)})",
             GO_API_CMD.strip("\n") % (rows, fields)]
    if module.regexes:
        parts.append("var (\n" + "".join(f"\trx{k} = regexp.MustCompile({go_str(re2)})\n"
                                         for k, (re2, _) in enumerate(module.regexes, 1)) + ")")
    for name, (args, result, doc) in table.fns.items():
        parts.append(go_fn_wrapper(name, args, result, doc, True))
    for k, row in enumerate(table.rows, 1):
        for column in ("required", "bad"):
            if (k, column) in compiled:
                parts.append(go_function(f"{column}{k}", [], compiled[k, column],
                                         f"{row['flag']} {column}: {row[column]}"))
    parts.append(go_parse_cmd(table))
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- режим входов процесса (P/03, P/04: $ОКРУЖЕНИЕ, <arg>)

GO_API_INPUTS = """
// Refusal — a refusal of a process input: the input ($NAME or <arg>) and the reason. The form sets no exit code for it:
// the process chooses it by its rows of forms/refusals.tsv (start); the message names the input.
type Refusal struct {
	Flag   string
	Reason string
}

func (r *Refusal) Error() string { return "input " + r.Flag + ": " + r.Reason }

func refuse(flag, reason string) *Refusal { return &Refusal{Flag: flag, Reason: reason} }

// Commands — the processes of the form (the column commands) in order of appearance.
var Commands = []string{%s}

func isCommand(cmd string) bool {
	for _, c := range Commands {
		if c == cmd {
			return true
		}
	}
	return false
}

// Inputs — the process inputs of cmd. A field of an input that cmd does not admit is zero; an input not given and
// without a literal default is zero too: its default rule (default_text, the field comment) is the adapter's, by the
// norm — Given tells which inputs were given.
type Inputs struct {
	Cmd   string          // the process: a value of the column commands
	Given map[string]bool // the inputs given ($NAME present in the environment, <arg> present): the keys of f
%s}

type env struct{ f, cmd any }

var numberRE = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\\.[0-9]+)?$`)

// valNumber — the type number: a finite decimal number.
func valNumber(raw string) (float64, error) {
	if !numberRE.MatchString(raw) {
		return 0, errors.New("not a finite decimal number")
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsInf(v, 0) || math.IsNaN(v) {
		return 0, errors.New("not a finite decimal number")
	}
	return v, nil
}
"""


def go_parse_inputs(table):
    pos = [r for r in table.rows if r["flag"].startswith("<")]
    out = ["// Parse — the process inputs of cmd: args are the positional words (the <arg> rows admitted by cmd, in form",
           "// order; more words — a refusal), getenv the environment (ok — the name is present, an empty value included).",
           "// Required and bad (CEL over f — the given values — and cmd) are checked before the literal defaults.",
           "func Parse(cmd string, args []string, getenv func(string) (string, bool)) (*Inputs, *Refusal) {",
           "\tif !isCommand(cmd) {",
           "\t\treturn nil, refuse(cmd, \"not a process of forms/daemon-flags.tsv\")",
           "\t}",
           "\tin := &Inputs{Cmd: cmd, Given: map[string]bool{}}",
           "\tf := map[string]any{}",
           "\tvar positional []string"]
    for row in pos:
        out += [f"\tif {admits(row)} {{", f"\t\tpositional = append(positional, {go_str(row['flag'])})", "\t}"]
    out += ["\tif len(args) > len(positional) {",
            "\t\treturn nil, refuse(args[len(positional)], fmt.Sprintf(\"%d positional words, the process takes %d\", "
            "len(args), len(positional)))",
            "\t}",
            "\tgiven := map[string]string{}",
            "\tfor k, w := range args {",
            "\t\tgiven[positional[k]] = w",
            "\t}"]
    for row in table.rows:
        if row["flag"].startswith("$"):
            out += [f"\tif {admits(row)} {{",
                    f"\t\tif v, ok := getenv({go_str(row['flag'][1:])}); ok {{",
                    f"\t\t\tgiven[{go_str(row['flag'])}] = v", "\t\t}", "\t}"]
    out += ["\tfor _, name := range inputOrder {",
            "\t\traw, ok := given[name]",
            "\t\tif !ok {",
            "\t\t\tcontinue",
            "\t\t}",
            "\t\tswitch name {"]
    for row in table.rows:
        out += [f"\t\tcase {go_str(row['flag'])}: // {row['type']}"]
        out += [f"\t\t\t{x}" for x in go_assign(row).copy()]
    out += ["\t\t}", "\t\tin.Given[name] = true", "\t}",
            "\te := &env{f: f, cmd: cmd}",
            "\t_ = e // a table without CEL in required and bad does not read it"]
    for k, row in enumerate(table.rows, 1):
        if row["required"] == "false":
            continue
        test = "" if row["required"] == "true" else f" && isTrue(required{k}(e))"
        out += [f"\tif ({admits(row)}) && !in.Given[{go_str(row['flag'])}]{test} {{",
                f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('the input is required: ' + row['required'])})",
                "\t}"]
    for k, row in enumerate(table.rows, 1):
        if row["bad"]:
            out += [f"\tif in.Given[{go_str(row['flag'])}] && isTrue(bad{k}(e)) {{",
                    f"\t\treturn nil, refuse({go_str(row['flag'])}, {go_str('a start refusal: ' + row['bad'])})",
                    "\t}"]
    for row in table.rows:
        if row["default_go"] is not None:
            out += [f"\tif ({admits(row)}) && !in.Given[{go_str(row['flag'])}] {{",
                    f"\t\tin.{row['field']} = {row['default_go']}", "\t}"]
    out += ["\treturn in, nil", "}"]
    return "\n".join(out).replace("fl.", "in.")


def go_module_inputs(table, rel, module, compiled):
    fields = ""
    for row in table.rows:
        dflt = row["default"] if row["default"] != "-" else "none"
        rule = f"; rule {row['default_text']}" if row["default_text"] not in ("-", row["default"]) else ""
        fields += (f"\t// {row['flag']} — {row['type']}; default {dflt}{rule}; {','.join(row['commands'])}; {row['norm']}\n"
                   f"\t{row['field']} {go_field_type(row['type'])}\n")
    order = "var inputOrder = []string{" + ", ".join(go_str(r["flag"]) for r in table.rows) + "}"
    imports = ['"errors"', '"fmt"', '"math"', '"regexp"', '"strconv"']
    parts = [f"// Code generated by tools/normgen/gen_flags.py from {rel}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}.\n\n"
             "// Package flags — the process inputs of the lesson (ADR-0125 № 3, addendum (5)): environment values $NAME\n"
             "// and positional <arg> of forms/daemon-flags.tsv; no CLI options.\n"
             "package flags\n\n"
             f"import ({chr(10).join(imports)})",
             GO_API_INPUTS.strip("\n") % (", ".join(go_str(c) for c in table.commands), fields), order]
    if module.regexes:
        parts.append("var (\n" + "".join(f"\trx{k} = regexp.MustCompile({go_str(re2)})\n"
                                         for k, (re2, _) in enumerate(module.regexes, 1)) + ")")
    for name, (args, result, doc) in table.fns.items():
        parts.append(go_fn_wrapper(name, args, result, doc, True))
    for k, row in enumerate(table.rows, 1):
        for column in ("required", "bad"):
            if (k, column) in compiled:
                parts.append(go_function(f"{column}{k}", [], compiled[k, column],
                                         f"{row['flag']} {column}: {row[column]}"))
    parts.append(go_parse_inputs(table))
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
    if table.command_table is not None:
        return go_module_cmd(table, rel, module, compiled)
    if table.inputs:
        return go_module_inputs(table, rel, module, compiled)
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
    cmds_path = table_path.parent / COMMANDS_FORM
    cmds = Commands(cmds_path.read_text(encoding="utf-8")) if cmds_path.is_file() else None
    table = Table(table_path.read_text(encoding="utf-8"), table_path.name, cmds)
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
    mod = Path(out) / "go/go.mod"                     # модуль выхода урока (у P/01 его пишет gen_tests)
    if not mod.exists():
        mod.write_text(f"module {L.go_module}\n\ngo 1.22\n", encoding="utf-8")
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
    cmds = DEFAULT_TABLE.parent / COMMANDS_FORM
    if cmds.is_file():                                 # команды урока (P/02): обе формы, судья cmdflag_judge
        return {"form": [entry(DEFAULT_TABLE), entry(cmds)], "generator": entry(Path(__file__).resolve()),
                "judge": entry(HERE / "cmdflag_judge.py")}
    if inputs_form():                                  # входы процесса (P/03, P/04): судья test_gen_flags_inputs
        return {"form": [entry(DEFAULT_TABLE)], "generator": entry(Path(__file__).resolve()),
                "judge": entry(HERE / "test_gen_flags_inputs.py")}
    return {"form": entry(DEFAULT_TABLE), "generator": entry(Path(__file__).resolve()), "judge": entry(JUDGE)}


def inputs_form():
    """Форма урока — входы процесса ($NAME, <arg>), а не флаги."""
    if not DEFAULT_TABLE.is_file() or (DEFAULT_TABLE.parent / COMMANDS_FORM).is_file():
        return False
    return Table(DEFAULT_TABLE.read_text(encoding="utf-8"), DEFAULT_TABLE.name).inputs


KIT_MD_INPUTS = """
## Part `flags`: the process inputs (generated from `forms/daemon-flags.tsv`: `$NAME` environment, `<arg>` positional)

| Package | Import path | Origin |
|---|---|---|
| `flags` | `{module}/internal/flags` | generated: `Parse`, `Inputs`, `Commands`, `Refusal`; closed |

```go
func Parse(cmd string, args []string, getenv func(string) (string, bool)) (*Inputs, *Refusal) // cmd — a process of the form
type Inputs struct { Cmd string; Given map[string]bool; /* one field per row */ }
type Refusal struct { Flag, Reason string }   // no exit code: the process chooses it by forms/refusals.tsv
```

`getenv` reports presence (`os.LookupEnv`; an empty value is given). The kit checks the form only: the type (dir and
file non-empty, number a finite decimal), `required`, `bad` (CEL over the given values), then literal defaults. A
default rule (`default_text`, in the field comment) and the contract checks of the norms (instance, labels, addresses,
role, capacity) are yours — `Given` tells what was supplied.
"""


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
  `--` ends the flags (the rest are positional); the daemon takes no positional words (a refusal). `--from` is spelled with two hyphens, as in the norm.
- Types (the header of the form, P/01.3-R031): `bytes`, `int` — a decimal integer without a sign, a plus or leading
  zeros, `bytes` without a suffix (no `KiB`); `duration` — `<integer>(ms|s|m|h)`, > 0 (`5s`, `250ms`; not `1h30m`);
  `addr` — `host:port`, a non-empty host (a name, IPv4 or `[IPv6]`), a port 1–65535; `id` — the member id of P/01.3 Н2.
- No `-id` and an empty or absent `SERVER_NAME` (outside a group) — a refusal, code 2.
- Not done here (content, not the form of the table): the rights file and the TLS kit contents, `-id` against the door
  certificate, the FORMAT mark, the inherited sockets, the positional words of the subcommands. Your own subcommands
  (for example `vectors` of part `tests`) — dispatch them before `ParseArgs`.
"""


KIT_MD = KIT_MD.replace("Platform/01-store/", L.rel + "/")      # пути урока; прочий текст — урока P/01

KIT_MD_CMD = """
## Part `flags`: the command line of the operator commands (generated from `forms/operator-commands.tsv` and `forms/daemon-flags.tsv`)

| Package | Import path | Origin |
|---|---|---|
| `flags` | `{module}/internal/flags` | generated: the commands, their options and positional words; closed |

```go
func ParseArgv(process string, argv []string) (*Flags, *Refusal) // argv without the process name: Lookup, then Parse
func Lookup(process string, argv []string) (*Command, []string) // the command whose prefix is the longest prefix of argv
func Parse(cmd string, args []string) (*Flags, *Refusal)        // cmd — a command id of operator-commands.tsv
type Command struct { ID, Process string; Prefix []string; Min, Max int } // Max -1 — no maximum
var Commands []Command                                          // the rows of operator-commands.tsv
type Flags struct { Cmd string; Given map[string]bool; Args []string; /* one field per option */ }
type Refusal struct { Flag, Reason string }                     // Error() names the option
```

- The kit's writing of an option (the forms fix none — a choice of the kit, not a norm): `-name value` or `-name=value`;
  a `bool` takes no value (given — true, absent — false); `--` ends the options; the other words are positional.
- `number` — the kit's choice of writing: a finite decimal `-?(0|[1-9][0-9]*)(\\.[0-9]+)?` (no `+`, exponent or `.5`);
  the value is kept as `float64` with its fraction. `string` — the word as is; `file` — a non-empty path.
- `required` and `bad` of the form are evaluated (CEL over `f` and `cmd`); a refusal is a `*Refusal`. **The forms set no
  exit code for it**: your command chooses the code by its rows of `forms/refusals.tsv` (surface `cli`).
"""


def kit_md():
    """Справка части: команды урока (operator-commands.tsv) — KIT_MD_CMD; иначе флаги демона P/01."""
    if (DEFAULT_TABLE.parent / COMMANDS_FORM).is_file():
        return KIT_MD_CMD
    return KIT_MD_INPUTS if inputs_form() else KIT_MD


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
