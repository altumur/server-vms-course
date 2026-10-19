"""Загрузчик формы, построенный из источника: интерпретатор диалекта (ADR-0087 п. 5) поверх слоя текста Н1.1.

Слои (Н3): текст → форма (имя, ключи, значения) → отношения references.tsv (только при чистой форме). Класс файла —
первый непустой из name, key, value, reference; пути — только отказов этого класса (свод Ф21), множеством в каноническом
порядке по байтам JSON Pointer (доп. (3) Р2). Решения свода журналов — в местах с их номерами.
"""
import json
import math
import re

from .source import Form, _is, _jt, load_source, form_segs, textlayer

_ABSENT = object()
SCALAR_CHECKS = {"in", "not in", "=", "!=", "<=", "~", "!~", "template"}


# ---------------------------------------------------------------- значения

def same(a, b):
    """Равенство с типом; числа — по значению (свод Ф9: `1 = 1.0`), bool ≠ числу."""
    ta, tb = _jt(a), _jt(b)
    if ta in ("integer", "number") and tb in ("integer", "number"):
        return a == b
    if ta != tb:
        return False
    if ta == "array":
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if ta == "object":
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    return a == b


def in_list(x, lits):
    return x is not _ABSENT and any(same(x, y) for y in lits)


def jcs_number(x):
    """Каноническая запись числа (RFC 8785 § 3.2.2.3, ECMAScript Number.toString)."""
    if isinstance(x, int):
        return str(x)
    if math.isnan(x) or math.isinf(x):
        raise ValueError("not finite")
    if x == 0:
        return "0"
    r = repr(x)                                  # кратчайшие цифры, как ECMAScript
    if "e" not in r:
        return r[:-2] if r.endswith(".0") else r
    m, e = r.split("e")
    e = int(e)
    if -7 < e < 21:
        sign, digits = ("-", m[1:]) if m.startswith("-") else ("", m)
        digits = digits.replace(".", "").rstrip("0") or "0"
        n = e + 1
        if n <= 0:
            return sign + "0." + "0" * -n + digits
        if n >= len(digits):
            return sign + digits + "0" * (n - len(digits))
        return sign + digits[:n] + "." + digits[n:]
    m = m.rstrip("0").rstrip(".") if "." in m else m
    return "%se%s%d" % (m, "+" if e > 0 else "-", abs(e))


def text_of(v):
    """text(): каноническая запись значения (доп. (4) В3): bool строчными, число — JCS."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return jcs_number(v)
    return v


def depth(x):
    """Скаляр уровня не добавляет, каждое отображение и список — уровень (свод Ф18)."""
    if isinstance(x, dict):
        return 1 + max([depth(v) for v in x.values()] or [0])
    if isinstance(x, list):
        return 1 + max([depth(v) for v in x] or [0])
    return 0


def unique(s):
    return all(not same(s[i], s[j]) for i in range(len(s)) for j in range(i))


def prefix_free(s):
    """Элемент с `/` в конце не начало никакого другого элемента (свод О13, М10/7 Н1.3)."""
    strs = [x for x in s if isinstance(x, str)]
    for i, a in enumerate(strs):
        if a.endswith("/") and any(j != i and b != a and b.startswith(a) for j, b in enumerate(strs)):
            return False
    return True


def template(t, plain, ints, bare):
    """Шаблон: `{имя}` — из plain, `{имя:int}` — из ints; `{` внутри открытой `{`, `{имя:}` и иное после `:` —
    отказ (свод О14, доп. (1) Р5); лишняя `}` и строка без `{` — допустимы (без bare)."""
    if not isinstance(t, str):
        return False
    if bare and "{" not in t:
        return in_list(t, plain)
    i = 0
    while True:
        a = t.find("{", i)
        if a < 0:
            return True
        b = t.find("}", a)
        if b < 0 or "{" in t[a + 1:b]:
            return False
        name, sep, conv = t[a + 1:b].partition(":")
        if sep and conv != "int":
            return False
        if not in_list(name, ints if sep else plain):
            return False
        i = b + 1


def pointer(path):
    return "".join("/" + str(s).replace("~", "~0").replace("/", "~1") for s in path)


def canonical_paths(paths):
    out = {}
    for p in paths:
        out.setdefault(pointer(p), list(p))
    return [out[k] for k in sorted(out, key=lambda k: k.encode("utf-8"))]


# ---------------------------------------------------------------- загрузчик

class Loader:
    """Loader(form, references, scalars) — пути или байты трёх файлов источника. judge(bytes) → {verdict, class,
    layer, paths, lines, why, rows}; rows — номера строк references.tsv, давших отказ (для покрытия)."""

    def __init__(self, form, references, scalars):
        src = load_source(form, references, scalars)
        self.form, self.rows, self.scalars = src.form, src.rows, src.scalars
        self.classes = self.form.class_positions()

    # ---- форма
    def class_at(self, p):
        for pat, c in self.classes:
            if len(p) >= len(pat) and all(x == "*" or x == y for x, y in zip(pat, p)):
                return c
        return None

    def fail(self, out, p, intrinsic, why, cls=None):
        out.append((cls or self.class_at(p) or intrinsic, list(p), why))

    def default_of(self, n, k):
        n = self.form.deref(n)
        if n.properties and k in n.properties and self.form.has_note(n.properties[k], "default"):
            return self.form.note(n.properties[k], "default")
        return _ABSENT

    def node(self, n, v, p, nm, out):
        f = self.form
        n = f.deref(n)
        if n.variants is not None:
            for vn in n.variants:
                if _is(v, f.types_of(vn)):
                    return self.node(vn, v, p, nm, out)
            return self.fail(out, p, "value", "type: none of the variants")
        if n.types and "any" not in n.types and not _is(v, n.types):
            return self.fail(out, p, "value", "type: expected %s" % "|".join(n.types))
        if n.enum is not None and not in_list(v, n.enum):
            self.fail(out, p, "value", "not in enum")
        if n.not_enum is not None and in_list(v, n.not_enum):
            self.fail(out, p, "value", "forbidden word")
        if n.pattern is not None and isinstance(v, str) and not re.fullmatch(n.pattern, v, re.S):
            self.fail(out, p, "value", "pattern")
        if n.not_pattern is not None and isinstance(v, str) and re.fullmatch(n.not_pattern, v, re.S):
            self.fail(out, p, "value", "forbidden pattern")
        num = isinstance(v, (int, float)) and not isinstance(v, bool)
        if num and n.minimum is not None and v < n.minimum:
            self.fail(out, p, "value", "minimum")
        if num and n.maximum is not None and v > n.maximum:
            self.fail(out, p, "value", "maximum")
        if num and n.exclusive_minimum is not None and v <= n.exclusive_minimum:
            self.fail(out, p, "value", "exclusive_minimum")
        if isinstance(v, dict) and not n.opaque:
            for k in v:
                if n.properties is not None and k in n.properties:
                    self.node(n.properties[k], v[k], p + [k], None, out)
                elif n.names is not None:
                    before = len(out)
                    self.node(n.names[0], k, p + [k], None, out)
                    if len(out) == before:          # имя не по форме — значение не проверяется
                        self.node(n.names[1], v[k], p + [k], k, out)
                elif n.properties is not None:
                    self.fail(out, p + [k], "key", "unknown key")
        if isinstance(v, dict):
            for k in n.required:
                if k not in v:
                    self.fail(out, p + [k], "value", "required")
            # Правила узла, прошедшего форму, — и при отказах ниже него (доп. (3) Р1, свод Ф11).
            for r in n.rules:
                self.rule(n, r, v, p, nm, out)
        if isinstance(v, list):
            if n.min_items is not None and len(v) < n.min_items:
                self.fail(out, p, "value", "min_items")
            if n.items is not None:
                for i, x in enumerate(v):
                    self.node(n.items, x, p + [i], None, out)
            if n.unique_items:
                for i in range(len(v)):
                    if any(same(v[i], v[j]) for j in range(i)):
                        self.fail(out, p + [i], "value", "repeated item")

    def rule(self, n, r, v, p, nm, out):
        w = r.when
        eff = lambda k: v[k] if k in v else self.default_of(n, k)   # noqa: E731 — умолчание из узла ключа (свод Ф23)
        if not all(k in v for k in w.get("present", [])):
            return
        if any(k in v for k in w.get("absent", [])):
            return
        if not all(in_list(eff(k), vals) for k, vals in (w.get("is") or {}).items()):     # null — ложно (Ф12)
            return
        if any(in_list(eff(k), vals) for k, vals in (w.get("is_not") or {}).items()):     # ничего — истинно (Ф12)
            return
        if "name_pattern" in w and not (nm is not None and re.fullmatch(w["name_pattern"], nm, re.S)):
            return
        if "name_not_pattern" in w and not (nm is not None and not re.fullmatch(w["name_not_pattern"], nm, re.S)):
            return
        for k in r.require:
            if k not in v:
                self.fail(out, p + [k], "value", "required by rule", r.xclass)
        for k in r.forbid:
            if k in v:
                self.fail(out, p + [k], "value", "forbidden by rule", r.xclass)
        if r.one_of:
            got = [k for k in r.one_of if k in v]          # «второй» — по списку правила (Ф15)
            if not got:
                self.fail(out, p, "value", "one_of: none", r.xclass)
            elif len(got) > 1:
                self.fail(out, p + [got[1]], "value", "one_of: more than one", r.xclass)
        if r.any_of and not any(k in v for k in r.any_of):
            self.fail(out, p, "value", "any_of: none", r.xclass)
        for k, c in r.check.items():
            if k in v:
                self.node(c, v[k], p + [k], None, out)
        if r.reject:
            self.fail(out, p, "value", "rule: %s" % r.reject, r.xclass)

    # ---- отношения
    def walk(self, doc, segs, env, row=False, cur=None):
        """Путь → (значение, путь, переменные). В терме и наборе связанная переменная подставляется (О2)."""
        def rec(node, i, path, env):
            if i == len(segs):
                yield node, path, env
                return
            s = segs[i]
            kind = s.kind
            if not row and kind == "bind":
                kind = "var"
            if not row and kind == "each_bind":
                kind = "ivar"
            if kind == "key":
                if isinstance(node, dict) and s.val in node:
                    yield from rec(node[s.val], i + 1, path + [s.val], env)
            elif kind == "dyn":
                k = self.term(s.val, doc, env, cur)
                if isinstance(k, str) and isinstance(node, dict) and k in node:
                    yield from rec(node[k], i + 1, path + [k], env)
            elif kind == "var":
                k = env.get(s.val)
                if isinstance(node, dict) and k in node:
                    yield from rec(node[k], i + 1, path + [k], env)
            elif kind == "ivar":
                j = env.get(s.val)
                if isinstance(node, list) and isinstance(j, int) and j < len(node):
                    yield from rec(node[j], i + 1, path + [j], env)
            elif kind == "star":
                if isinstance(node, dict):
                    for k in node:
                        yield from rec(node[k], i + 1, path + [k], env)
            elif kind == "bind":
                if isinstance(node, dict):
                    for k in node:
                        yield from rec(node[k], i + 1, path + [k], dict(env, **{s.val: k}))
            elif kind == "names":
                if isinstance(node, dict):
                    for k in node:
                        yield from rec(k, i + 1, path + [k], env)
            elif kind == "each":
                if isinstance(node, list):
                    for j, x in enumerate(node):
                        yield from rec(x, i + 1, path + [j], env)
            elif kind == "each_bind":
                if isinstance(node, list):
                    for j, x in enumerate(node):
                        yield from rec(x, i + 1, path + [j], dict(env, **{s.val: j}))
        yield from rec(doc, 0, [], env)

    def at(self, doc, segs, env, cur=None):
        """@путь: значение в дереве, иначе default формы; вариант — по значению дерева (свод О3)."""
        for v, _, _ in self.walk(doc, segs, env, cur=cur):
            if v is not None:
                return v
            break
        n, node, has = self.form.root, doc, True
        for s in segs:
            kind = s.kind
            key = None
            if kind == "key":
                key = s.val
            elif kind in ("bind", "var"):
                key = env.get(s.val)
            elif kind == "dyn":
                key = self.term(s.val, doc, env, cur)
            elif kind in ("each_bind", "ivar"):
                key = env.get(s.val)
            nxt = self.form.child(n, s.val if kind == "key" else "*", node, has)
            if nxt is None:
                return _ABSENT
            if has and isinstance(node, dict) and key in node:
                node = node[key]
            elif has and isinstance(node, list) and isinstance(key, int) and key < len(node):
                node = node[key]
            else:
                node, has = None, False
            n = nxt
        return self.form.note(n, "default") if self.form.has_note(n, "default") else _ABSENT

    def term(self, t, doc, env, cur):
        k = t[0]
        if k == "cur":
            return cur
        if k == "var":
            return env.get(t[1], _ABSENT)
        if k == "lit":
            return t[1]
        if k == "split":                                    # вне частей, не строка — нет значения (О15)
            x = self.term(t[1], doc, env, cur)
            if not isinstance(x, str):
                return _ABSENT
            parts = x.split(t[2])
            return parts[t[3]] if t[3] < len(parts) else _ABSENT
        if k == "at":
            return self.at(doc, t[1], env, cur)
        raise ValueError(t)

    def set_(self, s, doc, env, cur):
        out = []
        for a in s[1]:
            if a[0] == "lits":                              # терм без значения выпадает (О12)
                out += [x for x in (self.term(t, doc, env, cur) for t in a[1]) if x is not _ABSENT and x is not None]
            elif a[0] == "keys":
                for node, path, _ in self.walk(doc, a[1], env, cur=cur):
                    fp = form_segs(a[1])
                    if isinstance(node, dict):
                        out += [k for k in node if self.filt(fp, a[2], k, node[k], doc, env, cur)]
                    elif isinstance(node, list):        # у списка — его строки (О8)
                        out += [x for x in node if isinstance(x, str) and self.filt(fp, a[2], x, _ABSENT, doc, env, cur)]
            elif a[0] in ("values", "text"):
                vals = [v for v, _, _ in self.walk(doc, a[1], env, cur=cur)
                        if v is not None and not isinstance(v, (dict, list))]
                out += [text_of(v) for v in vals] if a[0] == "text" else vals
        return out

    def filt(self, fp, fs, nm, e, doc, env, cur):
        for f in fs:
            if f[0] == "has":
                dn = self.form.node_at(fp + ["*", f[1]])          # `has a` — и с default формы (О9, § 6)
                ok = isinstance(e, dict) and (f[1] in e or (dn is not None and self.form.has_note(dn, "default")))
                if not ok:
                    return False
            elif f[0] == "name~":
                if not re.fullmatch(f[1], nm, re.S):
                    return False
            elif f[0] == "name!~":
                if re.fullmatch(f[1], nm, re.S):
                    return False
            elif f[0] == "name!=":
                if eq(nm, self.term(f[1], doc, env, cur)):
                    return False
            else:
                a = _ABSENT
                if isinstance(e, dict) and f[1] in e and e[f[1]] is not None:
                    a = e[f[1]]
                elif isinstance(e, dict):
                    dn = self.form.node_at(fp + ["*", f[1]])
                    if dn is not None and self.form.has_note(dn, "default"):
                        a = self.form.note(dn, "default")
                if f[0] == "attr=" and not eq(a, self.term(f[2], doc, env, cur)):
                    return False
                if f[0] == "attr!=" and eq(a, self.term(f[2], doc, env, cur)):     # без значения — истинно (О9)
                    return False
                if f[0] == "attrin" and not in_list(a, self.set_(f[2], doc, env, cur)):
                    return False
        return True

    def pred(self, p, doc, env, cur):
        k = p[0]
        T = lambda t: self.term(t, doc, env, cur)            # noqa: E731
        if k == "exists":
            return T(p[1]) is not _ABSENT
        if k == "absent":
            return T(p[1]) is _ABSENT
        if k == "empty":
            return not self.set_(p[1], doc, env, cur)
        if k == "unique":
            return unique(self.set_(p[1], doc, env, cur))
        if k == "prefix_free":
            return prefix_free(self.set_(p[1], doc, env, cur))
        if k == "depth":
            return depth(T(p[1])) <= p[2]
        if k == "template":
            return template(T(p[1]), self.set_(p[2], doc, env, cur), self.set_(p[3], doc, env, cur), p[4])
        if k == "=":                                            # нет значения: = ложно, != истинно (О6)
            return eq(T(p[1]), T(p[2]))
        if k == "!=":
            return not eq(T(p[1]), T(p[2]))
        if k == "<=":
            a, b = T(p[1]), T(p[2])
            return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)) and a <= b
        if k == "~":                                            # не строка: ~ ложно, !~ истинно (О7)
            x = T(p[1])
            return isinstance(x, str) and re.fullmatch(p[2], x, re.S) is not None
        if k == "!~":
            x = T(p[1])
            return not (isinstance(x, str) and re.fullmatch(p[2], x, re.S) is not None)
        if k == "in":
            return in_list(T(p[1]), self.set_(p[2], doc, env, cur))
        if k == "not in":
            return not in_list(T(p[1]), self.set_(p[2], doc, env, cur))
        raise ValueError(p)

    def relations(self, doc):
        out = []
        for r in self.rows:
            for cur, path, env in self.walk(doc, r.path, {}, row=True):
                if cur is None:
                    continue
                if r.check[0] in SCALAR_CHECKS and r.check[1] == ("cur",) and isinstance(cur, (dict, list)):
                    continue
                if all(self.pred(c, doc, env, cur) for c in r.conds) and not self.pred(r.check, doc, env, cur):
                    out.append((r.cls, path, "references.tsv:%d" % r.no, r.no))
        return out

    # ---- проход
    def judge(self, data):
        try:
            tree, numbers, empties, lines = textlayer.load_text_map(data)
        except textlayer.TextRefused as exc:
            path = [exc.path] if exc.path is not None else []
            return {"verdict": "refused", "class": "text", "layer": "text:" + exc.rule, "paths": path,
                    "lines": [exc.line] if exc.line else [], "why": [str(exc)], "rows": [], "fired": []}
        return self.judge_tree(tree, [p for p, _ in numbers], empties, lines)

    def judge_tree(self, tree, numbers, empties, lines=None):
        out = []
        for p in numbers:                       # где бы ни остановился обход (свод Ф2); класс — по x-class (Ф1)
            self.fail(out, p, "value", "number out of scalars.tsv limits")
        for p in empties:
            self.fail(out, p, "value", "key without a value")
        self.node(self.form.root, tree, [], None, out)
        for cls in ("name", "key", "value", "reference"):
            hit = [f for f in out if f[0] == cls]
            if hit:
                return self.result(cls, "form", hit, lines, [])
        rel = self.relations(tree)
        if rel:
            cls = "value" if any(f[0] == "value" for f in rel) else "reference"
            return self.result(cls, "relations", [f for f in rel if f[0] == cls], lines, rel)
        return {"verdict": "ok", "class": None, "layer": None, "paths": [], "lines": [], "why": [], "rows": [],
                "fired": []}

    @staticmethod
    def result(cls, layer, hit, lines, rel):
        paths = canonical_paths([f[1] for f in hit])
        nums = set()
        for p in paths:
            for i in range(len(p), 0, -1):          # строка ключа отказа, иначе ближайшего предка в тексте
                if lines and tuple(p[:i]) in lines:
                    nums.add(lines[tuple(p[:i])])
                    break
        return {"verdict": "refused", "class": cls, "layer": layer, "paths": paths, "lines": sorted(nums),
                "why": [f[2] for f in hit][:8], "rows": sorted({f[3] for f in hit if len(f) > 3}),
                "fired": [(f[0], f[3]) for f in rel]}


def eq(a, b):
    return a is not _ABSENT and b is not _ABSENT and same(a, b)


def held_rows(results):
    """Строки references.tsv, которые корпус держит (мерка rows_coverage пилота): без строки меняется вердикт или класс
    хоть одного случая. results — ответы judge с rows и классом отношений."""
    held = set()
    for r in results:
        fired = r.get("fired") or []
        if not fired:
            continue
        base = "value" if any(c == "value" for c, _ in fired) else "reference"
        for no in {n for _, n in fired}:
            rest = [(c, n) for c, n in fired if n != no]
            new = None if not rest else "value" if any(c == "value" for c, _ in rest) else "reference"
            if new != base:
                held.add(no)
    return held
