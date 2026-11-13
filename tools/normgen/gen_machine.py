"""Generate lesson machines: P/03 slot-capture and P/04 slot-fate/slot-release (ADR-0125 addendum (5)).

  python3 tools/normgen/gen_machine.py --lesson 03-worker [<part> ...] [--out <out>] [--root <course-root>]
Default: all machines, out/pNN. --root permits alternate forms for judge mutants. A forms/<part>.tsv table declares n, state, condition, action, next, norm plus states, Initial, #var, #const and #action headers. Select the first matching row in the current state; no match waits without effect. An action '-' is a YOURS normative procedure, not a no-op. Conditions and arguments use generator 1's typed CEL parser: boolean operators, comparisons, +, ternary, literals and string-keyed maps. Unsupported syntax refuses with the form row. Integer addition is allowed only in arguments and reports CEL-style overflow.

Emit closed <package>/machine.go: State, In fields, constants, Step(state, in), Actions and Apply. Step selects a transition but does not execute events, reads or effects. Form tests cover the first enumerated input for each variable-value/outcome pair, including no match. Numeric boundaries come from constants and uppercase #var settings bound to daemon-flags.tsv defaults. Emit inventory.tsv and YOURS <package>impl/actions.go plus one file per action or '-' procedure, installed once and initially returning not in this stage. test_gen_machine.py independently evaluates the form with cel_expr_python and mutants over the same enumeration."""
import hashlib
import itertools
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402
from gen_checks import GenError as _CelError, Parser, go_str, gofmt  # noqa: E402

L = lesson.CURRENT
DEFAULT_OUT = L.out
GO_MODULE = L.go_module
COLUMNS = ["n", "state", "condition", "action", "next", "norm"]
TYPES = {"bool", "int", "double", "string"}
ARG_TYPES = TYPES | {"map<string,dyn>"}
GO_TYPE = {"bool": "bool", "int": "int64", "double": "float64", "string": "string", "map<string,dyn>": "map[string]any"}
NORM = re.compile(r"P/\d\d(?:\.\d+)?-R\d{3}")
NAME = re.compile(r"[a-z][a-z0-9_]*")
INT_MIN, INT_MAX = -2 ** 63, 2 ** 63 - 1
EPS = {"double": 0.001, "int": 1}


class GenError(Exception):
    pass


def camel(name):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_]", name.lower() if name.isupper() else name) if w)


def sconst(state):
    return "State" + camel(state)


def package(part):
    return part.replace("-", "")


# ---------------------------------------------------------------- form

class Machine:
    def __init__(self, part, text, rel):
        self.part, self.rel, self.pkg = part, rel, package(part)
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.vars, self.consts, self.actions, self.rows = {}, {}, {}, []
        self.states, self.initial, self.terminal_said, self.yours_doc = None, None, None, []
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        head = [ln for ln in lines if ln.startswith("#")]
        body = [ln for ln in lines if not ln.startswith("#")]
        after_dash = False
        for line in head:
            where = f"{rel}: {line[:40]!r}"
            if m := re.match(r"# states: ([a-z_,]+)\.", line):
                self.states = m[1].split(",")
                if mi := re.search(r"\bInitial:? ([a-z_]+)", line):
                    self.initial = mi[1]
                if mt := re.search(r"\bTerminal: ([a-z_,]+)", line):
                    self.terminal_said = mt[1].split(",")
            elif m := re.fullmatch(r"#var (\w+) (\w+) — (.*)", line):
                if m[2] not in TYPES:
                    raise GenError(f"{where}: #var type {m[2]!r} — one of {sorted(TYPES)}")
                self.vars[m[1]] = (m[2], m[3])
            elif m := re.fullmatch(r"#const ([A-Z][A-Z0-9_]*) (\w+) = (\S+) — (.*)", line):
                if m[2] not in ("int", "double"):
                    raise GenError(f"{where}: #const type {m[2]!r} — int or double")
                value = float(m[3]) if m[2] == "double" else int(m[3])
                self.consts[m[1]] = (m[2], value, m[3], m[4])
            elif m := re.fullmatch(r"#action ([a-z_]+)\(([^)]*)\) — (.*)", line):
                args = [a.strip() for a in re.split(r",(?![^<]*>)", m[2]) if a.strip()]
                for a in args:
                    if a not in ARG_TYPES:
                        raise GenError(f"{where}: #action {m[1]} argument type {a!r} — one of {sorted(ARG_TYPES)}")
                self.actions[m[1]] = (args, m[3])
            elif re.match(r"#(var|const|action) ", line):
                raise GenError(f"{where}: header line out of form")
            elif line.startswith("# action=-"):
                after_dash = True
                self.yours_doc.append(line[2:])
            elif after_dash and line.startswith("# "):
                self.yours_doc.append(line[2:])
        if not self.states or not self.initial:
            raise GenError(f"{rel}: the header needs «# states: a,b,…. Initial <state>»")
        if self.initial not in self.states:
            raise GenError(f"{rel}: initial {self.initial!r} is not a state")
        clash = set(self.vars) & set(self.consts)
        if clash:
            raise GenError(f"{rel}: {sorted(clash)} are both #var and #const")
        if not body or body[0].split("\t") != COLUMNS:
            raise GenError(f"{rel}: columns must be {COLUMNS}")
        for k, line in enumerate(body[1:], 1):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                raise GenError(f"{rel}: row {k}: {len(cells)} cells, expected {len(COLUMNS)}")
            row = dict(zip(COLUMNS, cells))
            where = f"{rel}: n {row['n']}"
            if row["n"] != str(k):
                raise GenError(f"{where}: n must be {k}")
            if row["state"] not in self.states or row["next"] not in self.states:
                raise GenError(f"{where}: state/next {row['state']!r}/{row['next']!r} — the closed states {self.states}")
            if not NORM.fullmatch(row["norm"]):
                raise GenError(f"{where}: norm {row['norm']!r} — an anchor P/NN[.K]-RNNN")
            row["n"] = k
            row["cond_ast"] = self.parse(row["condition"], f"{where} condition")
            if self.type_of(row["cond_ast"], f"{where} condition", cond=True) != "bool":
                raise GenError(f"{where}: condition is not bool")
            if row["action"] == "-":
                row["act"], row["args"] = None, []
            else:
                m = re.fullmatch(r"([a-z_]+)\((.*)\)", row["action"])
                if not m or m[1] not in self.actions:
                    raise GenError(f"{where}: action {row['action'][:30]!r} — «-» or a declared #action")
                row["act"] = m[1]
                call = self.parse(f"f({m[2]})", f"{where} action")
                row["args"] = list(call.args[1])
                want = self.actions[m[1]][0]
                if len(row["args"]) != len(want):
                    raise GenError(f"{where}: {m[1]} takes {len(want)} arguments, got {len(row['args'])}")
                for a, t in zip(row["args"], want):
                    got = self.type_of(a, f"{where} action")
                    if got != t:
                        raise GenError(f"{where}: {m[1]} argument is {got}, want {t}")
            self.rows.append(row)
        self.from_states = [s for s in self.states if any(r["state"] == s for r in self.rows)]
        self.terminal = [s for s in self.states if s not in self.from_states]
        if self.terminal_said is not None and sorted(self.terminal_said) != sorted(self.terminal):
            raise GenError(f"{rel}: Terminal {self.terminal_said} differs from the states without rows {self.terminal}")
        if self.initial in self.terminal:
            raise GenError(f"{rel}: initial {self.initial!r} has no rows")
        self.procs = []                       # YOURS procedures: (method, state, next, norm, row numbers).
        for row in self.rows:
            if row["act"] is None:
                name = f"{camel(row['state'])}To{camel(row['next'])}"
                for p in self.procs:
                    if p[0] == name:
                        if p[3] != row["norm"]:
                            raise GenError(f"{rel}: n {row['n']}: «-» {row['state']}→{row['next']} with two norms")
                        p[4].append(row["n"])
                        break
                else:
                    self.procs.append((name, row["state"], row["next"], row["norm"], [row["n"]]))
                row["proc"] = name

    def parse(self, text, where):
        try:
            return Parser(text, where).parse()
        except _CelError as exc:
            raise GenError(str(exc)) from None

    # Types.
    def type_of(self, node, where, cond=False):
        k, a = node.kind, node.args
        if k == "lit":
            if a[0] == "null":
                raise GenError(f"{where}: null is out of the subset")
            return a[0]
        if k == "ident":
            if a[0] in self.vars:
                return self.vars[a[0]][0]
            if a[0] in self.consts:
                return self.consts[a[0]][0]
            raise GenError(f"{where}: {a[0]} is not declared (#var, #const)")
        if k == "not":
            if self.type_of(a[0], where, cond) != "bool":
                raise GenError(f"{where}: ! over a non-bool")
            return "bool"
        if k == "bin":
            op, left, right = a
            lt, rt = self.type_of(left, where, cond), self.type_of(right, where, cond)
            if op in ("&&", "||"):
                if lt != "bool" or rt != "bool":
                    raise GenError(f"{where}: {op} over non-bool")
                return "bool"
            if lt != rt:
                raise GenError(f"{where}: {op} over {lt} and {rt} (no implicit conversion)")
            if op == "+":
                if lt not in ("int", "double", "string"):
                    raise GenError(f"{where}: + over {lt}")
                if lt == "int" and cond:
                    raise GenError(f"{where}: int arithmetic in a condition is out of the subset (overflow is a CEL error)")
                return lt
            if op in ("==", "!="):
                return "bool"
            if op in ("<", "<=", ">", ">="):
                if lt == "bool":
                    raise GenError(f"{where}: {op} over bool")
                return "bool"
            raise GenError(f"{where}: operator {op} is out of the subset")
        if k == "cond":
            if self.type_of(a[0], where, cond) != "bool":
                raise GenError(f"{where}: ?: condition is not bool")
            x, y = self.type_of(a[1], where, cond), self.type_of(a[2], where, cond)
            if x != y:
                raise GenError(f"{where}: ?: branches {x} and {y}")
            return x
        if k == "map":
            keys = []
            for key, value in a[0]:
                if key.kind != "lit" or key.args[0] != "string":
                    raise GenError(f"{where}: map keys must be string literals")
                if key.args[1] in keys:
                    raise GenError(f"{where}: duplicate map key {key.args[1]!r}")
                keys.append(key.args[1])
                self.type_of(value, where, cond)
            return "map<string,dyn>"
        raise GenError(f"{where}: {k} is out of the machine subset")

    def idents(self, node, out=None):
        out = set() if out is None else out
        if node.kind == "ident":
            out.add(node.args[0])
        for a in node.args:
            if hasattr(a, "kind"):
                self.idents(a, out)
            elif isinstance(a, (list, tuple)):
                for b in a:
                    if hasattr(b, "kind"):
                        self.idents(b, out)
                    elif isinstance(b, tuple):
                        for c in b:
                            if hasattr(c, "kind"):
                                self.idents(c, out)
        return out


def machine_forms(root=ROOT, lesson_=None):
    """Return {part: path} for lesson forms with machine columns."""
    les = lesson_ or L
    out = {}
    for p in sorted((Path(root) / les.rel / "forms").glob("*.tsv")):
        first = next((ln for ln in p.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")), "")
        if first.split("\t") == COLUMNS:
            out[p.stem] = p
    return out


def read(part, root=ROOT):
    forms = machine_forms(root)
    if part not in forms:
        raise GenError(f"{L.rel}/forms: no machine form {part}.tsv (machines: {', '.join(forms) or 'none'})")
    p = forms[part]
    m = Machine(part, p.read_text(encoding="utf-8"), str(p.relative_to(Path(root))))
    m.setting_defaults = {}
    flags = p.parent / "daemon-flags.tsv"
    if flags.is_file():
        import tsv_input
        try:
            table = tsv_input.read(flags, root=root)
        except tsv_input.TSVError as exc:
            raise GenError(str(exc)) from None
        for _, row in table.rows:
            name = row["flag"].removeprefix("$")
            if name not in m.vars or not name.isupper():
                continue
            typ = m.vars[name][0]
            try:
                value = int(row["default"]) if typ == "int" else float(row["default"])
            except ValueError:
                raise GenError(f"{flags}: {name}: numeric default required") from None
            if typ not in ("int", "double") or (typ == "int" and not INT_MIN <= value <= INT_MAX) or (typ == "double" and not math.isfinite(value)):
                raise GenError(f"{flags}: {name}: default is not a finite {typ}")
            m.setting_defaults[name] = value
    return m


# ---------------------------------------------------------------- generator enumeration

class Overflow(Exception):
    pass


def ev(m, node, env):
    k, a = node.kind, node.args
    if k == "lit":
        return a[1]
    if k == "ident":
        return env[a[0]] if a[0] in m.vars else m.consts[a[0]][1]
    if k == "not":
        return not ev(m, a[0], env)
    if k == "cond":
        return ev(m, a[1], env) if ev(m, a[0], env) else ev(m, a[2], env)
    if k == "map":
        return {key.args[1]: ev(m, v, env) for key, v in a[0]}
    op, left, right = a
    if op == "&&":
        return ev(m, left, env) and ev(m, right, env)
    if op == "||":
        return ev(m, left, env) or ev(m, right, env)
    x, y = ev(m, left, env), ev(m, right, env)
    if op == "+":
        r = x + y
        if isinstance(r, int) and not isinstance(r, bool) and not INT_MIN <= r <= INT_MAX:
            raise Overflow()
        return r
    return {"==": x == y, "!=": x != y, "<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]


def setting(m, name):
    """Use the machine's setting default from daemon-flags, or an explicit inline default."""
    if name in getattr(m, "setting_defaults", {}):
        return m.setting_defaults[name]
    t, doc = m.vars[name]
    d = re.search(r"\bdefault (\d+(?:\.\d+)?)", doc)
    if not d:
        raise GenError(f"{m.rel}: {name}: no default in daemon-flags.tsv or its #var description")
    v = float(d[1])
    return v if t == "double" else int(v)


def enumerated(doc):
    d = re.match(r"([a-z_]+(?:\|[a-z_]+)+)\b", doc)
    return d[1].split("|") if d else None


def domains(m, state):
    """Return {var: enumerated values} and {var: fixed value} for a state."""
    rows = [r for r in m.rows if r["state"] == state]
    cond_ids, arg_ids = set(), set()
    for r in rows:
        m.idents(r["cond_ast"], cond_ids)
        for a in r["args"]:
            m.idents(a, arg_ids)
    fixed, dom = {}, {}
    for name, (t, doc) in m.vars.items():
        if name.isupper():
            fixed[name] = setting(m, name)
            continue
        relevant = name in cond_ids or (name in arg_ids and (t == "bool" or enumerated(doc)))
        if not relevant:
            fixed[name] = {"bool": False, "int": 7, "double": 1000.0, "string": f"{name}-1"}[t]
            if t == "string" and enumerated(doc):
                fixed[name] = enumerated(doc)[0]
            continue
        if t == "bool":
            dom[name] = [False, True]
        elif t == "string":
            values = enumerated(doc)
            if values is None:
                values = sorted({lit for r in rows for lit in string_literals(m, r["cond_ast"], name)}) + [f"{name}-1"]
            dom[name] = values
        else:
            th = set()
            for r in rows:
                for c in thresholds(m, r["cond_ast"], name, fixed_settings(m)):
                    th.update({c - EPS[t], c, c + EPS[t]})
            zero = 0.0 if t == "double" else 0
            dom[name] = sorted({zero} | {round(x, 6) if t == "double" else x for x in th if x >= zero})
    return dom, fixed


def fixed_settings(m):
    return {n: setting(m, n) for n in m.vars if n.isupper()}


def string_literals(m, node, name):
    out = []
    if node.kind == "bin" and node.args[0] in ("==", "!="):
        l, r = node.args[1], node.args[2]
        for x, y in ((l, r), (r, l)):
            if x.kind == "ident" and x.args[0] == name and y.kind == "lit" and y.args[0] == "string":
                out.append(y.args[1])
    for a in node.args:
        if hasattr(a, "kind"):
            out += string_literals(m, a, name)
    return out


def constant(m, node, settings):
    ids = m.idents(node)
    if any(i in m.vars and i not in settings for i in ids):
        return None
    return ev(m, node, settings)


def thresholds(m, node, name, settings):
    out = []
    if node.kind == "bin" and node.args[0] in ("<", "<=", ">", ">=", "==", "!="):
        l, r = node.args[1], node.args[2]
        for x, y in ((l, r), (r, l)):
            if x.kind == "ident" and x.args[0] == name:
                c = constant(m, y, settings)
                if c is not None:
                    out.append(c)
    for a in node.args:
        if hasattr(a, "kind"):
            out += thresholds(m, a, name, settings)
    return out


def outcome(m, state, env):
    """Return (row or None, arguments or Overflow)."""
    for r in m.rows:
        if r["state"] == state and ev(m, r["cond_ast"], env):
            try:
                return r["n"], [ev(m, a, env) for a in r["args"]]
            except Overflow:
                return r["n"], Overflow
    return None, []


def cases(m):
    """Return the first (state, env, row-or-None, args) for each variable-value/outcome pair."""
    out = []
    for state in m.from_states:
        dom, fixed = domains(m, state)
        names = list(dom)
        seen, reached = set(), set()
        for values in itertools.product(*(dom[n] for n in names)):
            env = dict(fixed, **dict(zip(names, values)))
            row, args = outcome(m, state, env)
            reached.add(row)
            keys = [(n, v, row) for n, v in zip(names, values)] or [(None, None, row)]
            if all(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append((state, env, row, args))
        for r in m.rows:
            if r["state"] == state and r["n"] not in reached:
                raise GenError(f"{m.rel}: n {r['n']} is never the first match of {state} over the enumerated inputs "
                               f"({', '.join(f'{n}∈{dom[n]}' for n in names)}) — a shadowed row")
    return out


# ---------------------------------------------------------------- Go output

def go_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"int64({v})"
    if isinstance(v, float):
        return f"float64({v!r})"
    if isinstance(v, str):
        return go_str(v)
    if isinstance(v, dict):
        return "map[string]any{" + ", ".join(f"{go_str(k)}: {go_value(x)}" for k, x in v.items()) + "}"
    raise GenError(f"value {v!r}")


def go_expr(m, node, cond):
    """Emit a Go expression; integer argument addition uses addInt(&err, ...)."""
    k, a = node.kind, node.args
    if k == "lit":
        return go_str(a[1]) if a[0] == "string" else ("true" if a[1] is True else "false" if a[1] is False
                                                       else repr(a[1]) if a[0] == "double" else str(a[1]))
    if k == "ident":
        return f"in.{camel(a[0])}" if a[0] in m.vars else camel(a[0])
    if k == "not":
        return f"!({go_expr(m, a[0], cond)})"
    if k == "cond":
        t = GO_TYPE[m.type_of(a[1], "")]
        return (f"func() {t} {{ if {go_expr(m, a[0], cond)} {{ return {go_expr(m, a[1], cond)} }}; "
                f"return {go_expr(m, a[2], cond)} }}()")
    if k == "map":
        return "map[string]any{" + ", ".join(f"{go_str(key.args[1])}: {go_expr(m, v, cond)}" for key, v in a[0]) + "}"
    op, left, right = a
    if op == "+" and m.type_of(left, "") == "int":
        return f"addInt(&err, {go_expr(m, left, cond)}, {go_expr(m, right, cond)})"
    return f"({go_expr(m, left, cond)} {op} {go_expr(m, right, cond)})"


def go_machine(m):
    gen = f"// Code generated by tools/normgen/gen_machine.py from {m.rel} (kit part {m.part}); DO NOT EDIT."
    out = [gen, "",
           f"// Package {m.pkg} — the transition choice of the machine {m.part} ({m.rel}): the first matching row of the",
           "// current state wins; no match waits without an effect. It does not run the machine: reads, events and the",
           "// effects of the actions are core's (Actions, yours). A row with action «-» is a YOURS procedure at its norm,",
           "// never a noop: Apply calls it and it must finish before the next event is accepted.",
           f"package {m.pkg}", "", 'import (\n\t"errors"\n\t"fmt"\n\t"math"\n)', "",
           "// State is a closed state of the machine.", "type State string", "", "const ("]
    for s in m.states:
        out.append(f"\t{sconst(s)} State = {go_str(s)}")
    out += [")", "", f"// Initial is the initial state ({m.initial}).", f"const Initial = {sconst(m.initial)}", "",
            "// States lists the closed states in form order.",
            "var States = []State{" + ", ".join(sconst(s) for s in m.states) + "}", "",
            "// Terminal reports a state without rows (" + ", ".join(m.terminal) + ").",
            "func Terminal(s State) bool {", "\tswitch s {",
            f"\tcase {', '.join(sconst(s) for s in m.terminal)}:", "\t\treturn true", "\t}", "\treturn false", "}", ""]
    if m.consts:
        out.append("const (")
        for name, (t, _, text, doc) in m.consts.items():
            out.append(f"\t// {camel(name)} — #const {name}: {doc}")
            out.append(f"\t{camel(name)} {GO_TYPE[t]} = {text}")
        out += [")", ""]
    out += ["// In holds the typed inputs (#var) of one choice; core derives them by the norms named in each comment.",
            "type In struct {"]
    for name, (t, doc) in m.vars.items():
        out.append(f"\t// {camel(name)} — #var {name} {t}: {doc}")
        out.append(f"\t{camel(name)} {GO_TYPE[t]}")
    out += ["}", "",
            "// Move is a chosen transition: Row of the form, Action (\"\" for a YOURS procedure «-», then Proc names it),",
            "// its evaluated Args, Next and the Norm anchor.",
            "type Move struct {", "\tRow    int", "\tAction string", "\tProc   string", "\tArgs   []any", "\tNext   State",
            "\tNorm   string", "}", "",
            "// ErrOverflow — an int argument overflowed int64 (a CEL error): no transition is taken.",
            'var ErrOverflow = errors.New("' + m.pkg + ': int overflow in an action argument")', "",
            "func addInt(err *error, a, b int64) int64 {",
            "\tif (b > 0 && a > math.MaxInt64-b) || (b < 0 && a < math.MinInt64-b) {", "\t\t*err = ErrOverflow",
            "\t\treturn 0", "\t}", "\treturn a + b", "}", "",
            "// Step chooses the transition of state s for in: (move, true, nil) — the first matching row; (Move{}, false,",
            "// nil) — no row matches: stay and wait for input, no effect; an error — an argument cannot be evaluated or",
            "// s is not a state.",
            "func Step(s State, in In) (Move, bool, error) {", "\tvar err error", "\t_ = err", "\tswitch s {"]
    for s in m.states:
        rows = [r for r in m.rows if r["state"] == s]
        out.append(f"\tcase {sconst(s)}:")
        for r in rows:
            args = ", ".join(go_expr(m, a, False) for a in r["args"])
            cond = go_expr(m, r['cond_ast'], True)
            out.append(f"\t\tif {cond} {{ // n {r['n']}" if cond != "true" else f"\t\t{{ // n {r['n']}: true")
            out.append(f"\t\t\targs := []any{{{args}}}")
            if "addInt(" in args:
                out.append("\t\t\tif err != nil {\n\t\t\t\treturn Move{}, false, err\n\t\t\t}")
            out.append(f"\t\t\treturn Move{{Row: {r['n']}, Action: {go_str(r['act'] or '')}, "
                       f"Proc: {go_str(r.get('proc', ''))}, Args: args, Next: {sconst(r['next'])}, Norm: {go_str(r['norm'])}}}, true, nil")
            out.append("\t\t}")
        if not rows or rows[-1]["condition"] != "true":
            out.append("\t\treturn Move{}, false, nil")
    out += ["\t}", f'\treturn Move{{}}, false, fmt.Errorf("{m.pkg}: state %q is not a state of the machine", s)', "}", ""]
    out += ["// Actions are the effects of the transitions — yours (" + m.pkg + "impl): one method per #action and one per",
            "// YOURS procedure «-» of the form.", "type Actions interface {"]
    for name, (args, doc) in m.actions.items():
        params = ", ".join(f"a{i} {GO_TYPE[t]}" for i, t in enumerate(args))
        out.append(f"\t// {camel(name)} — #action {name}: {doc}")
        out.append(f"\t{camel(name)}({params}) error")
    for name, s, nxt, norm, ns in m.procs:
        out.append(f"\t// {name} — the YOURS procedure of rows {', '.join(map(str, ns))} ({s} → {nxt}) at {norm}.")
        out.append(f"\t{name}(in In) error")
    out += ["}", "", "// Apply calls the action of m on a: a typed #action with m.Args, or the YOURS procedure with in.",
            "func Apply(a Actions, in In, m Move) error {", "\tswitch {"]
    for name, (args, _) in m.actions.items():
        conv = ", ".join(f"m.Args[{i}].({GO_TYPE[t]})" for i, t in enumerate(args))
        out.append(f"\tcase m.Action == {go_str(name)} && len(m.Args) == {len(args)}:")
        out.append(f"\t\treturn a.{camel(name)}({conv})")
    for name, *_ in m.procs:
        out.append(f'\tcase m.Action == "" && m.Proc == {go_str(name)}:')
        out.append(f"\t\treturn a.{name}(in)")
    out += ["\t}", f'\treturn fmt.Errorf("{m.pkg}: move of row %d has no action", m.Row)', "}", ""]
    return gofmt("\n".join(out))


def go_in(m, env):
    return "In{" + ", ".join(f"{camel(n)}: {go_value(env[n])}" for n in m.vars) + "}"


def go_tests(m, cs):
    out = [f"// Code generated by tools/normgen/gen_machine.py from {m.rel} (kit part {m.part}); DO NOT EDIT.", "",
           f"package {m.pkg}", "", 'import (\n\t"errors"\n\t"reflect"\n\t"testing"\n)', "",
           "type formCase struct {", "\tstate State", "\tin    In", "\tok    bool", "\trow   int", "\targs  []any",
           "\toverflow bool", "}", "",
           "// The form's choices: per state, for each value of each input and each outcome (a row or no match), the first",
           "// input of the enumeration with that outcome.", "var formCases = []formCase{"]
    for state, env, row, args in cs:
        ok = row is not None
        ovf = args is Overflow
        a = "nil" if ovf or not ok else "[]any{" + ", ".join(go_value(x) for x in args) + "}"
        out.append(f"\t{{{sconst(state)}, {go_in(m, env)}, {str(ok).lower()}, {row or 0}, {a}, {str(ovf).lower()}}},")
    out += ["}", "", "var rows = map[int]Move{"]
    for r in m.rows:
        out.append(f"\t{r['n']}: {{Row: {r['n']}, Action: {go_str(r['act'] or '')}, Proc: {go_str(r.get('proc', ''))}, "
                   f"Next: {sconst(r['next'])}, Norm: {go_str(r['norm'])}}},")
    out += ["}", "",
            f"// TestForm — Step chooses the first matching row of {m.rel} with its arguments, or waits.",
            "func TestForm(t *testing.T) {", "\tfor k, c := range formCases {",
            "\t\tm, ok, err := Step(c.state, c.in)", "\t\tif c.overflow {",
            "\t\t\tif !errors.Is(err, ErrOverflow) {", '\t\t\t\tt.Errorf("case %d (%s %+v): err %v, want overflow", k, c.state, c.in, err)',
            "\t\t\t}", "\t\t\tcontinue", "\t\t}", "\t\tif err != nil || ok != c.ok {",
            '\t\t\tt.Errorf("case %d (%s %+v): ok %v err %v, want ok %v (row %d)", k, c.state, c.in, ok, err, c.ok, c.row)',
            "\t\t\tcontinue", "\t\t}", "\t\tif !ok {", "\t\t\tcontinue", "\t\t}", "\t\twant := rows[c.row]",
            "\t\twant.Args = c.args", "\t\tif !reflect.DeepEqual(m, want) {",
            '\t\t\tt.Errorf("case %d (%s %+v): move %+v, want %+v", k, c.state, c.in, m, want)', "\t\t}", "\t}", "}", "",
            "func TestStates(t *testing.T) {"]
    for s in m.states:
        out.append(f"\tif Terminal({sconst(s)}) != {str(s in m.terminal).lower()} {{")
        out.append(f'\t\tt.Errorf("Terminal(%q)", {sconst(s)})')
        out.append("\t}")
    out += [f"\tif Initial != {sconst(m.initial)} {{", '\t\tt.Errorf("Initial %q", Initial)', "\t}",
            '\tif _, _, err := Step("no-such-state", In{}); err == nil {', '\t\tt.Error("Step on an unknown state")',
            "\t}", "}", "", "type record struct {", "\tcalls []string", "\targs  [][]any", "}", ""]
    for name, (args, _) in m.actions.items():
        params = ", ".join(f"a{i} {GO_TYPE[t]}" for i, t in enumerate(args))
        vals = ", ".join(f"a{i}" for i in range(len(args)))
        out += [f"func (r *record) {camel(name)}({params}) error {{",
                f"\tr.calls = append(r.calls, {go_str(name)})", f"\tr.args = append(r.args, []any{{{vals}}})",
                "\treturn nil", "}", ""]
    for name, *_ in m.procs:
        out += [f"func (r *record) {name}(in In) error {{", f"\tr.calls = append(r.calls, {go_str('-' + name)})",
                "\tr.args = append(r.args, []any{})", "\treturn nil", "}", ""]
    out += ["// TestApply — Apply calls exactly the action of each row once (a YOURS procedure by its method).",
            "func TestApply(t *testing.T) {", "\tfor _, c := range formCases {",
            "\t\tm, ok, err := Step(c.state, c.in)", "\t\tif !ok || err != nil {", "\t\t\tcontinue", "\t\t}",
            "\t\tr := &record{}", "\t\tif err := Apply(r, c.in, m); err != nil {",
            '\t\t\tt.Fatalf("row %d: Apply: %v", m.Row, err)', "\t\t}", "\t\twant := m.Action", '\t\tif want == "" {',
            '\t\t\twant = "-" + m.Proc', "\t\t}",
            "\t\tif len(r.calls) != 1 || r.calls[0] != want || (m.Action != \"\" && !reflect.DeepEqual(r.args[0], m.Args)) {",
            '\t\t\tt.Fatalf("row %d: calls %v %v, want %s %v", m.Row, r.calls, r.args, want, m.Args)', "\t\t}",
            "\t}", "\tif err := Apply(&record{}, In{}, Move{Row: 99}); err == nil {",
            '\t\tt.Error("Apply of an empty move")', "\t}", "}", ""]
    return gofmt("\n".join(out))


def snake(name):
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def go_impl(m, module):
    """Return YOURS <package>impl files: actions.go type and one file per action or '-' procedure."""
    head = (f"// Generated by tools/normgen/gen_machine.py from {m.rel}. YOURS from here: the kit puts this file once\n"
            f"// and never overwrites it. Replace the body with your effect; keep the signature (core calls {m.pkg}.Apply).\n\n"
            f"package {m.pkg}impl\n\n")
    files = {"actions.go": gofmt(head + f'import "{module}/{m.pkg}"\n\n'
                                 f"// Actions implements {m.pkg}.Actions: one file per method. Each stub answers «not in\n"
                                 "// this stage» — an error, never a silent noop.\ntype Actions struct{}\n\n"
                                 f"var _ {m.pkg}.Actions = Actions{{}}\n")}
    for name, (args, doc) in m.actions.items():
        params = ", ".join(f"a{i} {GO_TYPE[t]}" for i, t in enumerate(args))
        files[f"{name}.go"] = gofmt(head + 'import "errors"\n\n' + "\n".join([
            f"// {camel(name)} — #action {name}: {doc}", f"func (Actions) {camel(name)}({params}) error {{",
            f'\treturn errors.New("{m.pkg}impl.{camel(name)}: not in this stage")', "}", ""]))
    for name, s, nxt, norm, ns in m.procs:
        lines = [f"// {name} — YOURS at {norm}: rows {', '.join(map(str, ns))} ({s} → {nxt}) of {m.rel}."]
        lines += [f"// {line}" for line in m.yours_doc]
        lines += [f"func (Actions) {name}(in {m.pkg}.In) error {{",
                  f'\treturn errors.New("{m.pkg}impl.{name}: not in this stage")', "}", ""]
        files[f"{snake(name)}.go"] = gofmt(head + f'import (\n\t"errors"\n\n\t"{module}/{m.pkg}"\n)\n\n' + "\n".join(lines))
    if len(files) != len(m.actions) + len(m.procs) + 1:
        raise GenError(f"{m.rel}: two methods share one file name")
    return files


def build(part, root=ROOT):
    m = read(part, root)
    cs = cases(m)
    files = {f"go/{m.pkg}/machine.go": go_machine(m), f"go/{m.pkg}/form_test.go": go_tests(m, cs),
             **{f"go/{m.pkg}impl/{name}": text for name, text in go_impl(m, GO_MODULE).items()}}
    inv = [f"# Inventory of the {m.part} form tests (gen_machine.py): every row — its cases; no row is excluded.",
           "n\tstate\tnext\taction\tnorm\tcases"]
    for r in m.rows:
        inv.append("\t".join([str(r["n"]), r["state"], r["next"], r["action"] if r["act"] else "- (YOURS " + r["proc"] + ")",
                              r["norm"], str(sum(1 for c in cs if c[2] == r["n"]))]))
    for s in m.from_states:
        inv.append("\t".join(["-", s, s, "no match: wait", "-", str(sum(1 for c in cs if c[0] == s and c[2] is None))]))
    files[f"go/{m.pkg}/inventory.tsv"] = "\n".join(inv) + "\n"
    return m, cs, files


def generate(parts=None, root=ROOT, out=DEFAULT_OUT):
    out = Path(out)
    done = []
    for part in parts or machine_forms(root):
        m, cs, files = build(part, root)
        for rel, text in files.items():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_text(text, encoding="utf-8")
        done.append((part, len(m.rows), len(cs)))
    mod = out / "go/go.mod"
    if not mod.exists():
        mod.parent.mkdir(parents=True, exist_ok=True)
        mod.write_text(f"module {GO_MODULE}\n\ngo 1.22\n", encoding="utf-8")
    return done


JUDGE = HERE / "test_gen_machine.py"


def kit_dirs(part):
    return (package(part),)


def kit_files(part, module, out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source, editable)]; stale output raises GenError."""
    _, _, files = build(part)
    res = []
    for rel, text in sorted(files.items()):
        kept = Path(out) / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_machine.py --lesson {L.key}")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel[3:].rsplit("/", 1)
        res.append((sub, name, data, "generated", L.output_source(kept, out), sub.endswith("impl")))
    return res


def provenance(part):
    import tsv_input

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    forms = tsv_input.source_files(machine_forms()[part], root=ROOT) + [L.form("README.md")]
    if any(name.isupper() for name in read(part).vars):
        forms += tsv_input.source_files(L.form("daemon-flags.tsv"), root=ROOT)
    return {"form": [entry(p) for p in dict.fromkeys(forms)],
            "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))],
            "handwritten": [entry(HERE / "gen_checks.py")], "judge": entry(JUDGE)}


def kit_md(part):
    m = read(part)
    return f"""
## Part `{part}`: the transition choice of `{m.rel}` (generated; the actions are **yours**)

| Package | Import path | Origin |
|---|---|---|
| `{m.pkg}` | `{{module}}/internal/{m.pkg}` | generated from the form: `Step`, `Apply`, `Actions`, `In`, states; closed |
| `{m.pkg}impl` | `{{module}}/internal/{m.pkg}impl` | **yours**: the effects of the actions and the procedures «-» (stubs «not in this stage») |

```go
func Step(s State, in In) (Move, bool, error) // the first matching row of s; false — no match: wait, no effect
func Apply(a Actions, in In, m Move) error     // calls the #action of m with its Args, or the YOURS procedure
```

Core derives `In` (one field per `#var`, the norm in its comment), calls `Step`, then `Apply` with your
`{m.pkg}impl.Actions`; a procedure «-» ({', '.join(p[0] for p in m.procs) or 'none'}) must finish before the next
event. The machine is not run by the kit: reads, events, retries and store effects are yours. `go test
./internal/{m.pkg}/` checks the choice against the form (`inventory.tsv`: cases per row).
"""


def main(argv):
    args = argv[1:]
    opts = {"--out": DEFAULT_OUT, "--root": ROOT}
    for flag in opts:
        if flag in args:
            k = args.index(flag)
            opts[flag] = Path(args[k + 1])
            del args[k:k + 2]
    try:
        done = generate(args or None, opts["--root"], opts["--out"])
    except GenError as exc:
        print(f"gen_machine: {exc}", file=sys.stderr)
        return 1
    for part, rows, n in done:
        print(f"gen_machine: {L.code} {part}: {rows} rows, {n} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
