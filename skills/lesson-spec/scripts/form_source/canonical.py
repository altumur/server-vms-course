"""Канонический вид спеки — общая часть проекции (ADR-0089 доп. (1) Р10, Р13, Р14): умолчания — только внутри
присутствующего родителя или родителя со своим default; отображение `ordered` — массив `{"name": ключ, …}` в порядке
автора; байты — JCS. Шаги урока 2 (сахар, вычисляемые умолчания) — его закрытый перечень, здесь их нет.
"""
import copy
import json

from .judge import jcs_number
from .source import _is


def project(form, tree):
    def rec(n, v):
        n = form.deref(n)
        if n.variants is not None:
            for vn in n.variants:
                if _is(v, form.types_of(vn)):
                    return rec(vn, v)
            return v
        if isinstance(v, dict) and not n.opaque:
            out = {}
            for k, x in v.items():
                child = (n.properties or {}).get(k) or (n.names[1] if n.names is not None else None)
                out[k] = rec(child, x) if child is not None else x
            for k, c in (n.properties or {}).items():
                if k not in v and form.has_note(c, "default"):
                    out[k] = rec(c, copy.deepcopy(form.note(c, "default")))
            if n.ordered:
                return [dict({"name": k}, **out[k]) for k in v]
            return out
        if isinstance(v, list) and n.items is not None:
            return [rec(n.items, x) for x in v]
        return v
    return rec(form.root, tree)


def _key(k):
    return k.encode("utf-16-be")                     # RFC 8785: ключи по кодовым единицам UTF-16


def jcs(v):
    if v is None or isinstance(v, bool):
        return json.dumps(v)
    if isinstance(v, (int, float)):
        return jcs_number(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(jcs(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(v[k]) for k in sorted(v, key=_key)) + "}"


def canonical_bytes(loader, data):
    """Байты спеки → байты `spec` канонического вида (чистая проекция, без обёртки, Р13); отказ загрузчика — None."""
    from .source import textlayer
    if loader.judge(data)["verdict"] != "ok":
        return None
    tree = textlayer.load_text(data)[0]
    return jcs(project(loader.form, tree)).encode("utf-8")
