"""Таблица проверок команды (ADR-0120 п. 2 (а)): `Platform/NN-*/data/<имя>-checks.tsv` и входы `<имя>-checks.probes.tsv`.

Форма таблицы — в её шапке (`#var`, `#lim`, `#fn`, колонки n, op, group, each, check, when, code, kind, fault, norm). Эта
проверка:
- форма: n по порядку с 1, op — `*` или перечень, group подряд, each `i, x in <путь>`, code — 100–599, kind — слово;
- `when` и `fault` компилируются в CEL окружения таблицы; свои функции — только из `#fn`, параметры `lim.X` — только из
  `#lim` (ответ «Архитектора» 2026-11-04 к форме (3));
- пробы: у каждой строки есть вход `only`; у каждой — `pair` или `nopair` с причиной; каждый вход сверяется с таблицей
  прогоном: `only` — первой нарушена n, ни одна следующая вычислимая не нарушена; `pair` — первой нарушена n и ближайшая
  следующая вычислимая тоже; `pass` — не нарушена ни одна, и все вычислимы. Вычислимая — `when` без ошибки CEL.
"""
import json
import math
import re
from pathlib import Path

COLUMNS = ["n", "op", "group", "each", "check", "when", "code", "kind", "fault", "norm"]
PROBE_COLUMNS = ["n", "case", "sock", "body"]
EACH = re.compile(r"([a-z]\w*), ([a-z]\w*) in (body(?:\.[a-z_]+)+)")
CEL_BUILTINS = {"type", "has", "size", "string", "bytes", "int", "double", "matches", "startsWith", "endsWith",
                "contains", "split", "exists", "all", "exists_one", "map", "filter", "in", "dyn", "bool"}
LONE = re.compile(r"[\ud800-\udfff]")


class Table:
    def __init__(self, path):
        self.path = Path(path)
        self.vars, self.lims, self.fns, self.rows, self.errors = {}, {}, {}, [], []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        body = [line for line in lines if not line.startswith("#")]
        for line in lines:
            if m := re.match(r"#var (\w+) (\S+) — ", line):
                self.vars[m[1]] = m[2]
            elif m := re.match(r"#lim ([A-Z][A-Z0-9_]*) — ", line):
                self.lims[m[1]] = line
            elif m := re.match(r"#fn ([a-z_]+)\(([^)]*)\) -> (\w+) — ", line):
                self.fns[m[1]] = ([a.strip() for a in m[2].split(",") if a.strip()], m[3])
            elif re.match(r"#(var|lim|fn) ", line):
                self.error(f"header line out of form: {line}")
        if not body or body[0].split("\t") != COLUMNS:
            self.error(f"columns must be {COLUMNS}")
            return
        for no, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                self.error(f"row {no}: {len(cells)} cells, expected {len(COLUMNS)}")
                continue
            self.rows.append(dict(zip(COLUMNS, cells)))
        self.form()

    def error(self, message):
        self.errors.append(f"{self.path.name}: {message}")

    def form(self):
        seen_groups, last_group = set(), None
        for k, row in enumerate(self.rows, 1):
            where = f"n {row['n']}"
            if row["n"] != str(k):
                self.error(f"{where}: n must be {k} (rows in order, without gaps)")
            if row["op"] != "*" and not re.fullmatch(r"[a-z]+(,[a-z]+)*", row["op"]):
                self.error(f"{where}: op {row['op']!r} — * or a list of values")
            if not re.fullmatch(r"[a-z][a-z_]*", row["check"]):
                self.error(f"{where}: check {row['check']!r} — a Latin name")
            if not re.fullmatch(r"[1-5][0-9]{2}", row["code"]) or not re.fullmatch(r"[a-z]+", row["kind"]):
                self.error(f"{where}: code {row['code']!r} / kind {row['kind']!r}")
            group = row["group"]
            if bool(group) != bool(row["each"]):
                self.error(f"{where}: group and each go together")
            if group and not EACH.fullmatch(row["each"]):
                self.error(f"{where}: each {row['each']!r} — «i, x in body.<поле>»")
            if group and group != last_group:
                if group in seen_groups:
                    self.error(f"{where}: group {group} is not contiguous")
                seen_groups.add(group)
            last_group = group or None
            for column in ("when", "fault"):
                expr = row[column]
                if not expr:
                    continue
                for name in re.findall(r"(?<![\w.])([a-z_][A-Za-z_]*)\s*\(", expr):
                    if name not in CEL_BUILTINS and name not in self.fns:
                        self.error(f"{where}: {column} calls {name}(), not declared by #fn")
                for name in re.findall(r"\blim\.([A-Za-z_][A-Za-z0-9_]*)", expr):
                    if name not in self.lims:
                        self.error(f"{where}: {column} uses lim.{name}, not declared by #lim")
                if re.search(r"(?<![\w.\"])[0-9]{3,}(?![\w\"])", expr.replace("{0,19}", "").replace("{1,64}", "")):
                    self.error(f"{where}: {column} has a number literal; limits are #lim names")

    def steps(self, body):
        """The chain on one input: (row, binding) in order; a group expands over its list, element by element."""
        rows, k = self.rows, 0
        while k < len(rows):
            row = rows[k]
            if not row["group"]:
                yield row, {}
                k += 1
                continue
            group = [r for r in rows[k:] if r["group"] == row["group"]]
            index, item, path = EACH.fullmatch(row["each"]).groups()
            value = body
            for part in path.split(".")[1:]:
                value = value.get(part) if isinstance(value, dict) else None
            if isinstance(value, list):
                for i, element in enumerate(value):
                    for r in group:
                        yield r, {index: i, item: element}
            else:
                yield group[0], None                         # not a list: the group is not evaluable
            k += len(group)


def decode(text):
    """JSON of a probe → (body with U+FFFD instead of lone surrogates, list of JSON Pointers of such strings)."""
    lone = []

    def pointer(parts):
        return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)

    def walk(value, parts):
        if isinstance(value, str):
            if LONE.search(value):
                lone.append(pointer(parts))
            return LONE.sub("�", value)
        if isinstance(value, list):
            return [walk(v, parts + [i]) for i, v in enumerate(value)]
        if isinstance(value, dict):
            out = {}
            for name, v in value.items():
                if LONE.search(name):
                    lone.append(pointer(parts))
                clean = LONE.sub("�", name)
                out[clean] = walk(v, parts + [clean])
            return out
        if isinstance(value, int) and not isinstance(value, bool) and not -2 ** 63 <= value < 2 ** 63:
            return float(value)
        return value

    return walk(json.loads(text), []), sorted(set(lone))


class Runner:
    """The table on cel-expr-python with the primitives of the probes (own #lim values and #allow rights)."""

    def __init__(self, table, lims, allows):
        from cel_expr_python import cel
        self.cel, self.table, self.lims, self.allows = cel, table, lims, allows
        T = cel.Type
        types = {"string": T.STRING, "bool": T.BOOL, "int": T.INT, "double": T.DOUBLE,
                 "map": T.Map(T.DYN, T.DYN), "list": T.List(T.DYN), "dyn": T.DYN}
        impls = {"key_ok": key_ok, "weight": weight, "finite": lambda x: math.isfinite(x),
                 "allowed": self.allowed}
        fns = []
        for name, (args, result) in table.fns.items():
            if name not in impls:
                raise ValueError(f"#fn {name}: no primitive in check_tables.Runner")
            fns.append(cel.FunctionDecl(name, [cel.Overload(f"{name}_{'_'.join(args)}", types[result],
                                                            [types[a] for a in args], impl=impls[name])]))
        cfg = cel.NewEnvConfigFromYaml("name: checks\nextensions:\n  - name: strings\n  - name: two-var-comprehensions\n")
        variables = {"body": T.DYN, "sock": T.STRING, "lone": T.List(T.STRING), "lim": T.Map(T.STRING, T.INT)}
        for row in table.rows:
            if row["each"]:
                i, x, _ = EACH.fullmatch(row["each"]).groups()
                variables.setdefault(i, T.INT)
                variables.setdefault(x, T.DYN)
        self.env = cel.NewEnv(config=cfg, variables=variables, functions=fns)
        self.compiled = {}
        for row in table.rows:
            for column in ("when", "fault"):
                if row[column]:
                    try:
                        self.compiled[row["n"], column] = self.env.compile(row[column])
                    except Exception as exc:                   # noqa: BLE001 — the message names the row
                        table.error(f"n {row['n']}: {column} does not compile: {exc}")

    def allowed(self, sock, op, key):
        return any(s == sock and o in ("*", op) and key.startswith(prefix) for s, o, prefix in self.allows)

    def eval(self, row, column, data):
        e = self.compiled.get((row["n"], column))
        if e is None:
            return "error", "not compiled"
        v = e.eval(data=data)
        if v.type() == self.cel.Type.ERROR:
            return "error", v.value()
        return "ok", v.plain_value()

    def run(self, sock, body, lone):
        """→ [(row, status, value)] over the chain: status ok | error; rows of other commands are skipped."""
        op = body.get("op") if isinstance(body, dict) else None
        out = []
        for row, binding in self.table.steps(body):
            if row["op"] != "*" and op not in row["op"].split(","):
                continue
            if binding is None:
                out.append((row, "error", "each over a non-list"))
                continue
            data = {"body": body, "sock": sock, "lone": lone, "lim": self.lims, **binding}
            status, value = self.eval(row, "when", data)
            if status == "ok" and not isinstance(value, bool):
                status, value = "error", f"when gives {type(value).__name__}, not bool"
            out.append((row, status, value, data) if status == "ok" else (row, status, value))
        return out


def key_ok(k):
    return k != "" and not k.startswith("/") and ".." not in k.split("/") and len(k.encode("utf-8")) <= 1024


def weight(items):
    total = 0
    for name, value in items.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise TypeError("weight: items is not an object of strings")
        total += len(name.encode("utf-8")) + len(value.encode("utf-8"))
    return total


def check(table_path):
    """→ (errors, stats) of one table with its probes."""
    table = Table(table_path)
    probes_path = table.path.with_name(table.path.name.replace(".tsv", ".probes.tsv"))
    if not probes_path.is_file():
        return table.errors + [f"{table.path.name}: no probes {probes_path.name} — the generator refuses a table "
                               f"without inputs"], {}
    lines = probes_path.read_text(encoding="utf-8").splitlines()
    lims, allows, probes = {}, [], []
    for line in lines:
        if m := re.fullmatch(r"#lim ([A-Z][A-Z0-9_]*) ([0-9]+)", line):
            lims[m[1]] = int(m[2])
        elif m := re.fullmatch(r"#allow (\S+) (\S+) ?(\S*)", line):
            allows.append((m[1], m[2], m[3]))
    missing = set(table.lims) - set(lims)
    if missing:
        table.error(f"{probes_path.name}: no #lim value for {sorted(missing)}")
    body = [line for line in lines if not line.startswith("#")]
    if not body or body[0].split("\t") != PROBE_COLUMNS:
        table.error(f"{probes_path.name}: columns must be {PROBE_COLUMNS}")
        return table.errors, {}
    for no, line in enumerate(body[1:], 2):
        cells = line.split("\t")
        if len(cells) != 4 or cells[1] not in {"only", "pair", "nopair", "pass"}:
            table.error(f"{probes_path.name} row {no}: n, case only|pair|nopair|pass, sock, body")
            continue
        probes.append((no, *cells))
    if table.errors:
        return table.errors, {}
    runner = Runner(table, lims, allows)
    numbers = {row["n"]: row for row in table.rows}
    cases = {}
    for no, n, case, sock, text in probes:
        where = f"{probes_path.name} row {no} (n {n}, {case})"
        cases.setdefault(n, set()).add(case)
        if case == "nopair":
            if n not in numbers or not text.strip():
                table.error(f"{where}: nopair names a row and gives a reason")
            continue
        if case == "pass" and n != "0" or case != "pass" and n not in numbers:
            table.error(f"{where}: n {n!r} — a row of the table (0 for pass)")
            continue
        try:
            value, lone = decode(text)
        except ValueError as exc:
            table.error(f"{where}: body is not JSON: {exc}")
            continue
        chain = runner.run(sock, value, lone)
        hits = [k for k, step in enumerate(chain) if step[1] == "ok" and step[2] is True]
        if case == "pass":
            bad = [s[0]["n"] for s in chain if s[1] != "ok" or s[2] is not False]
            if bad:
                table.error(f"{where}: a passing input violates or cannot evaluate rows {bad}")
            continue
        if not hits or chain[hits[0]][0]["n"] != n:
            first = chain[hits[0]][0]["n"] if hits else None
            table.error(f"{where}: the first violated row is {first}, not {n}")
            continue
        first = hits[0]
        row, _, _, data = chain[first]
        if row["fault"]:
            status, fault = runner.eval(row, "fault", data)
            if status != "ok" or not isinstance(fault, dict):
                table.error(f"{where}: fault does not evaluate: {fault}")
        later = [step for step in chain[first + 1:] if step[1] == "ok"]
        if case == "only" and any(step[2] is True for step in later):
            table.error(f"{where}: also violated: {[s[0]['n'] for s in later if s[2] is True]}")
        if case == "pair" and (not later or later[0][2] is not True):
            table.error(f"{where}: the next evaluable row {later[0][0]['n'] if later else None} is not violated")
    for row in table.rows:
        got = cases.get(row["n"], set())
        if "only" not in got:
            table.error(f"n {row['n']}: no probe «only» (only this row violated)")
        if not got & {"pair", "nopair"}:
            table.error(f"n {row['n']}: no probe «pair» (this row and the next) and no «nopair» with a reason")
    return table.errors, {"check_rows": len(table.rows), "check_probes": len(probes)}


def tables(root):
    return sorted(Path(root).glob("Platform/*/data/*-checks.tsv"))
