"""Чтение формы провода векторов Platform/common/vectors/wire.tsv (грамматика — Platform/common/vectors/wire.md).

Форма — данные: строка (package, table, surface) объявляет вход, фикстуры, ожидание, маркеры, сравнение и нативную рамку
вызова на каждой строке исходной таблицы (или группе строк). Здесь — разбор формы с отказом на всё, чего нет в закрытой
грамматике, и раскрытие в конкретные запуски урока: run(owner) → [Run] (вход, ожидаемый код, значение или байты,
сравнение, утверждения) и [Excluded] (строки, которые ни одно объявление урока не выбрало, — не PASS).

Условия when — CEL (row: map<string,string>, owner: string, расширение strings) — считает cel_expr_python, как
check_forms; на CT 103 — /opt/check-env/lesson-spec/bin/python.
"""
import json
import re
from dataclasses import dataclass, field
from typing import NamedTuple, Optional
from pathlib import Path

import vector_consumers

FORM = "Platform/common/vectors/wire.tsv"
CONSUMERS = "Platform/common/vectors/consumers.tsv"
COLUMNS = ["package", "table", "surface", "header", "inputs", "files", "expect", "compare", "markers", "native", "norm"]
COMPARES = {"value", "subset", "raw", "set", "object-sets", "lines-value", "lines-subset"}
TYPES = {"object", "array", "string", "number", "boolean", "null", "value", "bytes"}
FRAMES = {"json", "json-lf", "raw"}
DECODES_CELL = {"cell", "json", "text"}
DECODES_FILE = {"bytes", "text", "json"}
TESTS = {"prefix", "absent", "no-leak"}


class WireError(Exception):
    pass


def strict_json(text, where):
    """Строгий JSON: без BOM, NaN/Infinity и повторных ключей."""
    if text.startswith("﻿"):
        raise WireError(f"{where}: BOM")

    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise WireError(f"{where}: duplicate key in {keys}")
        return dict(items)

    def const(c):
        raise WireError(f"{where}: {c} is not JSON")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=const)
    except ValueError as e:
        raise WireError(f"{where}: not JSON: {e}") from None


def is_json(text):
    try:
        strict_json(text, "")
        return True
    except WireError:
        return False


def keys_of(obj, where, required=(), optional=()):
    if not isinstance(obj, dict):
        raise WireError(f"{where}: expected an object, got {obj!r}")
    extra = set(obj) - set(required) - set(optional)
    missing = set(required) - set(obj)
    if extra or missing:
        raise WireError(f"{where}: keys {sorted(obj)} (required {list(required)}, optional {list(optional)})")


def anchor(heading):
    """Якорь заголовка Markdown (как GitHub): нижний регистр, без пунктуации, пробел → «-»."""
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


# ---------------------------------------------------------------- разбор формы

@dataclass
class Binding:
    line: int
    package: str
    table: str
    surface: str
    header: list
    inputs: list
    files: dict
    expect: list
    compare: object
    markers: list
    native: object
    norm: str

    @property
    def key(self):
        return self.package, self.table, self.surface


def pointer_tokens(pointer, where, root=False):
    if root and pointer == "":
        return []
    if not isinstance(pointer, str) or not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise WireError(f"{where}: invalid JSON Pointer {pointer!r}")
    return [x.replace("~1", "/").replace("~0", "~") for x in pointer[1:].split("/")]


def at_pointer(value, pointer, where):
    for part in pointer_tokens(pointer, where):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", part) and int(part) < len(value):
            value = value[int(part)]
        else:
            raise WireError(f"{where}: missing selected path {pointer!r}")
    return value


def check_arg_json(v, where):
    """Closed input-only ValueExpr vocabulary; raw-json is legal only here."""
    if not isinstance(v, dict) or not v:
        raise WireError(f"{where}: argument ValueExpr {v!r}")
    if "column" in v:
        keys_of(v, where, ("column", "decode"))
        if not isinstance(v["column"], str) or v["decode"] not in {"text", "json", "raw-json"}:
            raise WireError(f"{where}: argument column/decode {v!r}")
    elif "literal" in v:
        keys_of(v, where, ("literal",))
    elif "object" in v:
        keys_of(v, where, ("object",))
        if not isinstance(v["object"], dict):
            raise WireError(f"{where}: argument object")
        for key, value in v["object"].items():
            check_arg_json(value, f"{where}.{key}")
    elif "array" in v:
        keys_of(v, where, ("array",))
        if not isinstance(v["array"], list):
            raise WireError(f"{where}: argument array")
        for i, value in enumerate(v["array"]):
            check_arg_json(value, f"{where}[{i}]")
    else:
        raise WireError(f"{where}: forbidden argument constructor {sorted(v)}")


def check_value(v, where, *, group=False, prefix=False, in_object=False):
    """Exactly one constructor; no evaluation of an implementation algorithm."""
    if not isinstance(v, dict) or not v:
        raise WireError(f"{where}: ValueExpr {v!r}")
    if "column" in v:
        keys_of(v, where, ("column", "decode"))
        if v["decode"] not in DECODES_CELL:
            raise WireError(f"{where}: decode {v['decode']!r}")
    elif "literal" in v:
        keys_of(v, where, ("literal",))
    elif "object" in v:
        keys_of(v, where, ("object",))
        if not isinstance(v["object"], dict):
            raise WireError(f"{where}: object {v!r}")
        for k, x in v["object"].items():
            check_value(x, f"{where}.{k}", group=group, prefix=prefix, in_object=True)
    elif "array" in v:
        keys_of(v, where, ("array",))
        if not isinstance(v["array"], list):
            raise WireError(f"{where}: array {v!r}")
        for i, x in enumerate(v["array"]):
            check_value(x, f"{where}[{i}]", group=group, prefix=prefix)
    elif "at" in v:
        keys_of(v, where, ("at",), ("decode",))
        a = v["at"]
        keys_of(a, where+".at", ("value", "pointer"))
        source = a["value"]
        if not isinstance(source, dict) or not ("column" in source or "literal" in source):
            raise WireError(f"{where}: at source must be column or literal")
        check_value(source, where+".at.value")
        pointer_tokens(a["pointer"], where+".at.pointer")
        if "decode" in v and v["decode"] != "json":
            raise WireError(f"{where}: at decode is json only")
    elif "map" in v:
        keys_of(v, where, ("map",))
        keys_of(v["map"], where+".map", ("key", "value"))
        if not group or not isinstance(v["map"]["key"], str):
            raise WireError(f"{where}: map requires group_by and a key column")
        check_value(v["map"]["value"], where+".map.value", group=group, prefix=prefix)
    elif "file" in v:
        keys_of(v, where, ("file", "decode"))
        f = v["file"]
        keys_of(f, where+".file", ("base",), ("path", "path_column"))
        if f["base"] not in ("package", "root") or ("path" in f) == ("path_column" in f):
            raise WireError(f"{where}: file {f!r}")
        if v["decode"] not in DECODES_FILE:
            raise WireError(f"{where}: decode {v['decode']!r}")
    elif "group" in v or "groups" in v:
        k = "group" if "group" in v else "groups"
        keys_of(v, where, (k,))
        keys_of(v[k], f"{where}.{k}", ("column", "decode") + (("by",) if k == "groups" else ()))
        if v[k]["decode"] not in DECODES_CELL or not group:
            raise WireError(f"{where}: {k} requires group_by and cell decode")
    elif "suffix" in v:
        keys_of(v, where, ("suffix", "decode"))
        if v["suffix"] is not True or v["decode"] not in DECODES_CELL or not prefix:
            raise WireError(f"{where}: suffix only in a prefix marker")
    elif "omit" in v:
        keys_of(v, where, ("omit",))
        if v["omit"] is not True or not in_object:
            raise WireError(f"{where}: omit only as an object field")
    else:
        raise WireError(f"{where}: no constructor in {sorted(v)}")


def check_compare(c, where, variants):
    if isinstance(c, str):
        if c not in COMPARES:
            raise WireError(f"{where}: compare {c!r}")
        return
    if not isinstance(c, dict) or set(c) - set(variants) or any(x not in COMPARES for x in c.values()):
        raise WireError(f"{where}: compare {c!r}")


def check_asserts(a, where, group, prefix=False):
    if not isinstance(a, list):
        raise WireError(f"{where}: assert {a!r}")
    for i, x in enumerate(a):
        w = f"{where}.assert[{i}]"
        keys_of(x, w, ("pointer",), ("test", "value", "decode", "compare", "min_bytes", "whole", "ignore"))
        pointer_tokens(x["pointer"], w, root=True)
        if "ignore" in x:
            if "test" in x:
                raise WireError(f"{w}: ignore is forbidden with test")
            check_ignore(x["ignore"], w)
        if "test" in x:
            if x["test"] not in TESTS or (x["test"] == "absent") == ("value" in x) or "compare" in x:
                raise WireError(f"{w}: {x!r}")
        elif "value" not in x:
            raise WireError(f"{w}: no value")
        leak = x.get("test") == "no-leak"
        mb = x.get("min_bytes")
        if leak != ("min_bytes" in x) or (leak and (not isinstance(mb, int) or isinstance(mb, bool) or mb < 1)):
            raise WireError(f"{w}: min_bytes (an integer >= 1) goes with no-leak only: {x!r}")
        if "whole" in x and (not leak or not isinstance(x["whole"], bool)):
            raise WireError(f"{w}: whole (a boolean) goes with no-leak only: {x!r}")
        if x.get("decode", "json") != "json":
            raise WireError(f"{w}: decode {x['decode']!r}")
        if "compare" in x and (x["compare"] not in COMPARES or x["compare"].startswith("lines-")):
            raise WireError(f"{w}: compare {x['compare']!r}")
        if "value" in x:
            check_value(x["value"], w + ".value", group=group, prefix=prefix)


def check_ignore(paths, where):
    if not isinstance(paths, list) or not paths:
        raise WireError(f"{where}: ignore must be a nonempty pointer array")
    seen = []
    for p in paths:
        parts = tuple(pointer_tokens(p, where))
        if any(parts[:len(q)] == q or q[:len(parts)] == parts for q in seen):
            raise WireError(f"{where}: duplicate/overlapping ignore pointer {p!r}")
        seen.append(parts)


def check_native(n, where):
    for i, d in enumerate(n if isinstance(n, list) else [n]):
        w = f"{where}[{i}]" if isinstance(n, list) else where
        keys_of(d, w, ("type", "frame"), ("schema",) + (("variant", "when") if isinstance(n, list) else ()))
        types = d["type"] if isinstance(d["type"], list) else [d["type"]]
        if not types or any(t not in TYPES for t in types) or d["frame"] not in FRAMES:
            raise WireError(f"{w}: {d!r}")
        if "bytes" in types and (types != ["bytes"] or d["frame"] != "raw" or "schema" in d):
            raise WireError(f"{w}: bytes is only frame raw without schema")
        if d["frame"] == "raw" and types != ["bytes"]:
            raise WireError(f"{w}: frame raw is only for bytes")


def parse(root, keys=None, surfaces=None):
    """→ [Binding] формы; любое отступление от грамматики — WireError с номером строки."""
    root = Path(root)
    path = root / FORM
    if not path.is_file():
        raise WireError(f"no {FORM}")
    head, out, seen = None, [], set()
    for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if head is None:
            if cells != COLUMNS:
                raise WireError(f"{FORM}:{no}: header {cells}, expected {COLUMNS}")
            head = cells
            continue
        w = f"{FORM}:{no}"
        if len(cells) != len(COLUMNS):
            raise WireError(f"{w}: {len(cells)} cells, expected {len(COLUMNS)}")
        r = dict(zip(COLUMNS, cells))
        if not re.fullmatch(r"(common|\d\d-[a-z0-9-]+)/[a-z0-9-]+", r["package"]):
            raise WireError(f"{w}: package {r['package']!r}")
        if not re.fullmatch(r"vectors|layout|stand:[a-z0-9-]+", r["surface"]):
            raise WireError(f"{w}: surface {r['surface']!r}")
        key = (r["package"], r["table"], r["surface"])
        if key in seen:
            raise WireError(f"{w}: second row {key}")
        seen.add(key)
        if ((keys is not None and (r["package"], r["table"]) not in keys)
                or (surfaces is not None and r["surface"] not in surfaces)):
            continue  # only selected table grammars are used; incomplete P/06 is not silently executed
        layout = r["surface"] == "layout"
        js = {k: strict_json(r[k], f"{w} {k}") for k in ("inputs", "files", "expect", "markers")}
        js["native"] = None if layout and r["native"] == "-" else strict_json(r["native"], f"{w} native")
        js["compare"] = r["compare"] if r["compare"] in COMPARES | {"-"} else strict_json(r["compare"], f"{w} compare")
        b = Binding(no, r["package"], r["table"], r["surface"], r["header"].split(","), js["inputs"], js["files"],
                    js["expect"], js["compare"], js["markers"], js["native"], r["norm"])
        check_binding(root, b, w)
        out.append(b)
    if head is None:
        raise WireError(f"{FORM}: no header")
    return out


def check_binding(root, b, w):
    if b.surface == "layout":
        if b.inputs != [] or b.files != {} or b.expect != [] or b.markers != [] or b.compare != "-" or b.native:
            raise WireError(f"{w}: layout has no inputs, files, expect, markers, compare, native")
    else:
        if b.compare == "-" or not isinstance(b.inputs, list) or not b.inputs:
            raise WireError(f"{w}: inputs and compare are required off layout")
        stand = b.surface.startswith("stand:")
        variants = set()
        groups = set()
        for i, d in enumerate(b.inputs):
            wi = f"{w} inputs[{i}]"
            keys_of(d, wi, ("variant", "arg_file" if stand else "cells"), ("when", "case", "group_by"))
            if not isinstance(d["variant"], str) or not isinstance(d.get("when", "true"), str):
                raise WireError(f"{wi}: variant/when")
            variants.add(d["variant"])
            groups.add("group_by" in d)
            c = d.get("case")
            if c is not None and not (isinstance(c, str) or c == {"line": True}
                                      or (isinstance(c, dict) and set(c) == {"literal"} and isinstance(c["literal"], str))):
                raise WireError(f"{wi}: case {c!r}")
            gb = d.get("group_by")
            if gb is not None and not (isinstance(gb, list) and all(isinstance(x, str) for x in gb)):
                raise WireError(f"{wi}: group_by {gb!r}")
            if stand:
                a = d["arg_file"]
                if isinstance(a, dict) and set(a) == {"json"}:
                    check_arg_json(a["json"], wi+".arg_file.json")
                else:
                    ok = (isinstance(a, dict) and (set(a) == {"column"} or set(a) == {"literal"}
                                                   or (set(a) == {"path_column", "base"} and a["base"] == "root")))
                    if not ok or not all(isinstance(x, str) for x in a.values()):
                        raise WireError(f"{wi}: arg_file {a!r}")
            else:
                if not isinstance(d["cells"], dict):
                    raise WireError(f"{wi}: cells {d['cells']!r}")
                for k, x in d["cells"].items():
                    if not (isinstance(x, dict) and len(x) == 1 and set(x) <= {"column", "literal"}
                            and isinstance(next(iter(x.values())), str)):
                        raise WireError(f"{wi}: cell {k}: {x!r}")
        group = True in groups
        if not isinstance(b.files, dict) or (stand and b.files):
            raise WireError(f"{w}: files {b.files!r} (stand: only {{}})")
        for k, f in b.files.items():
            keys_of(f, f"{w} files.{k}", ("base", "path"), ("when",))
            if "/" in k or f["base"] not in ("package", "root"):
                raise WireError(f"{w} files.{k}: {f!r}")
        if not isinstance(b.expect, list) or not b.expect:
            raise WireError(f"{w}: expect")
        for i, e in enumerate(b.expect):
            we = f"{w} expect[{i}]"
            keys_of(e, we, ("variant", "code", "value"), ("when", "assert", "ignore"))
            if e["variant"] not in variants:
                raise WireError(f"{we}: variant {e['variant']!r} has no input")
            if not isinstance(e["code"], int) or isinstance(e["code"], bool) or not 0 <= e["code"] <= 255:
                raise WireError(f"{we}: code {e['code']!r}")
            check_value(e["value"], we + ".value", group=group)
            if e["value"].get("omit"):
                raise WireError(f"{we}: omit at the root")
            check_asserts(e.get("assert", []), we, group)
            if "ignore" in e:
                check_ignore(e["ignore"], we)
        for i, m in enumerate(b.markers):
            wm = f"{w} markers[{i}]"
            keys_of(m, wm, ("variant", "column", "match"),
                    ("prefix", "code", "ignore_stdout", "value", "compare", "assert"))
            if m["variant"] not in variants or not isinstance(m["match"], str) or not m["match"]:
                raise WireError(f"{wm}: {m!r}")
            if "code" in m and (not isinstance(m["code"], int) or isinstance(m["code"], bool) or not 0 <= m["code"] <= 255):
                raise WireError(f"{wm}: code {m['code']!r}")
            for flag in ("prefix", "ignore_stdout"):
                if flag in m and not isinstance(m[flag], bool):
                    raise WireError(f"{wm}: {flag} must be boolean")
            if m.get("ignore_stdout") and ("value" in m or "compare" in m or "assert" in m):
                raise WireError(f"{wm}: ignore_stdout with a value")
            if "value" in m:
                check_value(m["value"], wm + ".value", group=group, prefix=bool(m.get("prefix")))
            if "compare" in m:
                check_compare(m["compare"], wm, variants)
            check_asserts(m.get("assert", []), wm, group, prefix=bool(m.get("prefix")))
        check_compare(b.compare, w, variants)
        check_native(b.native, f"{w} native")
    norm, _, anc = b.norm.partition("#")
    md = root / "Platform" / norm
    if not norm.endswith(".md") or not md.is_file():
        raise WireError(f"{w}: norm {b.norm!r}: no Platform/{norm}")
    if anc:
        heads = [anchor(m[1]) for m in re.finditer(r"^#+\s+(.*?)\s*#*\s*$", md.read_text(encoding="utf-8"), re.M)]
        if anc not in heads:
            raise WireError(f"{w}: norm {b.norm!r}: no heading #{anc} in Platform/{norm}")


# ---------------------------------------------------------------- раскрытие в запуски

class Assert(NamedTuple):
    pointer: str
    test: Optional[str]             # prefix | absent | no-leak | None (сравнение значения)
    compare: Optional[str]
    value: object
    min_bytes: Optional[int]        # только no-leak
    whole: Optional[bool]           # только no-leak (по умолчанию false)
    decode: Optional[str] = None    # json внутри строкового поля ответа
    ignore: Optional[list] = None   # comparison-only pointers, never with test


def leaks(text, secrets, min_bytes, whole=False):
    """Смысл no-leak: → секреты, след которых есть в UTF-8 текста. whole=false — любая подстрока секрета длиной
    ≥ min_bytes байт; whole=true — секрет целиком, если его длина ≥ min_bytes байт (короткие не судятся)."""
    data, out = text.encode("utf-8"), []
    for s in secrets:
        b = s.encode("utf-8")
        if whole:
            if len(b) >= min_bytes and b in data:
                out.append(s)
        elif len(b) >= min_bytes and any(b[i:i + min_bytes] in data for i in range(len(b) - min_bytes + 1)):
            out.append(s)                # любая подстрока длиннее содержит подстроку ровно min_bytes
    return out


@dataclass
class Run:
    owner: str
    binding: Binding
    variant: str
    case: str
    lines: list                     # физические строки таблицы (одна или группа)
    cells: dict = None              # vectors: имя → строка
    arg: bytes = None               # stand: байты файла {input} (path_column — байты фикстуры)
    arg_path: str = None            # stand path_column: путь фикстуры от корня выгрузки
    files: dict = field(default_factory=dict)      # имя → байты
    code: int = 0
    ignore_stdout: bool = False
    value: object = None            # ожидаемое значение JSON (или bytes при native bytes)
    compare: str = "value"
    asserts: list = field(default_factory=list)    # [Assert]
    ignore: list = field(default_factory=list)     # comparison pointers, after the full native schema
    native: dict = None

    @property
    def identity(self):
        b = self.binding
        return self.owner, b.package, b.table, b.surface, self.variant, self.case


@dataclass
class Excluded:
    owner: str
    binding: Binding
    line: int
    reason: str


class Cel:
    def __init__(self):
        from cel_expr_python import cel
        T = cel.Type
        self.cel = cel
        cfg = cel.NewEnvConfigFromYaml("name: wire\nextensions:\n  - name: strings\n")
        fn = cel.FunctionDecl("json", [cel.Overload(id="wire_json", parameters=[T.STRING], return_type=T.DYN,
                                                   impl=lambda text: strict_json(text, "wire when json"))])
        self.env = cel.NewEnv(config=cfg, variables={"row": T.Map(T.STRING, T.STRING), "owner": T.STRING},
                              functions=[fn])
        self.cache = {}

    def __call__(self, expr, row, owner, where):
        if expr == "true":
            return True
        e = self.cache.get(expr)
        if e is None:
            try:
                e = self.cache[expr] = self.env.compile(expr)
            except Exception as x:          # noqa: BLE001 — ошибка компиляции CEL
                raise WireError(f"{where}: when {expr!r}: {x}") from None
        try:
            v = e.eval(data={"row": row, "owner": owner})
        except Exception as x:
            raise WireError(f"{where}: when {expr!r}: {x}") from None
        if v.type() == self.cel.Type.ERROR or not isinstance(v.plain_value(), bool):
            raise WireError(f"{where}: when {expr!r} on {row}: {v.value()}")
        return v.plain_value()


def package_dir(root, package):
    owner, name = package.split("/", 1)
    return Path(root) / "Platform" / owner / "vectors" / name


def resolve(root, base_dir, rel, where):
    """Путь фикстуры: относительный, внутри выгрузки, существующий файл."""
    if rel.startswith("/") or not rel:
        raise WireError(f"{where}: path {rel!r}")
    p = (base_dir / rel).resolve()
    top = Path(root).resolve()
    if top not in p.parents:
        raise WireError(f"{where}: {rel!r} leaves the export")
    if not p.is_file():
        raise WireError(f"{where}: no file {p.relative_to(top)}")
    return p


def read_rows(root, b):
    """→ [(строка, {колонка: ячейка})]; шапка или позиционные поля сверены с header формы."""
    path = package_dir(root, b.package) / b.table
    if not path.is_file():
        raise WireError(f"{FORM}:{b.line}: no {path.relative_to(root)}")
    positional = b.header[0] == "-"
    names = b.header[1:] if positional else b.header
    head, rows = None, []
    for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if not positional and head is None:
            head = cells
            if head != names:
                raise WireError(f"{FORM}:{b.line}: header {names}, the table has {head}")
            continue
        if len(cells) != len(names):
            raise WireError(f"{path.relative_to(root)}:{no}: {len(cells)} cells, header {names}")
        rows.append((no, dict(zip(names, cells))))
    return rows


def decode(cell, how, where):
    if how == "text":
        return cell
    if how == "json":
        return strict_json(cell, where)
    return strict_json(cell, where) if is_json(cell) else cell


def substitute(template, rows, where):
    def one(m):
        vals = {r[m[1]] for _, r in rows if m[1] in r}
        if len(vals) != 1 or any(m[1] not in r for _, r in rows):
            raise WireError(f"{where}: {{{m[1]}}} is not one value over the group")
        return vals.pop()
    return re.sub(r"\{([a-z0-9_]+)\}", one, template)


def constant(rows, column, where):
    vals = {r.get(column) for _, r in rows}
    if None in vals:
        raise WireError(f"{where}: no column {column!r}")
    if len(vals) != 1:
        raise WireError(f"{where}: column {column!r} is not one value over the group")
    return vals.pop()


@dataclass
class RawJSON:
    text: str


def argument_json(value, where):
    if isinstance(value, RawJSON):
        return value.text
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + argument_json(v, where)
                               for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(argument_json(v, where) for v in value) + "]"
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise WireError(f"{where}: argument JSON: {exc}") from None


class Expander:
    def __init__(self, root, cel=None):
        self.root = Path(root)
        self.cel = cel or Cel()

    def agree(self, expr, rows, owner, where):
        """when на каждой строке группы; все результаты обязаны совпасть."""
        vals = {self.cel(expr, r, owner, where) for _, r in rows}
        if len(vals) != 1:
            raise WireError(f"{where}: when {expr!r} differs over the group")
        return vals.pop()

    def value(self, v, rows, pdir, where, suffix=None):
        if "column" in v:
            return decode(constant(rows, v["column"], where), v["decode"], where)
        if "literal" in v:
            return v["literal"]
        if "object" in v:
            out = {}
            for k, x in v["object"].items():
                if x.get("omit"):
                    continue
                out[k] = self.value(x, rows, pdir, f"{where}.{k}", suffix)
            return out
        if "array" in v:
            return [self.value(x, rows, pdir, f"{where}[{i}]", suffix) for i, x in enumerate(v["array"])]
        if "at" in v:
            a = v["at"]
            value = at_pointer(self.value(a["value"], rows, pdir, where, suffix), a["pointer"], where)
            if "decode" in v:
                if not isinstance(value, str):
                    raise WireError(f"{where}: at decode json requires a string")
                return strict_json(value, where)
            return value
        if "map" in v:
            m, out = v["map"], {}
            for row in rows:
                key = constant([row], m["key"], where)
                if key in out:
                    raise WireError(f"{where}: duplicate map key {key!r}")
                out[key] = self.value(m["value"], [row], pdir, where, suffix)
            return out
        if "file" in v:
            f = v["file"]
            base = pdir if f["base"] == "package" else self.root
            rel = constant(rows, f["path_column"], where) if "path_column" in f else substitute(f["path"], rows, where)
            data = resolve(self.root, base, rel, where).read_bytes()
            if v["decode"] == "bytes":
                return data
            text = data.decode("utf-8")
            return text if v["decode"] == "text" else strict_json(text, where)
        if "group" in v:
            g = v["group"]
            return [decode(r[g["column"]], g["decode"], where) for _, r in rows]
        if "groups" in v:
            g = v["groups"]
            out = {}
            for _, r in rows:
                out.setdefault(r[g["by"]], []).append(decode(r[g["column"]], g["decode"], where))
            return out
        if "suffix" in v:
            if suffix is None:
                raise WireError(f"{where}: suffix without a matched prefix marker")
            return decode(suffix, v["decode"], where)
        raise WireError(f"{where}: {v!r}")

    def argument(self, v, rows, where):
        if "column" in v:
            text = constant(rows, v["column"], where)
            if v["decode"] == "raw-json":
                strict_json(text, where)
                return RawJSON(text)
            return decode(text, v["decode"], where)
        if "literal" in v:
            return v["literal"]
        if "object" in v:
            return {k: self.argument(x, rows, where) for k, x in v["object"].items()}
        if "array" in v:
            return [self.argument(x, rows, where) for x in v["array"]]
        raise WireError(f"{where}: forbidden argument expression")

    def asserts(self, a, rows, pdir, where, suffix=None):
        """→ [Assert]; у no-leak value — массив секретов, whole — false по умолчанию."""
        out = []
        for x in a:
            v = self.value(x["value"], rows, pdir, where, suffix) if "value" in x else None
            if x.get("test") == "no-leak":
                v = [v] if isinstance(v, str) else v
                if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
                    raise WireError(f"{where}: no-leak value is a string or an array of strings, got {v!r:.80}")
            out.append(Assert(x["pointer"], x.get("test"), x.get("compare"), v, x.get("min_bytes"),
                              bool(x.get("whole", False)) if x.get("test") == "no-leak" else None, x.get("decode"), x.get("ignore")))
        return out

    def run(self, b, owner):
        """→ ([Run], [Excluded]) привязки b для урока owner (каталог урока)."""
        w = f"{FORM}:{b.line}"
        if b.surface == "layout":
            return [], [Excluded(owner, b, 0, f"layout ({b.norm})")]
        pdir = package_dir(self.root, b.package)
        rows = read_rows(self.root, b)
        runs, chosen = [], {}
        for d in b.inputs:
            sel = [(no, r) for no, r in rows if self.cel(d.get("when", "true"), r, owner, w)]
            for no, _ in sel:
                if (no, d["variant"]) in chosen:
                    raise WireError(f"{w}: line {no}: two inputs of variant {d['variant']!r}")
                chosen[no, d["variant"]] = d
            if "group_by" in d:
                gb, groups = d["group_by"], {}
                for no, r in sel:
                    groups.setdefault(tuple(r[c] for c in gb), []).append((no, r))
                parts = [groups[k] for k in sorted(groups, key=lambda k: [x.encode("utf-8") for x in k])]
            else:
                parts = [[x] for x in sel]
            for part in parts:
                runs.append(self.one(b, owner, d, part, pdir, w))
        seen = {}
        for r in runs:
            if r.identity in seen:
                raise WireError(f"{w}: run {r.identity} twice")
            seen[r.identity] = r
        done = {no for no, _ in chosen}
        excluded = [Excluded(owner, b, no, "no input declaration selects the line") for no, _ in rows if no not in done]
        return runs, excluded

    def one(self, b, owner, d, part, pdir, w):
        no0 = part[0][0]
        c = d.get("case")
        if c is None:
            heads = part[0][1]
            c = "case" if "case" in heads else "id" if "id" in heads else {"line": True}
        if c == {"line": True}:
            if len(part) != 1:
                raise WireError(f"{w}: case line over a group")
            case = f"line-{no0}"
        elif isinstance(c, dict):
            case = c["literal"]
        else:
            case = constant(part, c, w)
        run = Run(owner, b, d["variant"], case, [no for no, _ in part])
        if "cells" in d:
            run.cells = {k: (x["literal"] if "literal" in x else constant(part, x["column"], f"{w} cells.{k}"))
                         for k, x in d["cells"].items()}
        else:
            a = d["arg_file"]
            if "json" in a:
                run.arg = argument_json(self.argument(a["json"], part, w), w).encode("utf-8")
            elif "literal" in a:
                run.arg = a["literal"].encode("utf-8")
            elif "column" in a:
                run.arg = constant(part, a["column"], w).encode("utf-8")
            else:
                rel = constant(part, a["path_column"], w)
                p = resolve(self.root, self.root, rel, w)
                run.arg, run.arg_path = p.read_bytes(), rel
        for k, f in b.files.items():
            if self.agree(f.get("when", "true"), part, owner, f"{w} files.{k}"):
                run.files[k] = resolve(self.root, pdir if f["base"] == "package" else self.root,
                                       substitute(f["path"], part, f"{w} files.{k}"), f"{w} files.{k}").read_bytes()
        exp = [e for e in b.expect if e["variant"] == d["variant"]
               and self.agree(e.get("when", "true"), part, owner, f"{w} expect")]
        if len(exp) != 1:
            raise WireError(f"{w}: line {no0} variant {d['variant']!r}: {len(exp)} expectations")
        nat = b.native if isinstance(b.native, list) else [b.native]
        nat = [n for n in nat if n.get("variant", d["variant"]) == d["variant"]
               and self.agree(n.get("when", "true"), part, owner, f"{w} native")]
        if len(nat) != 1:
            raise WireError(f"{w}: line {no0} variant {d['variant']!r}: {len(nat)} native forms")
        run.native = nat[0]
        e = exp[0]
        cmp = b.compare if isinstance(b.compare, str) else b.compare.get(d["variant"])
        if cmp is None:
            raise WireError(f"{w}: no compare for variant {d['variant']!r}")
        marker, suffix = None, None
        for m in b.markers:
            if m["variant"] != d["variant"]:
                continue
            cell = constant(part, m["column"], f"{w} marker")
            if (cell.startswith(m["match"]) if m.get("prefix") else cell == m["match"]):
                marker, suffix = m, (cell[len(m["match"]):] if m.get("prefix") else None)
                break
        run.code = e["code"]
        run.compare = cmp
        run.ignore = e.get("ignore", [])
        if marker is None:
            run.value = self.value(e["value"], part, pdir, f"{w} expect")
            run.asserts = self.asserts(e.get("assert", []), part, pdir, f"{w} expect")
        else:
            run.code = marker.get("code", e["code"])
            run.ignore_stdout = bool(marker.get("ignore_stdout"))
            override = marker.get("compare", cmp)
            run.compare = override if isinstance(override, str) else override.get(d["variant"])
            if run.compare is None:
                raise WireError(f"{w}: marker has no comparison for variant {d['variant']!r}")
            if run.ignore_stdout:
                run.value = None
            else:
                run.value = self.value(marker.get("value", e["value"]), part, pdir, f"{w} marker", suffix)
            src = marker.get("assert", [] if "value" in marker else e.get("assert", []))
            run.asserts = self.asserts(src, part, pdir, f"{w} marker", suffix)
        if not run.ignore_stdout:
            check_type(run.value, run.native, f"{w} line {no0}", schema=not run.compare.endswith("subset") and not run.ignore)
        return run


def json_type(v):
    if isinstance(v, bool):
        return "boolean"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return "number"
    return {str: "string", list: "array", dict: "object", bytes: "bytes"}[type(v)]


def check_type(v, native, where, schema=True):
    """Ожидание обязано подходить нативной форме (type и schema): строка 12 при string и decode cell — ошибка.
    При сравнении subset ожидание — часть ответа: схема ответа к нему не прикладывается, только тип."""
    types = native["type"] if isinstance(native["type"], list) else [native["type"]]
    t = json_type(v)
    if "value" not in types and t not in types:
        raise WireError(f"{where}: expected {t} {v!r:.80} is not native {types}")
    if schema and "schema" in native and t != "bytes":
        import jsonschema
        try:
            jsonschema.Draft202012Validator(native["schema"]).validate(v)
        except jsonschema.ValidationError as e:
            raise WireError(f"{where}: expected value fails the native schema: {e.message}") from None


# ---------------------------------------------------------------- урок

def consumers(root):
    """→ {(package от Platform без vectors/, table): {урок}} из consumers.tsv."""
    try:
        return vector_consumers.read(root)
    except vector_consumers.ConsumerError as exc:
        raise WireError(str(exc)) from None


def lesson_bindings(root, owner, bindings=None):
    """Привязки урока: свои пакеты урока и общие, назначенные уроку consumers.tsv."""
    cons = consumers(root)
    if owner not in vector_consumers.lessons(root):
        raise WireError(f"{CONSUMERS}: unknown lesson {owner!r}")
    keys = {key for key, owners in cons.items() if owner in owners}
    bindings = parse(root, keys=keys) if bindings is None else bindings
    for b in bindings:
        for d in b.inputs:
            for o in re.findall(r'owner\s*==\s*"([^"]+)"', d.get("when", "")):
                if o not in cons.get((b.package, b.table), set()):
                    raise WireError(f"{FORM}:{b.line}: owner {o!r} is not a consumer of {b.package} {b.table}")
    return [b for b in bindings
            if b.package.split("/", 1)[0] == owner or owner in cons.get((b.package, b.table), set())]


def expand(root, owner, cel=None):
    """→ ([Run], [Excluded]) урока owner по форме."""
    ex = Expander(root, cel)
    runs, excl = [], []
    for b in lesson_bindings(root, owner):
        r, e = ex.run(b, owner)
        runs += r
        excl += e
    return runs, excl
