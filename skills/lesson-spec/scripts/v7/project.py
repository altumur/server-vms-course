"""Слой 6 В7 — проекция канонического вида (ADR-0092 «Свой остаток» п. 6; P/02.2 Н1.1, ADR-0089) над JSON Schema формы.

По порядку: сахар урока 2 (`tables`, `bound_to`, `in`) на дереве загрузчика; статические умолчания — аннотация `default`
схемы, только внутри присутствующего родителя или родителя со своим умолчанием (Р10); вычисляемые умолчания П1–П5;
отображение `x-ordered` — массив `{"name": ключ, …}` в порядке автора (Р14); байты — JCS (ADR-0072).
"""
import copy
import json
from pathlib import Path

from . import stack

_NONE = object()
FIELDS = (("unit", "fields", "*"), ("tables", "*", "fields", "*"))


def each(v, path):
    if not path:
        yield v
        return
    s, rest = path[0], path[1:]
    if s == "*":
        items = v.values() if isinstance(v, dict) else v if isinstance(v, list) else ()
        for x in list(items):
            yield from each(x, rest)
    elif isinstance(v, dict) and s in v:
        yield from each(v[s], rest)


def fields(t):
    for p in FIELDS:
        for f in each(t, p):
            if isinstance(f, dict):
                yield f


def secret_items(t):
    for f in fields(t):
        for e in f.get("secret_in") or []:
            if isinstance(e, dict):
                yield e


def unit_fields(t):
    u = t.get("unit") if isinstance(t, dict) else None
    fs = u.get("fields") if isinstance(u, dict) else None
    return fs if isinstance(fs, dict) else {}


def sugar(t):
    """P/02.2-02: `tables` списком имён, `bound_to` одним именем, `in` элемента `secret_in` одним словом."""
    if isinstance(t, dict) and isinstance(t.get("tables"), list):
        t["tables"] = {x: {} for x in t["tables"]}
    for f in fields(t):
        if isinstance(f.get("bound_to"), str):
            f["bound_to"] = [f["bound_to"]]
    for e in secret_items(t):
        if isinstance(e.get("in"), str):
            e["in"] = [e["in"]]


def computed(t):
    """P/02.2-03, П1–П5."""
    if "snapshot" not in t:                                       # П1
        t["snapshot"] = [k for k, f in unit_fields(t).items()
                         if not k.endswith("_secret") and k != "server"
                         and not (isinstance(f, dict) and f.get("type") == "blob")]
    if isinstance(t.get("tables"), dict):                         # П2
        for k, tbl in t["tables"].items():
            if isinstance(tbl, dict):
                j = tbl.setdefault("journal", {})
                j.setdefault("written", k + ".written")
                j.setdefault("deleted", k + ".deleted")
    d = t.get("display")                                          # П3
    if isinstance(d, dict) and "form" not in d:
        d["form"] = [{"fields": list(unit_fields(t))}]
    for f in fields(t):                                           # П4
        f.setdefault("default", None)
    for e in secret_items(t):                                     # П5
        if "regex" in e:
            e.setdefault("decoded", True)


def project(sch, tree, ordered=True):
    """Умолчания схемы внутри присутствующего (Р10); ordered — `x-ordered` массивом в порядке автора (Р14)."""
    def rec(s, v):
        chain = sch.resolve(s)
        var = sch.variant(chain, v)
        if var is not None:
            chain = chain + sch.resolve(var)
        if isinstance(v, dict) and not sch.word(chain, "x-opaque"):
            out = {}
            for k, x in v.items():
                c = sch.child(chain, v, k)
                out[k] = rec(c, x) if c is not None else x
            for c0 in chain:
                for k, c in c0.get("properties", {}).items():
                    if k not in v and k not in out:
                        d = sch.word(sch.resolve(c), "default", _NONE)
                        if d is not _NONE:
                            out[k] = rec(c, copy.deepcopy(d))
            if ordered and sch.word(chain, "x-ordered"):
                return [dict({"name": k}, **out[k]) for k in v]
            return out
        if isinstance(v, list):
            return [rec(sch.child(chain, v, i), x) if sch.child(chain, v, i) is not None else x
                    for i, x in enumerate(v)]
        return v
    return rec(sch.doc, tree)


def canonical(sch, tree):
    t = copy.deepcopy(tree)
    sugar(t)
    t = project(sch, t, ordered=False)
    computed(t)
    return project(sch, t)


def canonical_bytes(manifest, data):
    """Байты манифеста → байты `manifest` вида; отказ загрузчика В7 — None."""
    r = manifest.judge(data)
    if r["verdict"] != "ok":
        return None
    return stack.jcs(canonical(manifest.sch, r["tree"])).encode("utf-8")


def seta():
    """Набор А, векторы canonical P/02.2: байты вида В7 = expect/<case>.json (байты построителя эталона)."""
    from v7.seta import ROOT, tsv, v7_manifest
    vec = ROOT / "Platform/02-installer/vectors/canonical"
    m, _ = v7_manifest()
    out = []
    for no, cols in enumerate(tsv(vec / "cases.tsv")):
        case, inp, expect, _note = cols
        if case == "case":
            continue
        want = (vec / expect).read_bytes()
        got = canonical_bytes(m, (ROOT / inp).read_bytes())
        out.append({"case": case, "bytes_eq": got == want, "v7": None if got is None else got.decode("utf-8")[:200],
                    "want": want.decode("utf-8")[:200]})
    return out
