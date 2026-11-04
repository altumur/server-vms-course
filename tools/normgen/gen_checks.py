"""Генератор кода проверок по таблице формы ADR-0120 п. 2 (а) — пилот на P/01.1 Н2.1 (`write-checks.tsv`).

Читает таблицу (шапка `#var`, `#lim`, `#fn`; колонки n op group each check when code kind fault norm) и строит:
- модуль Go 1.22 только на стандартной библиотеке: `<out>/go/checks/checks.go` (package checks) и рядом
  `runtime.go` (среда CEL, tools/normgen/runtime/go) и `prims.go` (примитивы #fn, tools/normgen/prims/go);
- модуль Python 3.12 только на стандартной библиотеке: `<out>/python/checks.py` (среда и примитивы вставлены в файл).

`when` и `fault` переводятся из подмножества CEL в нативный код: свой разбор выражения и порождение операторов, без
интерпретатора CEL. Подмножество — ровно то, что встречается в таблице: литералы (строки, int, double, bool, null,
списки, отображения), идентификаторы, выбор поля, индекс, `!`, `&&`, `||`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`,
`?:`, `+`, `type()` и имена типов, `has()`, `size()`, `string()`, методы `matches` (шаблон — литерал), `startsWith`,
`exists` (одна и две переменные). Всё прочее — отказ генератора с номером строки (GenError).

Семантика — та, что у оракула skills/lesson-spec/scripts/check_tables.py на cel-expr-python: ошибка CEL — значение,
`&&` и `||` поглощают её (false && ошибка = false, true || ошибка = true), `exists` — true, если хоть один шаг true,
иначе ошибка, если хоть один шаг ошибка; `when` не bool — ошибка; строка с ошибкой в цепочке не нарушена.

Запуск: python tools/normgen/gen_checks.py [таблица.tsv [каталог_выхода]].
"""
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_TABLE = ROOT / "Platform/01-store/forms/write-checks.tsv"          # ADR-0124: формы — в forms/
DEFAULT_OUT = HERE / "out/p01-1"
COLUMNS = ["n", "op", "group", "each", "check", "when", "code", "kind", "fault", "norm"]
EACH = re.compile(r"([a-z]\w*), ([a-z]\w*) in (body(?:\.[a-z_]+)+)")
FN_TYPES = {"string", "map", "double", "int", "bool", "list", "dyn"}
TYPE_NAMES = ("bool", "int", "double", "string", "list", "map", "null_type", "type")
INT_MAX = 2 ** 63 - 1


class GenError(Exception):
    """Отказ генератора: таблица вне формы или выражение вне подмножества."""


# ---------------------------------------------------------------- таблица

class Table:
    def __init__(self, text, name="table"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.vars, self.lims, self.fns, self.rows = {}, [], {}, []
        lines = text.splitlines()
        for line in lines:
            if m := re.match(r"#var (\w+) (\S+) — ", line):
                self.vars[m[1]] = m[2]
            elif m := re.match(r"#lim ([A-Z][A-Z0-9_]*) — ", line):
                self.lims.append(m[1])
            elif m := re.match(r"#fn ([a-z_]+)\(([^)]*)\) -> (\w+) — (.*)", line):
                args = [a.strip() for a in m[2].split(",") if a.strip()]
                for t in args + [m[3]]:
                    if t not in FN_TYPES:
                        raise GenError(f"{name}: #fn {m[1]}: type {t!r} — one of {sorted(FN_TYPES)}")
                self.fns[m[1]] = (args, m[3], m[4])
            elif re.match(r"#(var|lim|fn) ", line):
                raise GenError(f"{name}: header line out of form: {line}")
        if set(self.vars) != {"body", "sock", "lone", "lim"}:
            raise GenError(f"{name}: #var must declare body, sock, lone, lim (got {sorted(self.vars)})")
        body = [line for line in lines if not line.startswith("#")]
        if not body or body[0].split("\t") != COLUMNS:
            raise GenError(f"{name}: columns must be {COLUMNS}")
        last_group, seen = None, set()
        for k, line in enumerate(body[1:], 1):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                raise GenError(f"{name}: row {k}: {len(cells)} cells, expected {len(COLUMNS)}")
            row = dict(zip(COLUMNS, cells))
            where = f"{name}: n {row['n']}"
            if row["n"] != str(k):
                raise GenError(f"{where}: n must be {k}")
            if row["op"] != "*" and not re.fullmatch(r"[a-z]+(,[a-z]+)*", row["op"]):
                raise GenError(f"{where}: op {row['op']!r} — * or a list of values")
            if not re.fullmatch(r"[a-z][a-z_]*", row["check"]):
                raise GenError(f"{where}: check {row['check']!r} — a Latin name")
            if not re.fullmatch(r"[1-5][0-9]{2}", row["code"]) or not re.fullmatch(r"[a-z]+", row["kind"]):
                raise GenError(f"{where}: code {row['code']!r} / kind {row['kind']!r}")
            if bool(row["group"]) != bool(row["each"]):
                raise GenError(f"{where}: group and each go together")
            if row["group"]:
                if not EACH.fullmatch(row["each"]):
                    raise GenError(f"{where}: each {row['each']!r} — «i, x in body.<поле>»")
                if row["group"] != last_group:
                    if row["group"] in seen:
                        raise GenError(f"{where}: group {row['group']} is not contiguous")
                    seen.add(row["group"])
                elif row["each"] != self.rows[-1]["each"]:
                    raise GenError(f"{where}: rows of group {row['group']} differ in each")
            if not row["when"]:
                raise GenError(f"{where}: when is empty")
            last_group = row["group"] or None
            row["n"], row["code"] = int(row["n"]), int(row["code"])
            self.rows.append(row)

    def plan(self):
        """[('row', row) | ('group', (i, x, path parts), rows)] — порядок цепочки, как Table.steps оракула."""
        out, k = [], 0
        while k < len(self.rows):
            row = self.rows[k]
            if not row["group"]:
                out.append(("row", row))
                k += 1
                continue
            rows = []
            while k < len(self.rows) and self.rows[k]["group"] == row["group"]:
                rows.append(self.rows[k])
                k += 1
            i, x, path = EACH.fullmatch(row["each"]).groups()
            out.append(("group", (i, x, path.split(".")[1:]), rows))
        return out


# ---------------------------------------------------------------- разбор CEL

TOKEN = re.compile(r"""
  (?P<ws>\s+)
| (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[uU]?)
| (?P<str>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
| (?P<id>[A-Za-z_][A-Za-z0-9_]*)
| (?P<op>\|\||&&|==|!=|<=|>=|[<>!?:()\[\]{},.+\-*/%])
""", re.X)
ESCAPES = {"\\": "\\", '"': '"', "'": "'", "n": "\n", "r": "\r", "t": "\t"}
RELOPS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge", "in": "in"}


class Node:
    __slots__ = ("kind", "args", "pos")

    def __init__(self, kind, *args, pos):
        self.kind, self.args, self.pos = kind, args, pos


class Parser:
    def __init__(self, text, where):
        self.text, self.where, self.toks, self.k = text, where, [], 0
        pos = 0
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                self.fail(pos, f"unexpected character {text[pos]!r}")
            if m.lastgroup != "ws":
                self.toks.append((m.lastgroup, m.group(), pos))
            pos = m.end()
        self.toks.append(("end", "", len(text)))

    def fail(self, pos, msg):
        raise GenError(f"{self.where}: {msg} at {pos}: {self.text[pos:pos + 24]!r}")

    def peek(self):
        return self.toks[self.k]

    def take(self, text=None):
        tok = self.toks[self.k]
        if text is not None and tok[1] != text:
            self.fail(tok[2], f"expected {text!r}")
        self.k += 1
        return tok

    def at(self, *texts):
        tok = self.toks[self.k]
        return tok[0] in ("op", "id") and tok[1] in texts

    def parse(self):
        node = self.expr()
        if self.peek()[0] != "end":
            self.fail(self.peek()[2], "unexpected token")
        return node

    def expr(self):
        node = self.or_()
        if self.at("?"):
            pos = self.take()[2]
            a = self.or_()
            self.take(":")
            b = self.expr()
            node = Node("cond", node, a, b, pos=pos)
        return node

    def or_(self):
        node = self.and_()
        while self.at("||"):
            pos = self.take()[2]
            node = Node("bin", "||", node, self.and_(), pos=pos)
        return node

    def and_(self):
        node = self.rel()
        while self.at("&&"):
            pos = self.take()[2]
            node = Node("bin", "&&", node, self.rel(), pos=pos)
        return node

    def rel(self):
        node = self.add()
        while self.at(*RELOPS):
            op, pos = self.take()[1:]
            node = Node("bin", op, node, self.add(), pos=pos)
        return node

    def add(self):
        node = self.unary()
        while self.at("+", "-", "*", "/", "%"):
            op, pos = self.take()[1:]
            if op != "+":
                self.fail(pos, f"operator {op} is out of the subset")
            node = Node("bin", "+", node, self.unary(), pos=pos)
        return node

    def unary(self):
        if self.at("!"):
            pos = self.take()[2]
            return Node("not", self.unary(), pos=pos)
        if self.at("-"):
            self.fail(self.peek()[2], "unary - is out of the subset")
        return self.member()

    def member(self):
        node = self.primary()
        while True:
            if self.at("."):
                self.take()
                kind, name, pos = self.take()
                if kind != "id":
                    self.fail(pos, "expected a field name")
                if self.at("("):
                    node = Node("method", node, name, self.args(")"), pos=pos)
                else:
                    node = Node("select", node, name, pos=pos)
            elif self.at("["):
                pos = self.take()[2]
                index = self.expr()
                self.take("]")
                node = Node("index", node, index, pos=pos)
            else:
                return node

    def args(self, close):
        self.take()
        out = []
        while not self.at(close):
            out.append(self.expr())
            if not self.at(","):
                break
            self.take()
        self.take(close)
        return out

    def primary(self):
        kind, text, pos = self.peek()
        if kind == "num":
            self.take()
            if text[-1] in "uU":
                self.fail(pos, "uint literal is out of the subset")
            if re.search(r"[.eE]", text):
                value = float(text)
                if value != value or value in (float("inf"), float("-inf")):
                    self.fail(pos, "double literal out of binary64 range")
                return Node("lit", "double", value, pos=pos)
            value = int(text)
            if value > INT_MAX:
                self.fail(pos, "int literal out of int64 range")
            return Node("lit", "int", value, pos=pos)
        if kind == "str":
            self.take()
            return Node("lit", "string", self.unquote(text, pos), pos=pos)
        if kind == "id":
            self.take()
            if text in ("true", "false"):
                return Node("lit", "bool", text == "true", pos=pos)
            if text == "null":
                return Node("lit", "null", None, pos=pos)
            if self.peek()[0] == "str":
                self.fail(pos, f"string prefix {text} is out of the subset")
            if self.at("("):
                return Node("call", text, self.args(")"), pos=pos)
            return Node("ident", text, pos=pos)
        if self.at("("):
            self.take()
            node = self.expr()
            self.take(")")
            return node
        if self.at("["):
            return Node("list", self.args("]"), pos=pos)
        if self.at("{"):
            self.take()
            pairs = []
            while not self.at("}"):
                key = self.expr()
                self.take(":")
                pairs.append((key, self.expr()))
                if not self.at(","):
                    break
                self.take()
            self.take("}")
            return Node("map", pairs, pos=pos)
        self.fail(pos, "unexpected token")

    def unquote(self, text, pos):
        body, out, k = text[1:-1], [], 0
        while k < len(body):
            ch = body[k]
            if ch != "\\":
                out.append(ch)
                k += 1
                continue
            nxt = body[k + 1]
            if nxt in ESCAPES:
                out.append(ESCAPES[nxt])
                k += 2
            elif nxt == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", body[k + 2:k + 6]):
                code = int(body[k + 2:k + 6], 16)
                if 0xD800 <= code < 0xE000:
                    self.fail(pos, "surrogate escape in a string literal")
                out.append(chr(code))
                k += 6
            else:
                self.fail(pos, f"escape \\{nxt} is out of the subset")
        return "".join(out)


# ---------------------------------------------------------------- шаблоны matches

def regex_for_python(pattern, fail):
    """Проверка шаблона RE2 на малое подмножество, общее с re Python; → шаблон Python ($ → \\Z)."""
    out, k, n = [], 0, len(pattern)
    escapable = set(".\\-/()[]{}*+?|^$")
    while k < n:
        ch = pattern[k]
        if ch == "\\":
            if k + 1 >= n or pattern[k + 1] not in escapable:
                fail(f"regex escape {pattern[k:k + 2]!r} is out of the subset")
            out.append(pattern[k:k + 2])
            k += 2
        elif ch == "[":
            end = k + 1
            if end < n and pattern[end] == "^":
                end += 1
            if end < n and pattern[end] == "]":
                fail("regex class starting with ] is out of the subset")
            while end < n and pattern[end] != "]":
                if pattern[end] == "\\":
                    if end + 1 >= n or pattern[end + 1] not in escapable:
                        fail("regex escape in a class is out of the subset")
                    end += 2
                    continue
                if pattern[end] == "[":
                    fail("[ inside a regex class is out of the subset")
                end += 1
            if end >= n:
                fail("regex class is not closed")
            out.append(pattern[k:end + 1])
            k = end + 1
        elif ch == "(":
            if pattern[k + 1:k + 2] == "?":
                fail("regex group flags (? are out of the subset")
            out.append(ch)
            k += 1
        elif ch == "{":
            m = re.compile(r"\{(\d{1,4})(,(\d{0,4}))?\}").match(pattern, k)
            if not m or int(m[1]) > 1000 or m[3] and int(m[3]) > 1000 or m[3] and int(m[3]) < int(m[1]):
                fail("regex repetition is out of the subset")
            out.append(m[0])
            k = m.end()
        elif ch == "$":
            out.append(r"\Z")
            k += 1
        elif ch in "}]":
            fail(f"unbalanced {ch} in a regex")
        elif ord(ch) < 0x20:
            fail("control character in a regex")
        else:
            out.append(ch)
            k += 1
    text = "".join(out)
    try:
        re.compile(text)
    except re.error as exc:
        fail(f"regex does not compile: {exc}")
    return text


# ---------------------------------------------------------------- перевод в операторы
# Операнд: ('t', имя) | ('v', выражение переменной) | ('lit', вид, значение) | ('type', имя) | ('rx', номер)
#          | ('str', строка) | ('keys', [строки]).
# Оператор: ('set', t, помощник, [операнды]) | ('or'|'and', t, L, l, R, r) | ('cond', t, C, c, A, a, B, b)
#           | ('exists', t, R, r, v1, v2 | None, P, p).

class Module:
    """Общее на модуль: шаблоны matches."""

    def __init__(self):
        self.regexes = []          # [(шаблон RE2, шаблон Python)]

    def regex(self, pattern, fail):
        py = regex_for_python(pattern, fail)
        for k, (re2, _) in enumerate(self.regexes, 1):
            if re2 == pattern:
                return k
        self.regexes.append((pattern, py))
        return len(self.regexes)


class Compiler:
    def __init__(self, table, module, where, bound):
        self.table, self.module, self.where = table, module, where
        self.scopes = [bound]      # bound: имя CEL → выражение переменной
        self.t, self.c = 0, 0
        self.temps = []

    def fail(self, node, msg):
        raise GenError(f"{self.where}: {msg} (at {node.pos})")

    def tmp(self):
        self.t += 1
        name = f"t{self.t}"
        self.temps.append(name)
        return name

    def resolve(self, node):
        name = node.args[0]
        for scope in reversed(self.scopes):
            if name in scope:
                return ("v", scope[name])
        if name in self.table.vars:
            return ("v", f"e.{name}")
        if name in TYPE_NAMES:
            return ("type", name)
        self.fail(node, f"identifier {name} is not declared (#var, each or a comprehension)")

    def set(self, helper, ops):
        t = self.tmp()
        return ("set", t, helper, ops), ("t", t)

    def compile(self, node):
        """→ (операторы, операнд результата)."""
        kind, a = node.kind, node.args
        if kind == "lit":
            return [], ("lit", a[0], a[1])
        if kind == "ident":
            return [], self.resolve(node)
        if kind == "select":
            target, field = a
            if target.kind == "ident" and target.args[0] == "lim" and self.resolve(target) == ("v", "e.lim") \
                    and field not in self.table.lims:
                self.fail(node, f"lim.{field} is not declared by #lim")
            return self.call("select", [target], extra=[("str", field)])
        if kind == "index":
            return self.call("index", list(a))
        if kind == "not":
            return self.call("not", [a[0]])
        if kind == "bin":
            op, left, right = a
            if op in ("||", "&&"):
                ls, lo = self.compile(left)
                rs, ro = self.compile(right)
                t = self.tmp()
                return ls + [("or" if op == "||" else "and", t, [], lo, rs, ro)], ("t", t)
            if op == "+":
                return self.call("add", [left, right])
            return self.call(RELOPS[op], [left, right])
        if kind == "cond":
            cs, co = self.compile(a[0])
            xs, xo = self.compile(a[1])
            ys, yo = self.compile(a[2])
            t = self.tmp()
            return cs + [("cond", t, [], co, xs, xo, ys, yo)], ("t", t)
        if kind == "list":
            return self.call("list", list(a[0]))
        if kind == "map":
            keys = []
            for key, _ in a[0]:
                if key.kind != "lit" or key.args[0] != "string":
                    self.fail(key, "map literal keys must be string literals")
                if key.args[1] in keys:
                    self.fail(key, f"duplicate map key {key.args[1]!r}")
                keys.append(key.args[1])
            stmts, ops = self.many([v for _, v in a[0]])
            s, o = self.set("map", [("keys", keys)] + ops)
            return stmts + [s], o
        if kind == "call":
            return self.global_call(node)
        if kind == "method":
            return self.method(node)
        self.fail(node, f"{kind} is out of the subset")

    def many(self, nodes):
        stmts, ops = [], []
        for n in nodes:
            s, o = self.compile(n)
            stmts += s
            ops.append(o)
        return stmts, ops

    def call(self, helper, nodes, extra=()):
        stmts, ops = self.many(nodes)
        s, o = self.set(helper, ops + list(extra))
        return stmts + [s], o

    def global_call(self, node):
        name, args = node.args
        if name == "has":
            if len(args) != 1 or args[0].kind != "select":
                self.fail(node, "has() takes one field selection x.f")
            target, field = args[0].args
            return self.call("has", [target], extra=[("str", field)])
        if name in ("type", "size", "string"):
            if len(args) != 1:
                self.fail(node, f"{name}() takes one argument")
            return self.call(name, args)
        if name in self.table.fns:
            want = self.table.fns[name][0]
            if len(args) != len(want):
                self.fail(node, f"{name}() takes {len(want)} arguments (#fn), got {len(args)}")
            return self.call(("fn", name), args)
        self.fail(node, f"function {name}() is out of the subset and not declared by #fn")

    def method(self, node):
        target, name, args = node.args
        if name == "matches":
            if len(args) != 1 or args[0].kind != "lit" or args[0].args[0] != "string":
                self.fail(node, "matches() takes one string literal pattern")
            k = self.module.regex(args[0].args[1], lambda msg: self.fail(args[0], msg))
            return self.call("matches", [target], extra=[("rx", k)])
        if name == "startsWith":
            if len(args) != 1:
                self.fail(node, "startsWith() takes one argument")
            return self.call("startswith", [target, args[0]])
        if name == "exists":
            if len(args) not in (2, 3) or any(v.kind != "ident" for v in args[:-1]):
                self.fail(node, "exists() takes one or two variable names and a predicate")
            names = [v.args[0] for v in args[:-1]]
            if len(set(names)) != len(names) or any(v in ("true", "false", "null") for v in names):
                self.fail(node, "exists() variables must be distinct names")
            rs, ro = self.compile(target)
            self.c += 1
            scope = {v: f"c{self.c}_{v}" for v in names}
            self.scopes.append(scope)
            ps, po = self.compile(args[-1])
            self.scopes.pop()
            t = self.tmp()
            self.temps.append(f"{t}e")
            v1 = scope[names[0]]
            v2 = scope[names[1]] if len(names) == 2 else None
            return rs + [("exists", t, [], ro, v1, v2, ps, po)], ("t", t)
        self.fail(node, f"method {name}() is out of the subset")


def compile_expr(table, module, where, text, bound):
    comp = Compiler(table, module, where, bound)
    stmts, result = comp.compile(Parser(text, where).parse())
    return stmts, result, comp.temps


# ---------------------------------------------------------------- вывод: Python

PY_HELPERS = {"eq": "_eq", "ne": "_ne", "lt": "_lt", "le": "_le", "gt": "_gt", "ge": "_ge", "in": "_in",
              "not": "_not", "select": "_sel", "has": "_has", "index": "_index", "size": "_size",
              "string": "_string", "add": "_add", "type": "_type", "startswith": "_starts", "matches": "_matches",
              "list": "_list", "map": "_map"}
PY_TYPECHECK = {"string": "str", "map": "dict", "double": "float", "int": "int", "bool": "bool", "list": "list"}


def py_operand(op):
    kind = op[0]
    if kind in ("t", "v"):
        return op[1]
    if kind == "lit":
        return repr(op[2])
    if kind == "type":
        return f'_TYPES["{op[1]}"]'
    if kind == "rx":
        return f"_RX{op[1]}"
    if kind == "str":
        return repr(op[1])
    if kind == "keys":
        return "(" + "".join(f"{k!r}, " for k in op[1]) + ")"
    raise AssertionError(op)


def py_stmts(stmts, ind):
    pad = "    " * ind
    out = []
    for s in stmts:
        kind = s[0]
        if kind == "set":
            _, t, helper, ops = s
            args = [py_operand(o) for o in ops]
            if isinstance(helper, tuple):
                out.append(f"{pad}{t} = _fn_{helper[1]}(e, {', '.join(args)})")
            else:
                out.append(f"{pad}{t} = {PY_HELPERS[helper]}({', '.join(args)})")
        elif kind in ("or", "and"):
            _, t, ls, lo, rs, ro = s
            lo, ro = py_operand(lo), py_operand(ro)
            stop = "True" if kind == "or" else "False"
            out += py_stmts(ls, ind)
            out.append(f"{pad}if {lo} is {stop}:")
            out.append(f"{pad}    {t} = {stop}")
            out.append(f"{pad}else:")
            out += py_stmts(rs, ind + 1)
            out.append(f"{pad}    {t} = _{kind}({lo}, {ro})")
        elif kind == "cond":
            _, t, cs, co, xs, xo, ys, yo = s
            co = py_operand(co)
            out += py_stmts(cs, ind)
            out.append(f"{pad}if {co} is True:")
            out += py_stmts(xs, ind + 1)
            out.append(f"{pad}    {t} = {py_operand(xo)}")
            out.append(f"{pad}elif {co} is False:")
            out += py_stmts(ys, ind + 1)
            out.append(f"{pad}    {t} = {py_operand(yo)}")
            out.append(f"{pad}else:")
            out.append(f"{pad}    {t} = _cond_err({co})")
        elif kind == "exists":
            _, t, rs, ro, v1, v2, ps, po = s
            r, p = py_operand(ro), py_operand(po)
            out += py_stmts(rs, ind)
            out.append(f"{pad}if type({r}) is list or type({r}) is dict:")
            out.append(f"{pad}    {t} = False")
            out.append(f"{pad}    {t}e = None")
            if v2 is None:
                out.append(f"{pad}    for {v1} in {r}:")
            else:
                out.append(f"{pad}    for {v1}, {v2} in (enumerate({r}) if type({r}) is list else {r}.items()):")
            out += py_stmts(ps, ind + 2)
            out.append(f"{pad}        if {p} is True:")
            out.append(f"{pad}            {t} = True")
            out.append(f"{pad}            break")
            out.append(f"{pad}        if {p} is not False:")
            out.append(f"{pad}            {t}e = _pred_err({t}e, {p})")
            out.append(f"{pad}    if {t} is False and {t}e is not None:")
            out.append(f"{pad}        {t} = {t}e")
            out.append(f"{pad}else:")
            out.append(f"{pad}    {t} = _range_err({r})")
        else:
            raise AssertionError(s)
    return out


def py_function(name, params, compiled, doc):
    stmts, result, _ = compiled
    lines = [f"def {name}({', '.join(['e'] + params)}):", f"    # {doc}"]
    lines += py_stmts(stmts, 1)
    lines.append(f"    return {py_operand(result)}")
    return "\n".join(lines)


def py_fn_wrapper(name, args, result, doc, prim):
    params = [f"a{k}" for k in range(len(args))]
    lines = [f"def _fn_{name}({', '.join(['e'] + params)}):",
             f"    # #fn {name}({', '.join(args)}) -> {result} — {doc}"]
    for p in params:
        lines.append(f"    if type({p}) is CelError:")
        lines.append(f"        return {p}")
    checks = [f"type({p}) is not {PY_TYPECHECK[t]}" for p, t in zip(params, args) if t != "dyn"]
    if checks:
        lines.append(f"    if {' or '.join(checks)}:")
        lines.append(f"        return _no({name!r}, {', '.join(params)})")
    if prim:
        call = f"prim_{name}({', '.join(params)})"
    else:
        lines.append(f"    fn = e.fns.get({name!r})")
        lines.append("    if fn is None:")
        lines.append(f"        return CelError({name + ': no callback in fns'!r})")
        call = f"fn({', '.join(params)})"
    lines += ["    try:", f"        return {call}", "    except Exception as exc:  # noqa: BLE001 — ошибка CEL",
              f"        return CelError(f\"{name}: {{exc}}\")"]
    return "\n".join(lines)


def py_filter(row):
    if row["op"] == "*":
        return None
    values = row["op"].split(",")
    return f"type(op) is str and op in {{{', '.join(repr(v) for v in values)}}}"


def py_row_step(row, args, ind):
    pad = "    " * ind
    n = row["n"]
    fault = f", _fault_{n}({args})" if row["fault"] else ""
    lines = [f"{pad}v = _when_{n}({args})",
             f"{pad}steps.append(({n}, _status(v)))",
             f"{pad}if v is True and hit is None:",
             f"{pad}    hit = _refusal({n}, {row['check']!r}, {row['code']}, {row['kind']!r}{fault})",
             f"{pad}    if not full:",
             f"{pad}        return steps, hit"]
    cond = py_filter(row)
    if cond:
        return [f"{pad}# n {n} {row['check']}", f"{pad}if {cond}:"] + ["    " + line for line in lines]
    return [f"{pad}# n {n} {row['check']}"] + lines


def py_driver(table):
    lines = ["def _run(e, full):",
             "    body = e.body",
             "    op = body.get(\"op\") if type(body) is dict else None",
             "    steps, hit = [], None"]
    for item in table.plan():
        if item[0] == "row":
            lines += py_row_step(item[1], "e", 1)
            continue
        (i, x, parts), rows = item[1], item[2]
        lines.append(f"    # group {rows[0]['group']}: {rows[0]['each']}")
        lines.append(f"    xs = _path(body, {tuple(parts)!r})")
        lines.append("    if type(xs) is list:")
        lines.append(f"        for v_{i}, v_{x} in enumerate(xs):")
        for row in rows:
            lines += py_row_step(row, f"e, v_{i}, v_{x}", 3)
        cond = py_filter(rows[0])
        lines.append(f"    elif {cond}:" if cond else "    else:")
        lines.append(f"        steps.append(({rows[0]['n']}, \"error\"))")
    lines.append("    return steps, hit")
    return "\n".join(lines)


PY_API = '''

class _Env:
    __slots__ = ("body", "sock", "lone", "lim", "fns")

    def __init__(self, body, sock, lone, lim, fns):
        self.body, self.sock, self.lone, self.lim, self.fns = body, sock, list(lone), dict(lim), dict(fns or {})


_NOFAULT = object()


def _refusal(n, check_name, code, kind, fault=_NOFAULT):
    out = {"n": n, "check": check_name, "code": code, "kind": kind, "fault": None, "fault_error": None}
    if fault is not _NOFAULT:
        if type(fault) is dict:
            out["fault"] = fault
        else:
            out["fault_error"] = fault.msg if type(fault) is CelError else f"fault is {_kind(fault)}, not map"
    return out


def _path(value, parts):
    for part in parts:
        value = value.get(part) if type(value) is dict else None
    return value


def _cond_err(c):
    return c if type(c) is CelError else _no("?:", c)


def check(body, sock, lone, lim, fns=None):
    """Первый отказ таблицы или None (прошла).

    body — тело после json.loads (строки — с U+FFFD вместо одиночного суррогата); sock — роль сокета; lone — JSON Pointer
    строк с одиночным суррогатом; lim — {имя #lim: int}; fns — внешние #fn без примитива: {имя: функция}.
    Отказ — {"n", "check", "code", "kind", "fault" (dict | None), "fault_error" (str | None)}.
    """
    return _run(_Env(body, sock, lone, lim, fns), False)[1]


def chain(body, sock, lone, lim, fns=None):
    """Вся цепочка без остановки: ([(n, "true" | "false" | "error")], первый отказ | None) — для сверки с оракулом."""
    return _run(_Env(body, sock, lone, lim, fns), True)
'''


def python_module(table, rel, module, compiled, prims):
    runtime = (HERE / "runtime/python/runtime.py").read_text(encoding="utf-8")
    prim_text = (HERE / "prims/python/prims.py").read_text(encoding="utf-8")
    parts = [f"# Code generated by tools/normgen/gen_checks.py from {rel}; DO NOT EDIT.\n"
             f"# Таблица sha256 {table.sha256}.\n"
             "# API: check(body, sock, lone, lim, fns) — первый отказ или None; chain(...) — вся цепочка.\n"
             "import re\n",
             "# ---- среда CEL: tools/normgen/runtime/python/runtime.py\n" + runtime,
             "# ---- примитивы #fn: tools/normgen/prims/python/prims.py\n" + prim_text,
             "# ---- таблица"]
    parts += [f"_RX{k} = re.compile({py!r})  # RE2 {re2!r}" for k, (re2, py) in enumerate(module.regexes, 1)]
    for name, (args, result, doc) in table.fns.items():
        parts.append(py_fn_wrapper(name, args, result, doc, name in prims))
    for row in table.rows:
        params = [f"v_{v}" for v in EACH.fullmatch(row["each"]).groups()[:2]] if row["group"] else []
        parts.append(py_function(f"_when_{row['n']}", params, compiled[row["n"], "when"],
                                 f"n {row['n']} {row['check']}: {row['when']}"))
        if row["fault"]:
            parts.append(py_function(f"_fault_{row['n']}", params, compiled[row["n"], "fault"],
                                     f"n {row['n']} fault: {row['fault']}"))
    parts.append(py_driver(table))
    return "\n\n\n".join(parts).rstrip() + "\n" + PY_API


# ---------------------------------------------------------------- вывод: Go

GO_HELPERS = {"eq": "celEq", "ne": "celNe", "lt": "celLt", "le": "celLe", "gt": "celGt", "ge": "celGe",
              "in": "celIn", "not": "celNot", "select": "celSelect", "has": "celHas", "index": "celIndex",
              "size": "celSize", "string": "celString", "add": "celAdd", "type": "celTypeOf",
              "startswith": "celStartsWith", "matches": "celMatches", "list": "mkList", "map": "mkMap"}
GO_TYPES = {"string": "string", "map": "map[string]any", "double": "float64", "int": "int64", "bool": "bool",
            "list": "[]any", "dyn": "any"}
GO_TYPE_CONST = {"bool": "typeBool", "int": "typeInt", "double": "typeDouble", "string": "typeString",
                 "list": "typeList", "map": "typeMap", "null_type": "typeNull", "type": "typeType"}


def go_str(s):
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch in '"\\':
            out.append("\\" + ch)
        elif o < 0x20 or o == 0x7F:
            out.append(f"\\x{o:02x}")
        else:
            out.append(ch)
    return "".join(out) + '"'


def camel(name):
    return "".join(part[:1].upper() + part[1:] for part in name.split("_"))


def go_operand(op):
    kind = op[0]
    if kind in ("t", "v"):
        return op[1]
    if kind == "lit":
        k, v = op[1], op[2]
        if k == "int":
            return f"int64({v})"
        if k == "double":
            return f"float64({v!r})"
        if k == "string":
            return go_str(v)
        if k == "bool":
            return "true" if v else "false"
        return "nil"
    if kind == "type":
        return GO_TYPE_CONST[op[1]]
    if kind == "rx":
        return f"rx{op[1]}"
    if kind == "str":
        return go_str(op[1])
    if kind == "keys":
        return "[]string{" + ", ".join(go_str(k) for k in op[1]) + "}"
    raise AssertionError(op)


def go_stmts(stmts, ind):
    pad = "\t" * ind
    out = []
    for s in stmts:
        kind = s[0]
        if kind == "set":
            _, t, helper, ops = s
            args = [go_operand(o) for o in ops]
            if isinstance(helper, tuple):
                out.append(f"{pad}{t} = fn{camel(helper[1])}({', '.join(['e'] + args)})")
            else:
                out.append(f"{pad}{t} = {GO_HELPERS[helper]}({', '.join(args)})")
        elif kind in ("or", "and"):
            _, t, ls, lo, rs, ro = s
            lo, ro = go_operand(lo), go_operand(ro)
            test, stop = ("isTrue", "true") if kind == "or" else ("isFalse", "false")
            out += go_stmts(ls, ind)
            out.append(f"{pad}if {test}({lo}) {{")
            out.append(f"{pad}\t{t} = {stop}")
            out.append(f"{pad}}} else {{")
            out += go_stmts(rs, ind + 1)
            out.append(f"{pad}\t{t} = cel{kind.capitalize()}({lo}, {ro})")
            out.append(f"{pad}}}")
        elif kind == "cond":
            _, t, cs, co, xs, xo, ys, yo = s
            co = go_operand(co)
            out += go_stmts(cs, ind)
            out.append(f"{pad}if isTrue({co}) {{")
            out += go_stmts(xs, ind + 1)
            out.append(f"{pad}\t{t} = {go_operand(xo)}")
            out.append(f"{pad}}} else if isFalse({co}) {{")
            out += go_stmts(ys, ind + 1)
            out.append(f"{pad}\t{t} = {go_operand(yo)}")
            out.append(f"{pad}}} else {{")
            out.append(f"{pad}\t{t} = condErr({co})")
            out.append(f"{pad}}}")
        elif kind == "exists":
            _, t, rs, ro, v1, v2, ps, po = s
            r, p, rr = go_operand(ro), go_operand(po), f"r{t}"
            out += go_stmts(rs, ind)
            out.append(f"{pad}switch {rr} := {r}.(type) {{")
            for case in ("[]any", "map[string]any"):
                out.append(f"{pad}case {case}:")
                out.append(f"{pad}\t{t} = false")
                out.append(f"{pad}\t{t}e = nil")
                if case == "[]any":
                    if v2 is None:
                        out.append(f"{pad}\tfor _, {v1} := range {rr} {{")
                        binds = []
                    else:
                        out.append(f"{pad}\tfor k{t}, el{t} := range {rr} {{")
                        binds = [f"{v1} := any(int64(k{t}))", f"{v2} := el{t}"]
                else:
                    if v2 is None:
                        out.append(f"{pad}\tfor k{t} := range {rr} {{")
                        binds = [f"{v1} := any(k{t})"]
                    else:
                        out.append(f"{pad}\tfor k{t}, el{t} := range {rr} {{")
                        binds = [f"{v1} := any(k{t})", f"{v2} := el{t}"]
                out += [f"{pad}\t\t{b}" for b in binds]
                used = [v1] + ([v2] if v2 else [])
                out.append(f"{pad}\t\t{', '.join('_' for _ in used)} = {', '.join(used)}")
                out += go_stmts(ps, ind + 2)
                out.append(f"{pad}\t\tif isTrue({p}) {{")
                out.append(f"{pad}\t\t\t{t} = true")
                out.append(f"{pad}\t\t\tbreak")
                out.append(f"{pad}\t\t}}")
                out.append(f"{pad}\t\tif !isFalse({p}) {{")
                out.append(f"{pad}\t\t\t{t}e = predErr({t}e, {p})")
                out.append(f"{pad}\t\t}}")
                out.append(f"{pad}\t}}")
                out.append(f"{pad}\tif isFalse({t}) && {t}e != nil {{")
                out.append(f"{pad}\t\t{t} = {t}e")
                out.append(f"{pad}\t}}")
            out.append(f"{pad}default:")
            out.append(f"{pad}\t{t} = rangeErr({r})")
            out.append(f"{pad}}}")
        else:
            raise AssertionError(s)
    return out


def go_function(name, params, compiled, doc):
    stmts, result, temps = compiled
    sig = ", ".join(["e *env"] + ([", ".join(params) + " any"] if params else []))
    lines = [f"// {name} — {doc}", f"func {name}({sig}) any {{"]
    if temps:
        lines.append(f"\tvar {', '.join(temps)} any")
    lines += go_stmts(stmts, 1)
    lines.append(f"\treturn {go_operand(result)}")
    lines.append("}")
    return "\n".join(lines)


def go_fn_wrapper(name, args, result, doc, prim):
    params = [f"a{k}" for k in range(len(args))]
    lines = [f"// fn{camel(name)} — #fn {name}({', '.join(args)}) -> {result} — {doc}",
             f"func fn{camel(name)}(e *env{''.join(', ' + p for p in params)} any) any {{"]
    for p in params:
        lines += [f"\tif isErr({p}) {{", f"\t\treturn {p}", "\t}"]
    xs = []
    for k, (p, t) in enumerate(zip(params, args)):
        if t == "dyn":
            xs.append(p)
            continue
        lines += [f"\tx{k}, ok{k} := {p}.({GO_TYPES[t]})", f"\tif !ok{k} {{",
                  f"\t\treturn noOverload({go_str(name)}{''.join(', ' + q for q in params)})", "\t}"]
        xs.append(f"x{k}")
    if prim:
        lines += [f"\tr, err := prim{camel(name)}({', '.join(xs)})", "\tif err != nil {",
                  f"\t\treturn errf(\"{name}: %v\", err)", "\t}", "\treturn r", "}"]
    else:
        lines += [f"\tif e.fns.{camel(name)} == nil {{", f"\t\treturn errf(\"{name}: no callback in Fns\")", "\t}",
                  f"\treturn e.fns.{camel(name)}({', '.join(xs)})", "}"]
    return "\n".join(lines)


def go_filter(row):
    if row["op"] == "*":
        return None
    return " || ".join(f"opStr == {go_str(v)}" for v in row["op"].split(","))


def go_row_step(row, args, ind):
    pad = "\t" * ind
    n = row["n"]
    fault = f"fault{n}({args}), true" if row["fault"] else "nil, false"
    body = [f"v = when{n}({args})",
            f"steps = append(steps, Step{{{n}, status(v)}})",
            "if hit == nil && isTrue(v) {",
            f"\thit = refusal({n}, {go_str(row['check'])}, {row['code']}, {go_str(row['kind'])}, {fault})",
            "\tif !full {", "\t\treturn steps, hit", "\t}", "}"]
    cond = go_filter(row)
    if cond:
        return [f"{pad}// n {n} {row['check']}", f"{pad}if {cond} {{"] + [f"{pad}\t{b}" for b in body] + [f"{pad}}}"]
    return [f"{pad}// n {n} {row['check']}"] + [f"{pad}{b}" for b in body]


def go_driver(table):
    lines = ["func run(in Input, full bool) ([]Step, *Refusal) {",
             "\te := newEnv(in)",
             "\tvar op any",
             "\tif m, ok := in.Body.(map[string]any); ok {",
             "\t\top = m[\"op\"]",
             "\t}",
             "\topStr, _ := op.(string)",
             "\t_ = opStr",
             "\tvar steps []Step",
             "\tvar hit *Refusal",
             "\tvar v any"]
    for item in table.plan():
        if item[0] == "row":
            lines += go_row_step(item[1], "e", 1)
            continue
        (i, x, parts), rows = item[1], item[2]
        lines.append(f"\t// group {rows[0]['group']}: {rows[0]['each']}")
        lines.append(f"\tif xs, ok := path(in.Body, {', '.join(go_str(p) for p in parts)}).([]any); ok {{")
        lines.append("\t\tfor k, el := range xs {")
        lines.append(f"\t\t\tv_{i}, v_{x} := any(int64(k)), el")
        for row in rows:
            lines += go_row_step(row, f"e, v_{i}, v_{x}", 3)
        lines.append("\t\t}")
        cond = go_filter(rows[0])
        lines.append(f"\t}} else if {cond} {{" if cond else "\t} else {")
        lines.append(f"\t\tsteps = append(steps, Step{{{rows[0]['n']}, \"error\"}})")
        lines.append("\t}")
    lines += ["\treturn steps, hit", "}"]
    return "\n".join(lines)


GO_API = '''
// Fns — внешние #fn без примитива в prims.go: их даёт вызывающий.
type Fns struct {
%s}

// Input — вход таблицы: тело уже разобрано как JSON по Н2.1.
type Input struct {
	// Body — JSON тела: nil, bool, int64, float64, string, []any, map[string]any; число без . и e в пределах int64 —
	// int64, иначе float64; строки — с U+FFFD вместо одиночного суррогата.
	Body any
	Sock string            // роль сокета вызывающего
	Lone []string          // JSON Pointer каждой строки тела с одиночным суррогатом
	Lim  map[string]int64  // параметры урока, имена #lim
	Fns  Fns
}

// Refusal — первый отказ: строка n, её check, code, kind и поля fault.
type Refusal struct {
	N        int
	Check    string
	Code     int
	Kind     string
	Fault    map[string]any // nil — у строки нет fault
	FaultErr string         // не пусто — fault не вычислился (ошибка CEL или не отображение)
}

// Step — шаг цепочки: строка n и исход её when: "true", "false" или "error".
type Step struct {
	N      int
	Status string
}

// Check — первый отказ таблицы или nil (команда идёт дальше).
func Check(in Input) *Refusal {
	_, hit := run(in, false)
	return hit
}

// Chain — вся цепочка без остановки и первый отказ — для сверки с оракулом.
func Chain(in Input) ([]Step, *Refusal) {
	return run(in, true)
}

type env struct {
	body, sock, lone, lim any
	fns                   Fns
}

func newEnv(in Input) *env {
	lone := make([]any, len(in.Lone))
	for k, p := range in.Lone {
		lone[k] = p
	}
	lim := make(map[string]any, len(in.Lim))
	for k, x := range in.Lim {
		lim[k] = x
	}
	return &env{body: in.Body, sock: in.Sock, lone: lone, lim: lim, fns: in.Fns}
}

func refusal(n int, check string, code int, kind string, fault any, hasFault bool) *Refusal {
	r := &Refusal{N: n, Check: check, Code: code, Kind: kind}
	if hasFault {
		if m, ok := fault.(map[string]any); ok {
			r.Fault = m
		} else {
			r.FaultErr = errText(fault)
		}
	}
	return r
}

func path(v any, parts ...string) any {
	for _, part := range parts {
		m, ok := v.(map[string]any)
		if !ok {
			return nil
		}
		v = m[part]
	}
	return v
}

func condErr(c any) any {
	if isErr(c) {
		return c
	}
	return noOverload("?:", c)
}
'''


def go_module(table, rel, module, compiled, prims):
    fields = ""
    for name, (args, result, doc) in table.fns.items():
        if name not in prims:
            fields += (f"\t// {camel(name)} — #fn {name}({', '.join(args)}) -> {result} — {doc}\n"
                       f"\t{camel(name)} func({', '.join(GO_TYPES[a] for a in args)}) {GO_TYPES[result]}\n")
    parts = [f"// Code generated by tools/normgen/gen_checks.py from {rel}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}.\n\n"
             "// Package checks — порядок проверок таблицы ADR-0120 п. 2 (а): Check — первый отказ, Chain — вся цепочка.\n"
             "package checks\n\n"
             + ('import "regexp"\n' if module.regexes else ""),
             GO_API.strip("\n") % fields]
    if module.regexes:
        parts.append("var (\n" + "".join(f"\trx{k} = regexp.MustCompile({go_str(re2)})\n"
                                         for k, (re2, _) in enumerate(module.regexes, 1)) + ")")
    for name, (args, result, doc) in table.fns.items():
        parts.append(go_fn_wrapper(name, args, result, doc, name in prims))
    for row in table.rows:
        params = [f"v_{v}" for v in EACH.fullmatch(row["each"]).groups()[:2]] if row["group"] else []
        parts.append(go_function(f"when{row['n']}", params, compiled[row["n"], "when"],
                                 f"n {row['n']} {row['check']}: {row['when']}"))
        if row["fault"]:
            parts.append(go_function(f"fault{row['n']}", params, compiled[row["n"], "fault"],
                                     f"n {row['n']} fault: {row['fault']}"))
    parts.append(go_driver(table))
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- сборка

def prims_present():
    """Имена #fn, у которых есть примитив; примитив должен быть в обоих языках."""
    py = set(re.findall(r"^def prim_([a-z_]+)\(", (HERE / "prims/python/prims.py").read_text(), re.M))
    go = set(re.findall(r"^func prim([A-Za-z]+)\(", (HERE / "prims/go/prims.go").read_text(), re.M))
    return py, go


def build(table, rel="table"):
    """→ (исходник Go checks.go, исходник Python checks.py); GenError — таблица вне подмножества."""
    py_prims, go_prims = prims_present()
    prims = set()
    for name in table.fns:
        if (name in py_prims) != (camel(name) in go_prims):
            raise GenError(f"{table.name}: #fn {name}: primitive in one language only")
        if name in py_prims:
            prims.add(name)
    module, compiled = Module(), {}
    for row in table.rows:
        bound = {}
        if row["group"]:
            i, x, _ = EACH.fullmatch(row["each"]).groups()
            bound = {i: f"v_{i}", x: f"v_{x}"}
        for column in ("when", "fault"):
            if row[column]:
                where = f"{table.name}: n {row['n']}: {column}"
                compiled[row["n"], column] = compile_expr(table, module, where, row[column], bound)
        if row["fault"]:
            fault = Parser(row["fault"], f"{table.name}: n {row['n']}: fault").parse()
            if fault.kind != "map":
                raise GenError(f"{table.name}: n {row['n']}: fault must be a map literal")
    return go_module(table, rel, module, compiled, prims), python_module(table, rel, module, compiled, prims)


def gofmt(src):
    exe = shutil.which("gofmt")
    if not exe:
        raise GenError("gofmt is not in PATH")
    done = subprocess.run([exe], input=src, capture_output=True, text=True)
    if done.returncode:
        raise GenError(f"gofmt rejects generated Go: {done.stderr}")
    return done.stdout


GO_MOD = "module normgen/{name}\n\ngo 1.22\n"


def generate(table_path=DEFAULT_TABLE, out=DEFAULT_OUT):
    table_path, out = Path(table_path).resolve(), Path(out)
    try:
        rel = table_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = table_path.name
    table = Table(table_path.read_text(encoding="utf-8"), table_path.name)
    go_src, py_src = build(table, rel)
    gdir, pdir = out / "go/checks", out / "python"
    gdir.mkdir(parents=True, exist_ok=True)
    pdir.mkdir(parents=True, exist_ok=True)
    (out / "go/go.mod").write_text(GO_MOD.format(name=out.name), encoding="utf-8")
    (gdir / "checks.go").write_text(gofmt(go_src), encoding="utf-8")
    for name, src in (("runtime.go", HERE / "runtime/go/runtime.go"), ("prims.go", HERE / "prims/go/prims.go")):
        text = src.read_text(encoding="utf-8")
        head = f"// Code generated by tools/normgen/gen_checks.py: copy of tools/normgen/{src.relative_to(HERE)}; DO NOT EDIT.\n\n"
        (gdir / name).write_text(gofmt(head + text), encoding="utf-8")
    (pdir / "checks.py").write_text(py_src, encoding="utf-8")
    return out


def main(argv):
    table = argv[1] if len(argv) > 1 else DEFAULT_TABLE
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        print(generate(table, out))
    except GenError as exc:
        print(f"gen_checks: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
