"""Проход ссылок (ADR-0085): строки 02-…references.tsv над деревом, прошедшим схему. Словарь check — CHECKS."""
from pathlib import Path


def _platform_list(name):
    """Закрытый список платформы из Source/tests/testdata/platform_lists.tsv (байты — «Спецификация»), не из кода."""
    for base in Path(__file__).resolve().parents:
        table = base / "Source" / "tests" / "testdata" / "platform_lists.tsv"
        if table.is_file():
            rows = (line.split("\t") for line in table.read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#"))
            words = {row[1] for row in rows if len(row) == 2 and row[0] == name}
            if not words:
                raise RuntimeError(f"platform_lists.tsv names no {name}")
            return words
    raise RuntimeError("platform_lists.tsv not found above spec_schema/")


PLATFORM_SHOWN = _platform_list("platform_shown")
OBJECT_FAMILIES = _platform_list("object_families")


# Слова прохода: по ветке в ok(); новое слово в references.tsv — новая ветка здесь.
CHECKS = {
    "unit_field", "row_field", "row_fields_nonsecret", "row_field_login", "row_field_secret", "unit_id",
    "int_unit_field", "fixed_unit_field", "in_enum", "schema_depth", "not_unit_rows", "table", "table_field",
    "table_count", "metric_where", "own_table", "table_without_secret", "unit_rows", "not_self", "snapshot_member",
    "group_by_url", "home", "unplaced", "display_name", "form_name", "option_name", "option_value", "domain_key_id",
    "request_key", "table_key", "outcome_key", "stamp_group", "requires", "le", "metric", "unique", "door_pass",
    "object_family", "no_nested_prefix", "own_sub", "ne", "not_in", "book_with_from", "token_claims", "unique_by",
    "shared_item",
}
CLASSES = {"reference", "value"}


def load_rows(path):
    """references.tsv → [(сегменты пути, check, class)]; строка не по форме или слово вне CHECKS — ValueError."""
    out = []
    with open(path, encoding="utf-8") as f:
        for no, l in enumerate(f, 1):
            l = l.rstrip("\n")
            if not l or l.startswith("#") or l.startswith("path\t"):
                continue
            cols = l.split("\t")
            if len(cols) != 4 or not all(cols[:3]):
                raise ValueError("line %d: expected path, check, class, norm" % no)
            path, check, cls, _ = cols
            if check.partition(":")[0] not in CHECKS or cls not in CLASSES:
                raise ValueError("line %d: unknown check %r or class %r" % (no, check, cls))
            out.append((path.split("."), check, cls))
    return out


def walk(node, segs, trail):
    """→ (значение, trail): trail — [(контейнер, ключ)] от корня до значения."""
    if not segs:
        yield node, trail
        return
    s, rest = segs[0], segs[1:]
    if s.endswith("[]"):
        name = s[:-2]
        if name:
            if not isinstance(node, dict) or name not in node:
                return
            node, trail = node[name], trail + [(node, name)]
        if isinstance(node, list):
            for i, x in enumerate(node):
                yield from walk(x, rest, trail + [(node, i)])
    elif s == "*":
        if isinstance(node, dict):
            for k, x in node.items():
                yield from walk(x, rest, trail + [(node, k)])
    elif s == "{}":
        if isinstance(node, dict) and not rest:
            for k in node:
                yield k, trail + [(node, k)]
    elif isinstance(node, dict) and s in node:
        yield from walk(node[s], rest, trail + [(node, s)])


def get(doc, path):
    node = doc
    for s in path.split("."):
        if not isinstance(node, dict) or s not in node:
            return None
        node = node[s]
    return node


class Doc:
    def __init__(self, doc):
        self.doc = doc
        self.unit = (doc.get("unit") or {}).get("fields") or {}
        t = doc.get("tables")
        self.tables = t if isinstance(t, dict) else {n: {} for n in (t or [])}
        self.metrics = [m.get("name") for m in doc.get("metrics") or []]
        self.status_words = {s.get("field") for f in get(doc, "display.form") or [] for s in f.get("status") or []}

    def table_fields(self, t):
        return (self.tables.get(t) or {}).get("fields") or {} if isinstance(t, str) else {}

    def all_table_fields(self):
        return {n for t in self.tables.values() for n in (t or {}).get("fields") or {}}


def ftype(f):
    return (f or {}).get("type", "string")


def secret(name):
    return isinstance(name, str) and name.endswith("_secret")


def row_fields(d, trail):
    return d.table_fields(trail[1][1]) if trail and trail[0][1] == "tables" else d.unit


def sibling(trail, rel):
    """rel: «x» — ключ родителя значения; «..x» — ключ на уровень выше; «@key» — ключ, под которым значение."""
    if rel == "@key":
        return trail[-1][1]
    up = 1
    while rel.startswith(".."):
        rel, up = rel[2:], up + 1
    c = trail[-up][0] if len(trail) >= up else None
    return c.get(rel) if isinstance(c, dict) else None


def template_parts(s):
    parts, i = [], 0
    while True:
        a = s.find("{", i)
        if a < 0:
            return parts
        b = s.find("}", a)
        if b < 0:
            return parts + [None]
        parts.append(s[a + 1:b])
        i = b + 1


def depth(x):
    if isinstance(x, dict):
        return 1 + max([depth(v) for v in x.values()] or [0])
    if isinstance(x, list):
        return 1 + max([depth(v) for v in x] or [0])
    return 0


def no_nested(names):
    p = sorted(n for n in names if isinstance(n, str) and n.endswith("/"))
    return all(not b.startswith(a) for i, a in enumerate(p) for b in p[i + 1:])


def ok(check, arg, v, trail, d):  # noqa: C901 — словарь check, по ветке на слово
    doc = d.doc
    if check == "unit_field":
        return v in d.unit
    if check == "row_field":
        return v in row_fields(d, trail)
    if check == "row_fields_nonsecret":
        return not isinstance(v, str) or (v in row_fields(d, trail) and not secret(v))
    if check == "row_field_login":
        f = row_fields(d, trail)
        return v in f and not secret(v) and ftype(f[v]) != "url"
    if check == "row_field_secret":
        return v in row_fields(d, trail) and secret(v)
    if check == "unit_id":
        return v == "numeric" or (v in d.unit and not secret(v) and ftype(d.unit[v]) == "string")
    if check == "int_unit_field":
        return v in d.unit and ftype(d.unit[v]) == "int"
    if check == "fixed_unit_field":
        return v in d.unit and (d.unit[v] or {}).get("fixed") is True
    if check == "in_enum":
        e = trail[-1][0].get("enum")
        return e is None or v is None or v in e
    if check == "schema_depth":
        return depth(v) <= int(arg)
    if check == "not_unit_rows":
        return v != get(doc, "unit.rows")
    if check == "table":
        return v in d.tables
    if check == "table_field":
        return v in d.table_fields(sibling(trail, arg))
    if check == "table_count":
        return v[len("table "):] in d.tables
    if check == "metric_where":
        c = sibling(trail, "..count")
        return v in (d.table_fields(c[len("table "):]) if isinstance(c, str) else d.unit)
    if check == "own_table":
        return v in d.tables and v != get(doc, "unit.rows")
    if check == "table_without_secret":
        return not any(secret(n) for n in d.table_fields(v))
    if check == "unit_rows":
        return v == get(doc, "unit.rows")
    if check == "not_self":
        return v != doc.get("name")
    if check == "snapshot_member":
        return not secret(v) and v != "server" and ftype(d.unit.get(v)) != "blob"
    if check == "group_by_url":
        return ftype(d.unit.get(get(doc, "placement.group_by.field"))) == "url"
    if check == "home":
        return get(doc, "placement.near") is not None if v == "near" else v in d.unit
    if check == "unplaced":
        uid = get(doc, "unit.id")
        fixed = [n for n, f in d.unit.items() if (f or {}).get("fixed") is True and n != uid]
        about = get(doc, "about.field")
        return not fixed and (about is None or about == uid)
    if check == "display_name":
        return v in d.unit or v in d.all_table_fields() or v in d.status_words or v in PLATFORM_SHOWN
    if check == "form_name":
        return v in d.unit or v in PLATFORM_SHOWN
    if check == "option_name":
        return v in d.status_words or (v in d.unit and "enum" in (d.unit[v] or {}))
    if check == "option_value":
        name = trail[-2][1]
        if name in d.status_words or name not in d.unit:
            return True
        return v in [str(x).lower() if isinstance(x, bool) else x for x in d.unit[name].get("enum") or []]
    if check == "domain_key_id":
        return v in [k.get("id") for k in get(doc, "domain.keys") or []]
    if check == "request_key":
        props = get(doc, "requests.schema.properties") or {}
        for p in template_parts(v):
            name, _, conv = (p or "").partition(":")
            t = (props.get(name) or {}).get("type") if isinstance(props.get(name), dict) else None
            if p is None or secret(name) or name not in props or conv not in ("", "int"):
                return False
            if (conv == "int" and t not in ("integer", "number")) or (conv != "int" and t != "string"):
                return False
        return True
    if check == "table_key":
        f = d.table_fields(trail[1][1])
        parts = template_parts(v) if "{" in v else [v]
        for p in parts:
            name, _, conv = (p or "").partition(":")
            if p is None or name not in f or secret(name) or conv not in ("", "int"):
                return False
            if (conv == "int" and ftype(f[name]) not in ("int", "float")) or (conv != "int" and ftype(f[name]) != "string"):
                return False
        return True
    if check == "outcome_key":
        return v != "fetched" or get(doc, "requests.key") is not None
    if check == "stamp_group":
        return v != "group" or get(doc, "placement.group_by") is not None
    if check == "requires":
        return get(doc, arg) is not None
    if check == "le":
        o = trail[-1][0].get(arg)
        return not isinstance(o, (int, float)) or v <= o
    if check == "metric":
        return v in d.metrics
    if check == "unique":
        return len(v) == len({repr(x) for x in v})
    if check == "door_pass":
        return v not in (get(doc, "door.routes") or []) and v != get(doc, "unit.rows") and v != "where"
    if check == "object_family":
        return v.split("/")[0] not in OBJECT_FAMILIES
    if check == "no_nested_prefix":
        return no_nested(v)
    if check == "own_sub":
        return v.split("/")[0] == doc.get("name")
    if check == "ne":
        return v != trail[-1][0].get(arg)
    if check == "not_in":
        return v not in (get(doc, arg) or [])
    if check == "book_with_from":
        b = (get(doc, "domain.books") or {}).get(v[:-1])
        return isinstance(b, dict) and "from" in b
    if check == "token_claims":
        claims = v.get("claims") or []
        for scope, extra in (("placement", ()), ("unit", ()), ("scenario", ("trigger_claim", "acts_claim", "up_claim"))):
            s = v.get(scope)
            if isinstance(s, dict):
                named = [s.get(k) for k in ("ref_claim", "audience_claim") + extra]
                if any(n not in claims for n in named) or len(set(named)) != len(named):
                    return False
        return True
    if check == "unique_by":
        ids = [x.get(arg) for x in v]
        return len(ids) == len(set(ids))
    if check == "shared_item":
        names = [x if isinstance(x, str) else x.get("name") for x in trail[-1][0]]
        if names.count(v if isinstance(v, str) else v.get("name")) > 1:
            return False
        if isinstance(v, dict):
            return v.get("name") not in d.unit
        f = d.unit.get(v)
        return f is not None and ("inherit" in f or v == get(doc, "display.tree.group_by"))
    raise ValueError("unknown check " + check)


def check(doc, rows):
    d = Doc(doc)
    found = []
    for segs, chk, cls in rows:
        name, _, arg = chk.partition(":")
        for v, trail in walk(doc, segs, []):
            if not ok(name, arg, v, trail, d):
                found.append((cls, ".".join(str(k) for _, k in trail), chk))
    return found
