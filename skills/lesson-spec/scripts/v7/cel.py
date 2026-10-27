"""Строки `references.tsv` (DIALECT § 6) → выражения CEL (ADR-0092 п. 12; слой 7 — три свои функции).

Строка — одно выражение над `doc` (дерево загрузчика): список нарушений `{"p": путь}`, вложенный по числу перебираемых
сегментов пути строки (раннер собирает отображения `p` из вложенных списков; `flatten` в выражении не нужен).
Расширения CEL — стандартные: `strings` (`split`), `two-var-comprehensions` (`transformList`, двуместные `all`/`exists`).
Свои функции (слой 7): `depth(dyn) → int`, `template(dyn, list, list, bool) → bool`, `text(list) → list`.

Термы — пара (есть ли значение, значение): «нет значения» диалекта — ложное первое. `@путь` без значения в дереве (или
со значением `null`) берёт статическое умолчание `default` формы (слой 6: связи — над деревом загрузчика, как у эталона).
Равенство — равенство CEL (числа по значению, bool не число: равенство разнотипных значений CEL).
"""
from form_source.source import ANY, form_segs

from . import regex

ENV = {
    "name": "relations",
    "extensions": [{"name": "strings"}, {"name": "two-var-comprehensions"}],
    "variables": [{"name": "doc", "type_name": "dyn"}],
}
OWN = ("depth", "template", "text")
SCALAR_CHECKS = {"in", "not in", "=", "!=", "<=", "~", "!~", "template"}


class NotTranslated(Exception):
    pass


def cel_str(s):
    out = ['"']
    for c in s:
        if c in '"\\':
            out.append("\\" + c)
        elif c == "\n":
            out.append("\\n")
        elif ord(c) < 0x20 or c == "\x7f":
            out.append("\\x%02x" % ord(c))
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def lit(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        r = repr(v)
        return r if ("." in r or "e" in r) else r + ".0"
    if isinstance(v, str):
        return cel_str(v)
    if isinstance(v, list):
        return "[" + ", ".join(lit(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (cel_str(k), lit(x)) for k, x in v.items()) + "}"
    raise NotTranslated("literal %r" % (v,))


def AND(*xs):
    xs = [x for x in xs if x != "true"]
    if "false" in xs:
        return "false"
    return "(" + " && ".join(xs) + ")" if len(xs) > 1 else (xs[0] if xs else "true")


def OR(*xs):
    xs = [x for x in xs if x != "false"]
    if "true" in xs:
        return "true"
    return "(" + " || ".join(xs) + ")" if len(xs) > 1 else (xs[0] if xs else "false")


def NOT(x):
    return "false" if x == "true" else "true" if x == "false" else "!(%s)" % x


def is_map(x):
    return "type(%s) == map" % x


def is_list(x):
    return "type(%s) == list" % x


def scalar(x):
    return AND("%s != null" % x, "type(%s) != map" % x, "type(%s) != list" % x)


class Row:
    """Перевод одной строки: Row(form, row).expr() → текст CEL; own — свои функции, которые выражение зовёт."""

    def __init__(self, form, row):
        self.f, self.r = form, row
        self.n = 0
        self.own = set()

    def var(self, p):
        self.n += 1
        return "%s%d" % (p, self.n)

    # ---------------------------------------------------------------- термы
    def term(self, t, env, cur):
        k = t[0]
        if k == "cur":
            return "true", cur
        if k == "var":
            if t[1] not in env:
                return "false", "null"
            return "true", env[t[1]]
        if k == "lit":
            return "true", lit(t[1])
        if k == "split":
            p, v = self.term(t[1], env, cur)
            parts = "%s.split(%s)" % (v, cel_str(t[2]))
            return AND(p, "type(%s) == string" % v, "size(%s) > %d" % (parts, t[3])), "%s[%d]" % (parts, t[3])
        if k == "at":
            return self.at(t[1], env, cur)
        raise NotTranslated("term %r" % (t,))

    def single(self, X, s, env, cur):
        """Один шаг пути без перебора: (условия, новое X)."""
        k = s.kind
        if k == "key":
            return [is_map(X), "%s in %s" % (cel_str(s.val), X)], "%s[%s]" % (X, cel_str(s.val))
        if k in ("bind", "var"):
            if s.val not in env:
                return ["false"], X
            return [is_map(X), "%s in %s" % (env[s.val], X)], "%s[%s]" % (X, env[s.val])
        if k in ("each_bind", "ivar"):
            if s.val not in env:
                return ["false"], X
            i = env[s.val]
            return [is_list(X), "%s < size(%s)" % (i, X)], "%s[%s]" % (X, i)
        if k == "dyn":
            p, v = self.term(s.val, env, cur)
            return [p, "type(%s) == string" % v, is_map(X), "%s in %s" % (v, X)], "%s[%s]" % (X, v)
        raise NotTranslated("segment %r is not a single step" % s)

    def at(self, segs, env, cur):
        """@путь: значение в дереве (не null), иначе статическое default формы, иначе нет значения (DIALECT § 6)."""
        X, conds = "doc", []
        for s in segs:
            c, X = self.single(X, s, env, cur)
            conds += c
        present = AND(*conds, "%s != null" % X)
        node = self.place(form_segs(segs))
        if node is not None and self.f.has_note(node, "default"):
            return "true", "(%s ? %s : %s)" % (present, X, lit(self.f.note(node, "default")))
        return present, X

    def place(self, fsegs):
        """Узел формы по пути; путь через `variants` — NotTranslated (умолчание варианта выбирается по дереву)."""
        n = self.f.root
        for s in fsegs:
            if self.f.deref(n).variants:
                raise NotTranslated("@path through variants: %s" % ".".join(fsegs))
            n = self.f.child(n, s)
            if n is None:
                return None
        return n

    # ---------------------------------------------------------------- наборы
    def steps(self, segs):
        """Сегменты пути набора: перебор (`*`, `{}`, `[]`) и одиночные шаги (`$x`, `[$i]`, ключ, `{терм}`)."""
        out = []
        for s in segs:
            k = s.kind
            if k == "bind":
                k = "var"
            elif k == "each_bind":
                k = "ivar"
            out.append((k, s))
        return out

    def ex(self, X, steps, leaf, env, cur):
        """Есть ли элемент набора, для которого leaf(X последнего места) — цепочка exists."""
        if not steps:
            return leaf(X)
        (k, s), rest = steps[0], steps[1:]
        if k == "star":
            K = self.var("k")
            return AND(is_map(X), "dyn(%s).exists(%s, %s)" % (X, K, self.ex("%s[%s]" % (X, K), rest, leaf, env, cur)))
        if k == "names":
            K = self.var("k")
            return AND(is_map(X), "dyn(%s).exists(%s, %s)" % (X, K, self.ex(K, rest, leaf, env, cur)))
        if k == "each":
            E = self.var("e")
            return AND(is_list(X), "dyn(%s).exists(%s, %s)" % (X, E, self.ex(E, rest, leaf, env, cur)))
        conds, Y = self.single(X, _Seg(k, s.val), env, cur)
        return AND(*conds, self.ex(Y, rest, leaf, env, cur))

    def atom_ex(self, a, body, env, cur):
        kind = a[0]
        if kind == "lits":
            out = []
            for t in a[1]:
                p, v = self.term(t, env, cur)
                out.append(AND(p, "%s != null" % v if t[0] != "lit" else "true", body(v)))
            return OR(*out)
        steps = self.steps(a[1])
        if kind == "keys":
            fp = form_segs(a[1])

            def leaf(X):
                K, E = self.var("k"), self.var("e")
                return OR(AND(is_map(X), "dyn(%s).exists(%s, %s)" % (
                              X, K, AND(self.filt(fp, a[2], K, "%s[%s]" % (X, K), env, cur), body(K)))),
                          AND(is_list(X), "dyn(%s).exists(%s, %s)" % (
                              X, E, AND("type(%s) == string" % E, self.filt(fp, a[2], E, None, env, cur), body(E)))))
            return self.ex("doc", steps, leaf, env, cur)
        if kind == "values":
            return self.ex("doc", steps, lambda X: AND(scalar(X), body(X)), env, cur)
        if kind == "text":
            V = self.var("t")
            return "%s.exists(%s, %s)" % (self.atom_list(a, env, cur), V, body(V))
        raise NotTranslated("set atom %r" % (a,))

    def set_ex(self, S, body, env, cur):
        return OR(*[self.atom_ex(a, body, env, cur) for a in S[1]])

    def member(self, S, v, env, cur):
        return self.set_ex(S, lambda x: "%s == %s" % (x, v), env, cur)

    def atom_list(self, a, env, cur):
        """Набор списком CEL: не больше одного перебора, после перебора — только одиночные шаги к скаляру."""
        kind = a[0]
        if kind == "lits":
            parts = []
            for t in a[1]:
                p, v = self.term(t, env, cur)
                parts.append("(%s ? [%s] : [])" % (AND(p, "%s != null" % v if t[0] != "lit" else "true"), v)
                             if p != "true" or t[0] != "lit" else "[%s]" % v)
            return " + ".join(parts)
        steps = self.steps(a[1])
        loops = [i for i, (k, _) in enumerate(steps) if k in ("star", "names", "each")]
        if len(loops) > 1 or (loops and kind == "keys"):
            raise NotTranslated("set %r as a list: more than one level" % (a,))
        if kind == "text":
            self.own.add("text")
            return "text(%s)" % self.atom_list(("values",) + tuple(a[1:]), env, cur)
        X, conds = "doc", []
        head = steps[:loops[0]] if loops else steps
        for k, s in head:
            c, X = self.single(X, _Seg(k, s.val), env, cur)
            conds += c
        if kind == "keys":
            fp = form_segs(a[1])
            K, E = self.var("k"), self.var("e")
            lst = "(%s ? dyn(%s).filter(%s, %s) : (%s ? dyn(%s).filter(%s, %s) : []))" % (
                is_map(X), X, K, self.filt(fp, a[2], K, "%s[%s]" % (X, K), env, cur),
                is_list(X), X, E, AND("type(%s) == string" % E, self.filt(fp, a[2], E, None, env, cur)))
        elif not loops:
            lst = "(%s ? [%s] : [])" % (scalar(X), X)
        else:
            k, s = steps[loops[0]]
            E = self.var("e")
            if k == "each":
                rng, item, L = is_list(X), E, X
            elif k == "star":
                rng, item, L = is_map(X), "%s[%s]" % (X, E), X
            else:
                raise NotTranslated("names in a values set")
            Y, tc = item, []
            for k2, s2 in steps[loops[0] + 1:]:
                c, Y = self.single(Y, _Seg(k2, s2.val), env, cur)
                tc += c
            if k == "star":
                lst = "(%s ? dyn(%s).filter(%s, %s).map(%s, %s) : [])" % (rng, L, E, AND(*tc, scalar(Y)), E, Y)
            else:
                lst = "(%s ? dyn(%s).filter(%s, %s).map(%s, %s) : [])" % (rng, L, E, AND(*tc, scalar(Y)), E, Y)
        c = AND(*conds)
        return lst if c == "true" else "(%s ? %s : [])" % (c, lst)

    def set_list(self, S, env, cur):
        return " + ".join("(%s)" % self.atom_list(a, env, cur) for a in S[1])

    def filt(self, fp, fs, K, E, env, cur):
        """Фильтр keys(… ? …) над ключом K со значением E (None — элемент-строка списка, значения нет)."""
        out = []
        for f in fs:
            kind = f[0]
            if kind == "has":
                dn = self.f.node_at(fp + ["*", f[1]])
                d = dn is not None and self.f.has_note(dn, "default")
                out.append("false" if E is None else
                           is_map(E) if d else AND(is_map(E), "%s in %s" % (cel_str(f[1]), E)))
            elif kind in ("name~", "name!~"):
                m = "%s.matches(%s)" % (K, cel_str(regex.anchored(f[1])))
                out.append(m if kind == "name~" else NOT(m))
            elif kind == "name!=":
                p, v = self.term(f[1], env, cur)
                out.append(NOT(AND(p, "%s == %s" % (K, v))))
            else:
                a = f[1]
                if E is None:
                    pa, va = "false", "null"
                else:
                    have = AND(is_map(E), "%s in %s" % (cel_str(a), E), "%s[%s] != null" % (E, cel_str(a)))
                    dn = self.f.node_at(fp + ["*", a])
                    if dn is not None and self.f.has_note(dn, "default"):
                        pa = is_map(E)
                        va = "(%s ? %s[%s] : %s)" % (have, E, cel_str(a), lit(self.f.note(dn, "default")))
                    else:
                        pa, va = have, "%s[%s]" % (E, cel_str(a))
                if kind == "attr=":
                    p, v = self.term(f[2], env, cur)
                    out.append(AND(pa, p, "%s == %s" % (va, v)))
                elif kind == "attr!=":
                    p, v = self.term(f[2], env, cur)
                    out.append(NOT(AND(pa, p, "%s == %s" % (va, v))))
                elif kind == "attrin":
                    out.append(AND(pa, self.member(f[2], va, env, cur)))
                else:
                    raise NotTranslated("filter %r" % (f,))
        return AND(*out)

    # ---------------------------------------------------------------- предикаты
    def pred(self, p, env, cur, curnode):
        k = p[0]
        if k == "exists":
            return self.term(p[1], env, cur)[0]
        if k == "absent":
            return NOT(self.term(p[1], env, cur)[0])
        if k == "empty":
            return NOT(self.set_ex(p[1], lambda x: "true", env, cur))
        # Порядок перебора отображения в CEL не задан (cel-go — свой при каждом переборе): наборы из keys() сравниваются
        # без номеров — подсчётом и по значению (D18).
        if k == "unique":
            L = self.set_list(p[1], env, cur)
            A, B = self.var("a"), self.var("b")
            return "(%s).all(%s, (%s).filter(%s, %s == %s).size() == 1)" % (L, A, L, B, B, A)
        if k == "prefix_free":
            L = self.set_list(p[1], env, cur)
            A, B = self.var("a"), self.var("b")
            return ("(%s).all(%s, !(type(%s) == string && %s.endsWith(\"/\") && (%s).exists(%s, "
                    "type(%s) == string && %s != %s && %s.startsWith(%s))))"
                    % (L, A, A, A, L, B, B, B, A, B, A))
        if k == "depth":
            if p[1][0] != "cur":
                raise NotTranslated("depth of a term other than '.'")
            self.no_defaults(curnode)
            self.own.add("depth")
            return "depth(%s) <= %d" % (cur, p[2])
        if k == "template":
            pt, vt = self.term(p[1], env, cur)
            self.own.add("template")
            return "template(%s, %s, %s, %s)" % (vt if pt == "true" else "(%s ? %s : null)" % (pt, vt),
                                                 self.set_list(p[2], env, cur), self.set_list(p[3], env, cur),
                                                 "true" if p[4] else "false")
        if k in ("=", "!="):
            pa, va = self.term(p[1], env, cur)
            pb, vb = self.term(p[2], env, cur)
            e = AND(pa, pb, "%s == %s" % (va, vb))
            return e if k == "=" else NOT(e)
        if k == "<=":
            pa, va = self.term(p[1], env, cur)
            pb, vb = self.term(p[2], env, cur)
            num = lambda v: "(type(%s) == int || type(%s) == double)" % (v, v)   # noqa: E731
            return AND(pa, pb, num(va), num(vb), "double(dyn(%s)) <= double(dyn(%s))" % (va, vb))
        if k in ("~", "!~"):
            pa, va = self.term(p[1], env, cur)
            m = AND(pa, "type(%s) == string" % va, "%s.matches(%s)" % (va, cel_str(regex.anchored(p[2]))))
            return m if k == "~" else NOT(m)
        if k in ("in", "not in"):
            pa, va = self.term(p[1], env, cur)
            m = AND(pa, self.member(p[2], va, env, cur))
            return m if k == "in" else NOT(m)
        raise NotTranslated("predicate %r" % (p,))

    def no_defaults(self, fsegs):
        """depth — по значению с умолчаниями формы (Ф18): переводится, только если под местом умолчаний нет."""
        n = self.f.node_at(fsegs)
        seen, stack = set(), [n]
        while stack:
            x = stack.pop()
            if x is None or x is ANY or x.id in seen:
                continue
            seen.add(x.id)
            if "default" in x.notes and x is not n:
                raise NotTranslated("depth over a place with defaults below: %s" % x.where)
            if x.ref is not None:
                stack.append(self.f.defs[x.ref])
            stack += list((x.properties or {}).values()) + list(x.names or []) + ([x.items] if x.items else [])
            stack += list(x.variants or [])

    # ---------------------------------------------------------------- строка
    def expr(self):
        r = self.r
        return self.walk("doc", r.path, 0, [], {}, [])

    def walk(self, X, segs, i, path, env, fsegs):
        if i == len(segs):
            return self.leaf(X, path, env, fsegs)
        s = segs[i]
        k = s.kind
        if k == "key":
            inner = self.walk("%s[%s]" % (X, cel_str(s.val)), segs, i + 1, path + [cel_str(s.val)], env, fsegs + [s.val])
            return "((%s && %s in %s) ? %s : [])" % (is_map(X), cel_str(s.val), X, inner)
        if k in ("star", "bind"):
            K = self.var("k")
            env2 = dict(env, **{s.val: K}) if k == "bind" else env
            inner = self.walk("%s[%s]" % (X, K), segs, i + 1, path + [K], env2, fsegs + ["*"])
            return "(%s ? dyn(%s).map(%s, %s) : [])" % (is_map(X), X, K, inner)
        if k == "names":
            K = self.var("k")
            inner = self.walk(K, segs, i + 1, path + [K], env, fsegs + ["*"])
            return "(%s ? dyn(%s).map(%s, %s) : [])" % (is_map(X), X, K, inner)
        if k in ("each", "each_bind"):
            I, E = self.var("i"), self.var("e")
            env2 = dict(env, **{s.val: I}) if k == "each_bind" else env
            inner = self.walk(E, segs, i + 1, path + [I], env2, fsegs + ["*"])
            return "(%s ? dyn(%s).transformList(%s, %s, %s) : [])" % (is_list(X), X, I, E, inner)
        raise NotTranslated("row path segment %r" % s)

    def leaf(self, cur, path, env, fsegs):
        r = self.r
        conds = ["%s != null" % cur]
        if r.check[0] in SCALAR_CHECKS and r.check[1] == ("cur",):
            conds += ["type(%s) != map" % cur, "type(%s) != list" % cur]
        conds += [self.pred(c, env, cur, fsegs) for c in r.conds]
        conds.append(NOT(self.pred(r.check, env, cur, fsegs)))
        return "(%s ? [{\"p\": [%s]}] : [])" % (AND(*conds), ", ".join(path))


class _Seg:
    def __init__(self, kind, val):
        self.kind, self.val = kind, val


def translate(form, rows):
    """[(row, текст CEL, свои функции)] и [(row, причина)] непереведённых."""
    out, bad = [], []
    for r in rows:
        try:
            t = Row(form, r)
            out.append((r, t.expr(), sorted(t.own)))
        except NotTranslated as exc:
            bad.append((r, str(exc)))
    return out, bad
