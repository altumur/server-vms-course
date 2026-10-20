"""Канонический вид спеки (ADR-0089, доп. (1)–(2); окно главы 2.2): проекция принятой спеки, его построенная форма и
JSON Schema, раздел «Форма канонического вида» норм главы 2.2.

Проекция (P/02.2-01…03) — по порядку:
1. сахар урока 2 (`tables`, `bound_to`, `in`; P/02.2-02) — на дереве загрузчика;
2. умолчания источника — только внутри присутствующего родителя или родителя со своим default (Р10);
3. вычисляемые умолчания урока 2 (П1–П5, P/02.2-03) — на дереве с умолчаниями, до `ordered`;
4. отображение `ordered` — массив `{"name": ключ, …}` в порядке автора (Р14), прочие — по ключам JCS;
5. байты — JCS (ADR-0072), UTF-8, без перевода строки в конце.
Шаги 1 и 3 — закрытый перечень STEPS; шаг действует, если его места есть в форме (у формы без них — не действует:
синтетические формы тестов). Обёртки здесь нет (Р13): `{form, rev, sha256, spec}` — сценарии главы 2.2.

Форма вида строится из той же формы спеки (ADR-0089 п. 3): ключ с умолчанием — обязателен, умолчаний нет; `ordered` —
список объектов с `name` первым ключом и без повторов `name`; сахар приведён — у ключа одна форма; ключ вычисляемого
умолчания обязателен (у `decoded` — при `regex`); правил и отношений формы спеки нет — их проверил установщик;
пометки x-class (класс отказа) не нужны. Отображение без имён автора закрыто, как в форме спеки.
"""
import copy
import json
from types import SimpleNamespace

from .judge import jcs_number
from .section import Section, cell, code
from .source import ANY, Node, Rule, SourceError, _is, all_nodes

FORM = 1                                          # номер формы вида (окно 2.2, В1): ключ …/canonical/1
BEGIN = "<!-- canonical:begin -->"
END = "<!-- canonical:end -->"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
UNIQUE_BY = "x-unique-by"                         # у списка `ordered`: имя ключа без повторов (JSON Schema не говорит)


# ---------------------------------------------------------------- обход дерева

def each(v, path):
    """Значения дерева по пути: '*' — значения отображения или элементы списка; нет места — ничего."""
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


UNIT_FIELDS = ("unit", "fields")
FIELDS = (("unit", "fields", "*"), ("tables", "*", "fields", "*"))     # описатели полей единицы и таблиц


def fields(tree):
    for p in FIELDS:
        for f in each(tree, p):
            if isinstance(f, dict):
                yield f


def secret_items(tree):
    for f in fields(tree):
        for e in f.get("secret_in") or []:
            if isinstance(e, dict):
                yield e


def unit_fields(tree):
    u = tree.get("unit") if isinstance(tree, dict) else None
    fs = u.get("fields") if isinstance(u, dict) else None
    return fs if isinstance(fs, dict) else {}


# ---------------------------------------------------------------- шаги урока 2 (закрытый перечень)

class Step:
    """Шаг проекции урока 2: name — имя в перечне нормы, phase — sugar (до умолчаний) или computed (после), places —
    места формы, без которых шаг не действует; tree(t) — правка дерева; form(f) — что шаг меняет в форме вида."""

    def __init__(self, name, phase, norm, what, result, places, tree, form):
        self.name, self.phase, self.norm, self.what, self.result = name, phase, norm, what, result
        self.places, self.tree, self.form = places, tree, form


def _tables_list(t):
    if isinstance(t, dict) and isinstance(t.get("tables"), list):
        t["tables"] = {x: {} for x in t["tables"]}


def _bound_to(t):
    for f in fields(t):
        if isinstance(f.get("bound_to"), str):
            f["bound_to"] = [f["bound_to"]]


def _secret_in_word(t):
    for e in secret_items(t):
        if isinstance(e.get("in"), str):
            e["in"] = [e["in"]]


def _snapshot(t):
    if "snapshot" not in t:
        t["snapshot"] = [k for k, f in unit_fields(t).items()
                         if not k.endswith("_secret") and k != "server" and not (isinstance(f, dict) and f.get("type") == "blob")]


def _journal(t):
    for k, tbl in (t.get("tables") or {}).items() if isinstance(t.get("tables"), dict) else ():
        if isinstance(tbl, dict):
            j = tbl.setdefault("journal", {})
            j.setdefault("written", k + ".written")
            j.setdefault("deleted", k + ".deleted")


def _display_form(t):
    d = t.get("display")
    if isinstance(d, dict) and "form" not in d:
        d["form"] = [{"fields": list(unit_fields(t))}]


def _field_default(t):
    for f in fields(t):
        f.setdefault("default", None)


def _decoded(t):
    for e in secret_items(t):
        if "regex" in e:
            e.setdefault("decoded", True)


def _narrow(f, path, types):
    """Сахар приведён: у места остаётся одна форма значения — тип из types (вариант или тип узла)."""
    n = f.deref(f.node_at(path))
    if n.variants is not None:
        keep = [v for v in n.variants if set(f.types_of(v)) & set(types)]
        if len(keep) != 1:
            raise SourceError("%s: canonical: sugar needs exactly one variant of %s" % (n.where, types))
        v = f.deref(keep[0])
        notes = dict(n.notes)
        n.__dict__.update(copy.copy(v.__dict__))
        n.notes = dict(v.notes, **notes)
        n.id = Node._n = Node._n + 1
        return
    n.types = [x for x in n.types if x in types]
    if "array" not in n.types:
        n.items = n.min_items = None
        n.unique_items = False
    if "object" not in n.types:
        n.properties = n.names = None


def _require(f, path, key, step):
    n = f.deref(f.node_at(path))
    if key not in n.required:
        n.required.append(key)
    n.properties[key].notes["x-step"] = step


def _form_tables(f):
    _narrow(f, ("tables",), ["object"])
    n = f.deref(f.node_at(("tables",)))
    n.notes.update({"x-step": "tables", "description": "имя → таблица (список имён приведён шагом сахара `tables`)"})


def _form_bound_to(f):
    for p in FIELDS:
        _narrow(f, p + ("bound_to",), ["array"])
        f.node_at(p + ("bound_to",)).notes["x-step"] = "bound_to"
    f.deref(f.node_at(FIELDS[0] + ("bound_to",))).notes["description"] = \
        "список имён полей этой строки, не секретов (одно имя приведено шагом сахара `bound_to`)"


def _form_secret_in(f):
    for p in FIELDS:
        _narrow(f, p + ("secret_in", "*", "in"), ["array"])
        f.node_at(p + ("secret_in", "*", "in")).notes["x-step"] = "in"


def _form_snapshot(f):
    _require(f, (), "snapshot", "П1")


def _form_journal(f):
    _require(f, ("tables", "*"), "journal", "П2")
    for k in ("written", "deleted"):
        _require(f, ("tables", "*", "journal"), k, "П2")


def _form_display(f):
    _require(f, ("display",), "form", "П3")


def _form_default(f):
    for p in FIELDS:
        _require(f, p, "default", "П4")


def _form_decoded(f):
    for p in FIELDS:
        n = f.deref(f.node_at(p + ("secret_in", "*")))
        if not any(r.when == {"present": ["regex"]} and r.require == ["decoded"] for r in n.rules):
            r = Rule(n.where + ".rules[П5]")
            r.when, r.require = {"present": ["regex"]}, ["decoded"]
            n.rules.append(r)
        n.properties["decoded"].notes["x-step"] = "П5"


STEPS = [
    Step("tables", "sugar", "P/02.2-02", "`tables` списком имён", "`{<имя>: {}}` на каждое имя, по порядку списка",
         [("tables",)], _tables_list, _form_tables),
    Step("bound_to", "sugar", "P/02.2-02", "`bound_to` одним именем (поля единицы и таблиц)", "список из одного имени",
         [p + ("bound_to",) for p in FIELDS], _bound_to, _form_bound_to),
    Step("in", "sugar", "P/02.2-02", "`in` элемента `secret_in` одним словом", "список из одного слова",
         [p + ("secret_in", "*", "in") for p in FIELDS], _secret_in_word, _form_secret_in),
    Step("П1", "computed", "P/02.2-03", "нет `snapshot`",
         "имена `unit.fields` в порядке автора без `*_secret`, полей `type: blob` и `server`; явный `[]` остаётся",
         [("snapshot",), UNIT_FIELDS + ("*", "type")], _snapshot, _form_snapshot),
    Step("П2", "computed", "P/02.2-03", "нет `tables.<т>.journal` или одного из его ключей",
         "`written` — `\"<т>.written\"`, `deleted` — `\"<т>.deleted\"`; сказанный ключ остаётся",
         [("tables", "*", "journal", "written"), ("tables", "*", "journal", "deleted")], _journal, _form_journal),
    Step("П3", "computed", "P/02.2-03", "нет `display.form`",
         "`[{\"fields\": [<имена unit.fields в порядке автора>]}]`", [("display", "form"), UNIT_FIELDS],
         _display_form, _form_display),
    Step("П4", "computed", "P/02.2-03", "нет `default` у описателя поля (единицы и таблиц)",
         "`null` (и у `blob`, и при `inherit`)", [p + ("default",) for p in FIELDS], _field_default, _form_default),
    Step("П5", "computed", "P/02.2-03", "нет `decoded` у элемента `secret_in` с `regex`", "`true`",
         [p + ("secret_in", "*", "decoded") for p in FIELDS], _decoded, _form_decoded),
]


def steps_of(form, skip=()):
    """Шаги, чьи места есть в форме, без названных в skip (проба мутаций)."""
    return [s for s in STEPS if s.name not in skip and all(form.node_at(p) not in (None, ANY) for p in s.places)]


# ---------------------------------------------------------------- проекция

def project(form, tree, ordered=True):
    """Умолчания внутри присутствующего (Р10); ordered — отображение `ordered` массивом в порядке автора (Р14)."""
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
            if n.ordered and ordered:
                return [dict({"name": k}, **out[k]) for k in v]
            return out
        if isinstance(v, list) and n.items is not None:
            return [rec(n.items, x) for x in v]
        return v
    return rec(form.root, tree)


def canonical(form, tree, skip=()):
    """Дерево принятой спеки → значение канонического вида (P/02.2-01…03). skip — имена шагов, которые не делать."""
    steps = steps_of(form, skip)
    t = copy.deepcopy(tree)
    for s in steps:
        if s.phase == "sugar":
            s.tree(t)
    t = project(form, t, ordered=False)
    for s in steps:
        if s.phase == "computed":
            s.tree(t)
    return project(form, t)


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


def tree_of(data):
    from .source import textlayer
    return textlayer.load_text(data)[0]


def canonical_bytes(loader, data, skip=()):
    """Байты спеки → байты `spec` канонического вида (чистая проекция, без обёртки, Р13); отказ загрузчика — None."""
    if loader.judge(data)["verdict"] != "ok":
        return None
    return jcs(canonical(loader.form, tree_of(data), skip)).encode("utf-8")


# ---------------------------------------------------------------- форма вида

def view_form(form):
    """Форма канонического вида из формы спеки (ADR-0089 п. 3): новая Form, исходная не меняется."""
    f = copy.deepcopy(form)
    steps = steps_of(f)
    nodes = all_nodes(f)
    for n in nodes:                                   # ключ с умолчанием — обязателен (Р10, P/02.2-05)
        for k, c in (n.properties or {}).items():
            if f.has_note(c, "default") and k not in n.required:
                n.required.append(k)
                c.notes.setdefault("x-default", True)
    for n in nodes:
        for k in ("default", "default_text", "x-class"):
            n.notes.pop(k, None)
        n.rules = []
    for s in steps:
        s.form(f)
    for n in all_nodes(f):                            # ordered — список объектов `{name, …}` без повторов name
        if n.ordered and n.names is not None:
            key, v = n.names[0], f.deref(n.names[1])
            item = Node(n.where + "[]")
            item.types = ["object"]
            item.properties = dict({"name": key}, **(v.properties or {}))
            item.required = ["name"] + [k for k in v.required if k != "name"]
            item.rules = list(v.rules)
            item.notes = {k: x for k, x in v.notes.items() if k in ("description", "owner")}
            key.notes = dict(key.notes, description="ключ автора" + (": " + key.notes["description"]
                                                                    if key.notes.get("description") else ""))
            n.types, n.names, n.items = ["array"], None, item
    reach, stack = set(), [f.root]
    while stack:                                      # определения, до которых дотягивается корень
        n = stack.pop()
        if n.ref is not None and n.ref not in reach:
            reach.add(n.ref)
            stack.append(f.defs[n.ref])
        stack += list((n.properties or {}).values()) + list(n.names or []) + ([n.items] if n.items else [])
        stack += list(n.variants or [])
    f.defs = {k: d for k, d in f.defs.items() if k in reach}
    return f


# ---------------------------------------------------------------- JSON Schema вида (2020-12)

def ecma(p):
    """Выражение диалекта (§ 4, полное совпадение, `.` — любой знак) → ECMA-262 с якорями; `.` — `[\\s\\S]`."""
    out, i, cls = [], 0, False
    while i < len(p):
        c = p[i]
        if c == "\\":
            out.append(p[i:i + 2])
            i += 2
            continue
        if cls:
            if c == "]" and not (out and out[-1] in ("[", "[^")):
                cls = False
            out.append(c)
        elif c == "[":
            cls = True
            if p[i + 1:i + 2] == "^":
                out.append("[^")
                i += 2
                continue
            out.append("[")
        elif c == ".":
            out.append("[\\s\\S]")
        else:
            out.append(c)
        i += 1
    return "^(?:%s)$" % "".join(out)


def node_schema(f, n):
    if n.ref is not None:
        return {"$ref": "#/$defs/" + n.ref}
    if n.variants is not None:
        vs = [node_schema(f, v) for v in n.variants]
        return vs[0] if len(vs) == 1 else {"anyOf": vs}
    s = {}
    if n.types and "any" not in n.types:
        s["type"] = n.types[0] if len(n.types) == 1 else list(n.types)
    if n.enum is not None:
        s["enum"] = list(n.enum)
    nots = []
    if n.not_enum is not None:
        nots.append({"enum": list(n.not_enum)})
    if n.not_pattern is not None:
        nots.append({"type": "string", "pattern": ecma(n.not_pattern)})
    if nots:
        s["not"] = nots[0] if len(nots) == 1 else {"anyOf": nots}
    if n.pattern is not None:
        s["pattern"] = ecma(n.pattern)
    for k, w in (("minimum", "minimum"), ("maximum", "maximum"), ("exclusive_minimum", "exclusiveMinimum")):
        if getattr(n, k) is not None:
            s[w] = getattr(n, k)
    if n.properties is not None:
        s["properties"] = {k: node_schema(f, c) for k, c in n.properties.items()}
    if n.required:
        s["required"] = list(n.required)
    if n.names is not None:
        key = node_schema(f, n.names[0])
        s["propertyNames"] = {"anyOf": [{"enum": list(n.properties)}, key]} if n.properties else key
        s["additionalProperties"] = node_schema(f, n.names[1])
    elif n.properties is not None:
        s["additionalProperties"] = False
    if n.items is not None:
        s["items"] = node_schema(f, n.items)
    if n.min_items is not None:
        s["minItems"] = n.min_items
    if n.unique_items:
        s["uniqueItems"] = True
    if n.ordered:
        s[UNIQUE_BY] = "name"
    conds = []
    for r in n.rules:
        if set(r.when) != {"present"} or not r.require or r.forbid or r.one_of or r.any_of or r.check or r.reject:
            raise SourceError("%s: canonical schema: only `when present → require` rules" % r.where)
        conds.append({"if": {"required": list(r.when["present"])}, "then": {"required": list(r.require)}})
    if conds:
        s["allOf"] = conds
    return s


def view_schema(form):
    """JSON Schema 2020-12 формы вида; UNIQUE_BY — у списка `ordered` (проверка — unique_names)."""
    f = view_form(form)
    s = {"$schema": SCHEMA_DIALECT, "title": "canonical view of a subsystem spec, form %d" % FORM}
    s.update(node_schema(f, f.root))
    if f.defs:
        s["$defs"] = {k: node_schema(f, d) for k, d in f.defs.items()}
    return s


def schema_text(form):
    return json.dumps(view_schema(form), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def unique_names(schema, value):
    """Пути JSON Pointer списков с повтором `name` там, где схема говорит UNIQUE_BY (обход по $ref и properties)."""
    defs, out = schema.get("$defs", {}), []

    def rec(s, v, p):
        while "$ref" in s:
            s = defs[s["$ref"].rsplit("/", 1)[1]]
        if "anyOf" in s:
            for x in s["anyOf"]:
                rec(x, v, p)
            return
        if isinstance(v, list):
            if UNIQUE_BY in s:
                names = [x.get(s[UNIQUE_BY]) for x in v if isinstance(x, dict)]
                if len(names) != len(set(map(json.dumps, names))):
                    out.append(p)
            if "items" in s:
                for i, x in enumerate(v):
                    rec(s["items"], x, "%s/%d" % (p, i))
        elif isinstance(v, dict):
            for k, x in v.items():
                c = (s.get("properties") or {}).get(k)
                if c is None and isinstance(s.get("additionalProperties"), dict):
                    c = s["additionalProperties"]
                if c is not None:
                    rec(c, x, "%s/%s" % (p, k.replace("~", "~0").replace("/", "~1")))
    rec(schema, value, "")
    return out


# ---------------------------------------------------------------- раздел «Форма канонического вида» (глава 2.2)

class ViewSection(Section):
    """Таблица формы вида тем же языком, что раздел «Форма» главы 2.1; без скаляров и отношений."""

    def __init__(self, form):
        super().__init__(SimpleNamespace(form=view_form(form), rows=[], scalars=None))
        self.steps = steps_of(form)
        self.phases = {s.name: s.phase for s in self.steps}

    def need(self, parent, k, n):
        if parent is None:
            return ""
        step = self.f.note(n, "x-step")
        phase = self.phases.get(step)
        if k in self.f.deref(parent).required:
            why = "шаг %s" % step if phase == "computed" else "умолчание формы" if n.notes.get("x-default") else ""
            out = "есть всегда" + (" (%s)" % why if why else "")
        elif phase == "computed":
            out = "есть по правилу отображения (шаг %s)" % step
        else:
            out = "есть, если сказан в спеке"
        if phase == "sugar":
            out += "; сахар приведён (`%s`)" % step
        return out

    def rule_text(self, r):
        return super().rule_text(r).replace(" (путь — недостающий ключ)", "")

    def type_word(self, n, t):
        s = super().type_word(n, t)
        if t == "array" and n.ordered:
            s += "; порядок автора, `name` без повторов (ordered)"
        return s

    def build(self):
        f = self.f
        out = ["### Форма канонического вида (построена из источника)", "",
               "Значение `spec` строки `platform/spec/<sub>/canonical/%d` — JSON (JCS, ADR-0072) этой формы; форма "
               "построена из формы спеки главы 2.1 (ADR-0089 п. 3). Отображение без имён автора закрыто: ключа вне таблицы "
               "нет. «Есть всегда» — ключ с умолчанием формы спеки или шагом проекции; «есть, если сказан в спеке» — "
               "ключ без умолчания, его отсутствие и есть значение. Отображение `ordered` — список объектов "
               "`{name, …}` в порядке автора. Правил и отношений формы спеки здесь нет: принятую спеку проверил "
               "установщик." % FORM, "",
               "#### Шаги урока 2", "",
               "Закрытый перечень: сахар — до умолчаний формы, вычисляемые умолчания — после них, до `ordered`.", "",
               "| Шаг | Норма | Когда | Что в виде |", "|---|---|---|---|"]
        for s in self.steps:
            out.append("| %s | %s | %s | %s |" % ("`%s`" % s.name if s.phase == "sugar" else s.name, s.norm,
                                                 cell(s.what), cell(s.result)))
        rows, rules = [], []
        self.expand("", f.root, rows, rules, (), own=True)
        out += ["", "#### Корень", ""] + self.table(rows) + [""]
        if rules:
            out += ["Правила:", ""] + self.rules_text(rules) + [""]
        if self.own:
            out += ["#### Определения", ""]
            for k in self.own:
                d = f.defs[k]
                out += ["**`%s`**%s" % (k, (" — " + cell(d.notes["description"])) if d.notes.get("description") else ""), ""]
                rows, rules = [("<%s>" % k, self.kind(d), "", d.notes.get("owner") or "", "", "")], []
                if d.rules:
                    rules.append(("<%s>" % k, d))
                for i, v in enumerate(d.variants or []):
                    vt = f.deref(v)
                    if vt.properties or vt.names or vt.items is not None:
                        self.expand("<%s> ⟨вариант %d⟩" % (k, i + 1), v, rows, rules, (k,))
                self.expand("<%s>" % k, d, rows, rules, (k,), own=True)
                out += self.table(rows) + [""]
                if rules:
                    out += ["Правила:", ""] + self.rules_text(rules) + [""]
        return "\n".join(out).rstrip("\n") + "\n"


def build_view_section(form):
    """Текст раздела главы 2.2 между маркерами BEGIN и END (сами маркеры — в нормах); form — Form спеки (2.1)."""
    return ViewSection(form).build()
