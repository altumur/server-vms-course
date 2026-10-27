"""Корпус семей набора А (ADR-0092 п. 13; ADR-0087 доп. (9) п. 1–2): экземпляры каждой семьи каталога с исходом эталона.

Строка корпуса — вход пакета `family-read` (семья, режим, текст) и исход эталона (вердикт, пути, исход `outcomes.tsv`):
    {"family": key, "kind": row|object|file, "schema": путь схемы, "mode": writer|reader, "text": текст экземпляра,
     "why": что меняет мутация, "ref": {"verdict", "paths", "outcomes"}}
Текст строки (`row`) — JSON-объект items (значения — строки), объекта — JSON, файла — текст файла.

Базовый экземпляр строится из формы и чинится по отказам эталона (писатель). Мутации: корень `null`; на каждом месте —
чужой тип, хвостовой `\\n` и нарушение `pattern`, вне `enum`, слово `not_enum`, совпадение `not_pattern`, `max_bytes`,
`unique_items`, `min_items`, `max_items` (и имена сверх него), целое `1.0`, `1.5`, `100.00000000000000001`, вне
границ, время `1e0`/`-1`/`1.0001`; у отображения — без обязательного ключа, лишний ключ, имя не по форме
(`propertyNames`); у строки — записи кодека не по форме. На каждую строку `outcomes.tsv` — экземпляр, где она
действует, или пометка «недостижима».
"""
import copy
import json
import re
from pathlib import Path

from form_source import families as fam
from form_source.source import ANY

from v7 import build, stack

ROOT = Path(__file__).resolve().parents[4]


class EncText(str):
    """Текст места `encoding` как есть (мутация записи JSON внутри строки)."""


class Raw:
    """Число с записью (в тексте JSON — как есть): `1.0`, `1e0`, `100.00000000000000001`."""

    def __init__(self, text):
        self.text = text


def dump(v):
    if isinstance(v, Raw):
        return v.text
    if v is None or isinstance(v, bool):
        return json.dumps(v)
    if isinstance(v, (int, float, str)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(dump(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + dump(x) for k, x in v.items()) + "}"


# ---------------------------------------------------------------- образец строки по выражению диалекта

def _parse(p):
    """Выражение диалекта → дерево: ('seq', [..]) ('alt', [..]) ('lit', c) ('cls', neg, [(lo, hi)]) ('rep', x, m, n)."""
    i = 0

    def atom():
        nonlocal i
        c = p[i]
        if c == "(":
            i += 1
            x = alt()
            i += 1
            return x
        if c == "[":
            i += 1
            neg = p[i:i + 1] == "^"
            if neg:
                i += 1
            ranges, first = [], True
            while first or p[i] != "]":
                first = False
                a = ch()
                if p[i:i + 1] == "-" and p[i + 1:i + 2] not in ("]", ""):
                    i += 1
                    b = ch()
                    ranges.append((a, b))
                else:
                    ranges.append((a, a))
            i += 1
            return ("cls", neg, ranges)
        if c == ".":
            i += 1
            return ("cls", True, [])
        return ("lit", ch())

    def ch():
        nonlocal i
        m = re.match(r"\\x\{([0-9A-Fa-f]{2,6})\}", p[i:])
        if m:
            i += len(m.group(0))
            return chr(int(m.group(1), 16))
        if p[i] == "\\":
            i += 2
            return p[i - 1]
        i += 1
        return p[i - 1]

    def rep():
        nonlocal i
        x = atom()
        while i < len(p) and p[i] in "*+?{":
            c = p[i]
            if c == "{":
                m = re.match(r"\{([0-9]+)(?:,([0-9]+))?\}", p[i:])
                i += len(m.group(0))
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.group(2) is not None else lo
                x = ("rep", x, lo, hi)
            else:
                i += 1
                x = ("rep", x, {"*": 0, "+": 1, "?": 0}[c], {"*": None, "+": None, "?": 1}[c])
        return x

    def seq():
        out = []
        while i < len(p) and p[i] not in "|)":
            out.append(rep())
        return ("seq", out)

    def alt():
        nonlocal i
        out = [seq()]
        while i < len(p) and p[i] == "|":
            i += 1
            out.append(seq())
        return ("alt", out)
    return alt()


def _pick(neg, ranges, avoid=""):
    if not neg:
        for lo, hi in ranges:
            for c in ("a", "x", "0", lo):
                if lo <= c <= hi and c not in avoid:
                    return c
        return ranges[0][0]
    for c in "ax0Z_-":
        if not any(lo <= c <= hi for lo, hi in ranges):
            return c
    return "\u00e9"


def sample(p, longer=0):
    """Короткая строка, которую выражение берёт целиком; longer — у повторов брать больше (вариант)."""
    def gen(x):
        k = x[0]
        if k == "seq":
            return "".join(gen(y) for y in x[1])
        if k == "alt":
            return gen(x[1][min(longer, len(x[1]) - 1)]) if longer else gen(x[1][0])
        if k == "lit":
            return x[1]
        if k == "cls":
            return _pick(x[1], x[2])
        if k == "rep":
            n = x[2] if not longer else min(x[3] if x[3] is not None else x[2] + 2, x[2] + 2)
            return gen(x[1]) * max(n, 0)
        raise ValueError(x)
    return gen(_parse(p))


def fits(n, s):
    if n.pattern is not None and not re.fullmatch(stack_py(n.pattern), s, re.S):
        return False
    if n.not_pattern is not None and re.fullmatch(stack_py(n.not_pattern), s, re.S):
        return False
    if n.not_enum is not None and s in n.not_enum:
        return False
    return n.max_bytes is None or len(s.encode("utf-8")) <= n.max_bytes


def stack_py(p):
    from form_source.source import py_pattern
    return py_pattern(p)


# ---------------------------------------------------------------- базовый экземпляр

class Gen:
    def __init__(self, form):
        self.f = form

    def value(self, n, depth=0):
        f = self.f
        t = f.deref(n)
        if t.variants:
            return self.value(t.variants[0], depth)
        if t.enum:
            return copy.deepcopy(t.enum[0])
        types = t.types or ["any"]
        for ty in ("object", "array", "string", "time", "integer", "number", "boolean", "any", "null"):
            if ty in types:
                return self.of(t, ty, depth, n)
        return None

    def of(self, t, ty, depth, site):
        if ty == "object":
            if t.opaque:
                return {}
            out = {}
            for k in t.required:
                if t.properties and k in t.properties:
                    out[k] = self.value(t.properties[k], depth + 1)
            if t.names is not None and (t.min_items or 0) > 0:
                out[self.name(t.names[0])] = self.value(t.names[1], depth + 1)
            return out
        if ty == "array":
            if t.items is None:
                return []
            n = max(t.min_items or 0, 1 if depth < 6 else 0)
            out = []
            for i in range(n):
                v = self.value(t.items, depth + 1)
                if t.unique_items and isinstance(v, str):
                    v = v + ("%d" % i if i else "")
                out.append(v)
            return out
        if ty == "string":
            return self.string(t)
        if ty == "time":
            return "1"
        if ty in ("integer", "number"):
            lo = t.minimum if t.minimum is not None else (t.exclusive_minimum + 1 if t.exclusive_minimum is not None
                                                          else 0)
            v = max(lo, 1) if t.maximum is None or t.maximum >= 1 else lo
            if t.maximum is not None:
                v = min(v, t.maximum)
            return int(v) if ty == "integer" or float(v).is_integer() else v
        if ty == "boolean":
            return True
        if ty == "any":
            return "x"
        return None

    def string(self, t):
        cands = []
        w = t.writer
        for p in ([w.pattern] if w is not None and w.pattern is not None else []) + \
                ([t.pattern] if t.pattern is not None else []):
            cands += [sample(p), sample(p, 1), sample(p, 2)]
        if w is not None and w.enum:
            cands = [x for x in w.enum if isinstance(x, str)] + cands
        cands += ["a", "x1", "ab"]
        for s in cands:
            if fits(t, s) and (w is None or fits(w, s)) and (w is None or not w.enum or s in w.enum):
                return s
        return cands[0]

    def name(self, n):
        t = self.f.deref(n)
        if t.enum:
            return t.enum[0]
        s = self.string(t)
        return s if isinstance(s, str) else "a"


# ---------------------------------------------------------------- запись экземпляра (кодек писателя)

def encode_row(form, value):
    """Значения строки → items (строки) записью писателя (codec.tsv)."""
    t = form.deref(form.root)
    out = {}
    for k, v in value.items():
        node = (t.properties or {}).get(k) or (t.names[1] if t.names is not None else None)
        if v is None or node is None:
            continue
        out[k] = encode_item(form, node, v)
    return out


def encode_item(form, node, v):
    t = form.deref(node)
    if isinstance(v, EncText):
        return str(v)
    if t.encoding == "jcs":
        return stack.jcs(v)
    if t.encoding == "json":
        return dump(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return stack.plain_decimal(v)
    if isinstance(v, list):
        return stack.list_text(v)
    return v


def encode_value(form, n, v):
    """Объект или файл: места `encoding` — текст JSON разобранного значения."""
    f = form
    t = f.deref(n)
    if isinstance(v, EncText):
        return str(v)
    if t.variants:
        for vn in t.variants:
            if _jtype_ok(f, vn, v):
                return encode_value(f, vn, v)
        return v
    if isinstance(v, dict) and not t.opaque:
        out = {}
        for k, x in v.items():
            c = (t.properties or {}).get(k) or (t.names[1] if t.names is not None else None)
            out[k] = encode_value(f, c, x) if c is not None else x
        v = out
    elif isinstance(v, list) and t.items is not None:
        v = [encode_value(f, t.items, x) for x in v]
    if t.encoding == "jcs" and not isinstance(v, Raw):
        return stack.jcs(v)
    if t.encoding == "json" and not isinstance(v, Raw):
        return dump(v)
    return v


def _jtype_ok(f, n, v):
    from form_source.source import _is
    return _is(v, f.types_of(n))


# ---------------------------------------------------------------- эталон

class Ref:
    def __init__(self, family):
        self.fam = family
        self.j = {m: fam.Judge(family.form, m) for m in ("writer", "reader")}

    def judge(self, text, mode):
        k = self.fam.kind
        if k == "row":
            try:
                value = json.loads(text)
            except ValueError:
                value = text
        elif k == "file":
            value = text.encode("utf-8")
        else:
            value = text
        try:
            r = self.j[mode].judge(value, k)
        except Exception as exc:                 # noqa: BLE001 — падение эталона: исход «авария» (дефект эталона)
            return {"verdict": "crash", "paths": [], "outcomes": [], "why": "%s: %s" % (type(exc).__name__, exc)}
        outs = fam.outcomes_for(self.fam.outcomes, r["paths"]) if mode == "reader" else []
        return {"verdict": r["verdict"], "paths": r["paths"], "outcomes": [o.path for o in outs]}


def text_of(family, value):
    k = family.kind
    if k == "row":
        return dump(encode_row(family.form, value))
    v = encode_value(family.form, family.form.root, value)
    if k == "file":
        return v if isinstance(v, str) else dump(v)
    return dump(v)


def base_instance(family, ref):
    """Базовый экземпляр, принятый эталоном у писателя (и читателя); починка по путям отказа: недостающий ключ —
    дописать, лишний или запрещённый — снять."""
    g, f = Gen(family.form), family.form
    v = g.value(f.root)
    for _ in range(12):
        t = text_of(family, v)
        r = ref.judge(t, "writer")
        if r["verdict"] == "ok":
            return v, t
        changed = False
        for p in r["paths"]:
            segs = fam.unpointer(p)
            try:
                parent = v
                for s in segs[:-1]:
                    parent = parent[int(s)] if isinstance(parent, list) else parent[s]
            except (KeyError, IndexError, ValueError, TypeError):
                continue
            last = segs[-1] if segs else None
            if isinstance(parent, dict) and last is not None:
                if last in parent:
                    del parent[last]
                else:
                    n = fam.place(f, p)
                    if n is not None:
                        parent[last] = g.value(n)
                changed = True
        if not changed:
            break
    return None, None


# ---------------------------------------------------------------- мутации

def places(form, v, path=()):
    """(путь, узел, значение) каждого места базового экземпляра."""
    yield list(path), form.root if not path else None, v


def walk(form, n, v, path):
    yield path, n, v
    t = form.deref(n)
    if t.variants:
        for vn in t.variants:
            if _jtype_ok(form, vn, v):
                yield from walk(form, vn, v, path)
                return
        return
    if isinstance(v, dict) and not t.opaque:
        for k, x in v.items():
            c = (t.properties or {}).get(k) or (t.names[1] if t.names is not None else None)
            if c is not None:
                yield from walk(form, c, x, path + [k])
    elif isinstance(v, list) and t.items is not None:
        for i, x in enumerate(v):
            yield from walk(form, t.items, x, path + [i])


def setat(v, path, x):
    v = copy.deepcopy(v)
    if not path:
        return x
    cur = v
    for s in path[:-1]:
        cur = cur[s]
    cur[path[-1]] = x
    return v


def delat(v, path):
    v = copy.deepcopy(v)
    cur = v
    for s in path[:-1]:
        cur = cur[s]
    del cur[path[-1]]
    return v


def mutations(family, base):
    """(why, значение или ('text', текст))."""
    f = family.form
    out = [("root null", ("text", "null"))]
    if family.kind != "row":
        out.append(("not JSON", ("text", "{")))
    for path, n, v in walk(f, f.root, base, []):
        t = f.deref(n)
        here = "/".join(map(str, path))
        types = f.types_of(n)
        if path:
            out.append(("%s: wrong type" % here, setat(base, path, [] if not isinstance(v, list) else {"zz": 1})))
        if t.encoding is not None:
            for bad in ("1e400", '{"zz":1e400}', "[1e400]", '{"b":1,"a":2}', "{", "NaN"):
                out.append(("%s: encoded %s %r" % (here, t.encoding, bad), setat(base, path, EncText(bad))))
        if isinstance(v, str):
            out.append(("%s: trailing \\n" % here, setat(base, path, v + "\n")))
            if t.pattern is not None:
                out.append(("%s: pattern violated" % here, setat(base, path, "")))
                out.append(("%s: pattern violated (space)" % here, setat(base, path, v + " !")))
            if t.enum is not None:
                out.append(("%s: not in enum" % here, setat(base, path, "zz_not_in_enum")))
            if t.not_enum:
                out.append(("%s: not_enum word" % here, setat(base, path, t.not_enum[0])))
            if t.not_pattern is not None:
                s = sample(t.not_pattern)
                out.append(("%s: not_pattern match" % here, setat(base, path, s)))
            mb = t.max_bytes if t.max_bytes is not None else (t.writer.max_bytes if t.writer is not None else None)
            if mb is not None:
                out.append(("%s: max_bytes" % here, setat(base, path, "\u00e9" * (mb // 2 + 1))))
            if "time" in types:
                out.append(("%s: time 1e0" % here, setat(base, path, "1e0")))
                out.append(("%s: time -1" % here, setat(base, path, "-1")))
                out.append(("%s: time 1.0001" % here, setat(base, path, "1.0001")))
        if "time" in types and family.kind != "row" and path:
            out.append(("%s: time number 1e0" % here, setat(base, path, Raw("1e0"))))
            out.append(("%s: time number 1.5" % here, setat(base, path, Raw("1.5"))))
        if "integer" in types and "number" not in types and path:
            for raw in ("1.0", "1e0", "1.5", "100.00000000000000001", "-0.0", "1e400"):
                out.append(("%s: integer %s" % (here, raw), setat(base, path, Raw(raw))))
            if t.minimum is not None:
                out.append(("%s: below minimum" % here, setat(base, path, t.minimum - 1)))
            if t.maximum is not None:
                out.append(("%s: above maximum" % here, setat(base, path, t.maximum + 1)))
            out.append(("%s: 2^53" % here, setat(base, path, 2 ** 53)))
        if "number" in types and path:
            out.append(("%s: number 1e400" % here, setat(base, path, Raw("1e400"))))
        if isinstance(v, list):
            if v:
                out.append(("%s: duplicate item" % here, setat(base, path, v + [copy.deepcopy(v[0])])))
            out.append(("%s: empty list" % here, setat(base, path, [])))
            mi = t.max_items if t.max_items is not None else (t.writer.max_items if t.writer is not None else None)
            if mi is not None and v:
                out.append(("%s: max_items" % here, setat(base, path, v + [copy.deepcopy(v[0])] * (mi + 1))))
        if isinstance(v, dict) and not t.opaque:
            for k in t.required:
                if k in v:
                    out.append(("%s: without required %s" % (here, k), delat(base, path + [k])))
            for k in (t.properties or {}):
                if k not in v:
                    g = Gen(f)
                    out.append(("%s: optional %s" % (here, k), setat(base, path + [k], g.value(t.properties[k]))))
            if t.names is None and t.properties is not None:
                out.append(("%s: unknown key" % here, setat(base, path + ["zz_extra"], 1)))
            if t.names is not None:
                g = Gen(f)
                val = g.value(t.names[1])
                for bad in ("", "Bad Name!", "a\n", "/x", "zz_extra"):
                    out.append(("%s: name %r" % (here, bad), setat(base, path + [bad], val)))
                mi = t.max_items if t.max_items is not None else (t.writer.max_items if t.writer is not None else None)
                if mi is not None:
                    more = dict(v)
                    for i in range(mi + 1):
                        more["n%d" % i] = val
                    out.append(("%s: names over max_items" % here, setat(base, path, more)))
    if family.kind == "row":
        t = f.deref(f.root)
        for k, c in (t.properties or {}).items():
            for bad in ("1.0", "x", "True", "1e0", "[1", "{", '{"b":1,"a":2}', "a,,b", "", " 1"):
                out.append(("item %s: record %r" % (k, bad), ("items", k, bad)))
    return out


def targeted(family, base, opath):
    """Экземпляр на строку outcomes.tsv: на месте её пути — значение чужого типа (родители достраиваются)."""
    f, g = family.form, Gen(family.form)
    segs = fam.unpointer(opath) if opath else []
    if not segs:
        return None
    v = copy.deepcopy(base)
    cur, prefix = v, ""
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        if isinstance(cur, list):
            if not cur:
                n = fam.place(f, prefix + "/*")
                cur.append(g.value(n) if n is not None else {})
            s = 0
        elif isinstance(cur, dict):
            if s == "*":
                s = next(iter(cur), None) or "a"
        else:
            return None
        prefix += "/" + str(s if segs[i] != "*" else "*")
        if last:
            n = fam.place(f, "/".join([""] + [x for x in segs]))
            types = f.types_of(n) if n is not None else ["any"]
            bad = 12345 if ("array" in types or "object" in types or "string" in types) else []
            if "integer" in types and "string" not in types:
                bad = "zz_wrong"
            if isinstance(cur, list):
                cur[s] = bad
            else:
                cur[s] = bad
            return v
        if isinstance(cur, dict) and s not in cur:
            n = fam.place(f, "/" + "/".join(str(x) for x in segs[:i + 1]))
            cur[s] = g.value(n) if n is not None else {}
            if not isinstance(cur[s], (dict, list)):
                cur[s] = {}
        cur = cur[s]
    return v


def row_text(family, base, m):
    if isinstance(m, tuple) and m[0] == "text":
        return m[1]
    if isinstance(m, tuple) and m[0] == "items":
        items = json.loads(text_of(family, base))
        items[m[1]] = m[2]
        return dump(items)
    return text_of(family, m)


def corpus(root=ROOT):
    """Строки корпуса семей: каждая семья каталога, оба режима."""
    rows = []
    for row, family, sch in build.all_families(root):
        fobj = fam.load_family(root, row)
        ref = Ref(fobj)
        base, t0 = base_instance(fobj, ref)
        lesson = row["schema"][:2]
        meta = {"family": row["key"], "kind": row["kind"], "schema": row["schema"], "lesson": lesson}
        if base is None:
            rows.append(dict(meta, mode="writer", text=None, why="no base instance", ref=None))
            continue
        texts = [("base", t0)]
        muts = list(mutations(fobj, base))
        for o in fobj.outcomes:
            tv = targeted(fobj, base, o.path)
            if tv is not None:
                muts.append(("outcome %s: wrong type" % o.path, tv))
        for why, m in muts:
            try:
                texts.append((why, row_text(fobj, base, m)))
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        seen = set()
        for why, text in texts:
            if text in seen:
                continue
            seen.add(text)
            for mode in ("writer", "reader"):
                rows.append(dict(meta, mode=mode, text=text, why=why, ref=ref.judge(text, mode)))
        rows += uncovered(fobj, ref, meta, rows)
    return rows


def uncovered(family, ref, meta, rows):
    """Строки outcomes.tsv, которых не выбрал ни один экземпляр семьи: пометка (недостижима генератором или нормой)."""
    hit = set()
    for r in rows:
        if r["family"] == meta["family"] and r["kind"] == meta["kind"] and r.get("ref") and r["mode"] == "reader":
            hit.update(r["ref"]["outcomes"])
    return [dict(meta, mode="reader", text=None, why="outcome %r not reached" % o.path, ref=None)
            for o in family.outcomes if o.path not in hit]


# ---------------------------------------------------------------- набор А: стек В7 на корпусе

def v7_judge(sch, kind, text, mode, go=None, schema_file=None):
    fam_v7 = stack.Family(sch, kind)
    if kind == "row":
        try:
            value = json.loads(text)
        except ValueError:
            value = text
    elif kind == "file":
        value = text.encode("utf-8")
    else:
        value = text
    if go is None:
        return fam_v7.judge(value, mode)
    return go_family(fam_v7, value, mode, go, schema_file)


def go_family(fv, value, mode, go, schema_file):
    """Тот же проход, что stack.Family.judge, но проверка схемы — библиотекой Go."""
    orig = stack.py_records

    def recs(validator, instance, schema=None):
        return go.records(schema_file, _plain(instance), "" if schema is None else "#/$defs/writer")
    stack.py_records = recs
    try:
        return fv.judge(value, mode)
    finally:
        stack.py_records = orig


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, float) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, int) and not isinstance(v, bool):
        return int(v)
    return v


def seta(go=None):
    out_dir = Path(__file__).resolve().parent / "out"
    cache = {}
    rows = []
    for r in corpus():
        if r["text"] is None:
            rows.append(dict(r, v7=None, verdict_eq=False, paths_eq=False, outcome_eq=False, note="no instance"))
            continue
        key = (r["schema"], r["kind"])
        if key not in cache:
            rel = "families/" + r["schema"].replace("/data/", "/").replace(".form.yaml", ".schema.json")
            p = out_dir / rel
            alt = out_dir / rel.replace(".schema.json", ".%s.schema.json" % r["kind"])
            p = alt if alt.exists() else p
            cache[key] = (json.loads(p.read_text(encoding="utf-8")), p, fam.load_family(ROOT, _catrow(r)))
        sch, p, fobj = cache[key]
        v = v7_judge(sch, r["kind"], r["text"], r["mode"], go, p)
        outs = [o.path for o in fam.outcomes_for(fobj.outcomes, v["paths"])] if r["mode"] == "reader" else []
        ref = r["ref"]
        rows.append(dict(r, v7={"verdict": v["verdict"], "paths": v["paths"], "outcomes": outs},
                         verdict_eq=ref["verdict"] == v["verdict"], paths_eq=ref["paths"] == v["paths"],
                         outcome_eq=ref["outcomes"] == outs))
    return rows


_CAT = None


def _catrow(r):
    global _CAT
    if _CAT is None:
        _CAT = {(x["key"], x["kind"], x["schema"]): x for x in fam.read_catalog(ROOT)}
    return _CAT[(r["family"], r["kind"], r["schema"])]
