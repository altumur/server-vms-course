"""Источник формы спеки (ADR-0087): `*.form.yaml`, `*.references.tsv`, `*.scalars.tsv` → разобранная форма.

Форма читается слоем текста Н1.1 (доп. (4) В1); таблицы — как TSV, не YAML (доп. (6)). Построение отказывает
(SourceError) на слове вне диалекта, на выражении вне подмножества § 4, на пути правила, которого нет в форме
(доп. (1) Р2), на регулярном выражении отношения без кавычек (доп. (4) В2).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spec_schema"))
import textlayer  # noqa: E402

TYPES = {"object", "array", "string", "integer", "number", "boolean", "null", "any"}
NOTE_WORDS = {"description", "owner", "default", "default_text", "x-class"}
NODE_WORDS = {"ref", "type", "enum", "not_enum", "pattern", "not_pattern", "minimum", "maximum", "exclusive_minimum",
              "properties", "names", "opaque", "ordered", "required", "items", "min_items", "unique_items", "variants",
              "rules"} | NOTE_WORDS
RULE_WORDS = {"when", "require", "forbid", "one_of", "any_of", "check", "reject", "x-class", "ref"}
WHEN_WORDS = {"present", "absent", "is", "is_not", "name_pattern", "name_not_pattern"}
CLASSES = {"name", "key", "value", "reference"}
SCALAR_KINDS = {"null", "true", "false", "int", "float", "nonfinite", "string"}
REPEAT_MAX = 1000          # предел повтора RE2 — общее подмножество (доп. (1) Р5)


class SourceError(Exception):
    pass


# ---------------------------------------------------------------- pattern (диалект § 4)

_PUNCT = set("!\"#%&',-./:;<=>@_`~{}[]()*+?|\\^$")


def check_pattern(p, where):
    """§ 4: печатный ASCII; . [] [^] () | * + ? {m} {m,n} (m ≤ n ≤ 1000); \\ только перед пунктуацией; без ^ $ вне
    класса, без \\s \\d \\w \\b, просмотра, флагов и ленивых повторов."""
    if not isinstance(p, str):
        raise SourceError("%s: pattern must be a string" % where)
    i, depth = 0, 0
    while i < len(p):
        c = p[i]
        if ord(c) < 0x20 or ord(c) > 0x7e:
            raise SourceError("%s: pattern %r: non-ASCII or control char" % (where, p))
        if c == "\\":
            if i + 1 >= len(p) or p[i + 1] not in _PUNCT:
                raise SourceError("%s: pattern %r: escape \\%s outside the dialect" % (where, p, p[i + 1:i + 2]))
            i += 2
            continue
        if c in "^$":
            raise SourceError("%s: pattern %r: anchors are implicit (full match)" % (where, p))
        if c == "[":
            j = i + 1
            if j < len(p) and p[j] == "^":
                j += 1
            if j < len(p) and p[j] == "]":
                j += 1
            while j < len(p) and p[j] != "]":
                if p[j] == "\\":
                    if j + 1 >= len(p) or p[j + 1] not in _PUNCT:
                        raise SourceError("%s: pattern %r: escape in class" % (where, p))
                    j += 1
                elif p[j] == "[":
                    raise SourceError("%s: pattern %r: nested [ in class" % (where, p))
                j += 1
            if j >= len(p):
                raise SourceError("%s: pattern %r: unclosed class" % (where, p))
            i = j + 1
            continue
        if c == "(":
            if p[i + 1:i + 2] == "?":
                raise SourceError("%s: pattern %r: (? … ) outside the dialect" % (where, p))
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0:
                raise SourceError("%s: pattern %r: unbalanced )" % (where, p))
        elif c in "*+?":
            if p[i + 1:i + 2] in ("?", "+"):
                raise SourceError("%s: pattern %r: lazy or possessive repeat" % (where, p))
        elif c == "{":
            m = re.match(r"\{([0-9]+)(,([0-9]+))?\}", p[i:])
            if not m:
                raise SourceError("%s: pattern %r: { must be a repeat {m} or {m,n}; literal is \\{" % (where, p))
            lo, hi = int(m.group(1)), int(m.group(3) if m.group(3) is not None else m.group(1))
            if lo > hi or hi > REPEAT_MAX:
                raise SourceError("%s: pattern %r: repeat {%s} outside 0 ≤ m ≤ n ≤ %d" % (where, p, m.group(0)[1:-1],
                                                                                         REPEAT_MAX))
            i += len(m.group(0))
            if p[i:i + 1] in ("?", "+"):
                raise SourceError("%s: pattern %r: lazy repeat" % (where, p))
            continue
        elif c == "}":
            raise SourceError("%s: pattern %r: literal } is \\}" % (where, p))
        i += 1
    if depth:
        raise SourceError("%s: pattern %r: unbalanced (" % (where, p))
    try:
        re.compile(p)
    except re.error as exc:
        raise SourceError("%s: pattern %r: %s" % (where, p, exc))
    return p


# ---------------------------------------------------------------- форма

class Node:
    """Узел формы. ref — имя defs (узел-ссылка), иначе слова узла. notes — пометки позиции."""
    _n = 0

    def __init__(self, where):
        Node._n += 1
        self.id = Node._n
        self.where = where
        self.ref = None
        self.types = None
        self.enum = self.not_enum = None
        self.pattern = self.not_pattern = None
        self.minimum = self.maximum = self.exclusive_minimum = None
        self.properties = None          # {имя: Node}
        self.names = None               # (Node имени, Node значения)
        self.opaque = False
        self.ordered = False
        self.required = []
        self.items = None
        self.min_items = None
        self.unique_items = False
        self.variants = None
        self.rules = []
        self.notes = {}
        self.rules_only = False


ANY = Node("<любое значение>")


class Rule:
    def __init__(self, where):
        self.where = where
        self.ref = None
        self.when = {}
        self.require, self.forbid, self.one_of, self.any_of = [], [], [], []
        self.check = {}
        self.reject = None
        self.xclass = None


class Form:
    def __init__(self, root, defs):
        self.root, self.defs = root, defs

    def deref(self, n):
        seen = set()
        while n.ref is not None:
            if n.ref in seen:
                raise SourceError("ref cycle at %s" % n.ref)
            seen.add(n.ref)
            n = self.defs[n.ref]
        return n

    def note(self, n, k):
        """Пометка позиции: своя, иначе у цели ссылки."""
        while True:
            if k in n.notes:
                return n.notes[k]
            if n.ref is None:
                return None
            n = self.defs[n.ref]

    def has_note(self, n, k):
        while True:
            if k in n.notes:
                return True
            if n.ref is None:
                return False
            n = self.defs[n.ref]

    def types_of(self, n):
        n = self.deref(n)
        if n.variants is not None:
            out = []
            for v in n.variants:
                out += self.types_of(v)
            return out
        return n.types or ["any"]

    def child(self, n, s, value=None, has_value=False):
        """Узел под сегментом s ('*' — имя автора или элемент). При вариантах — вариант по типу значения (О3),
        без значения — первый, где место есть. None — нет такого места."""
        n = self.deref(n)
        if n.variants:
            cands = [self.deref(v) for v in n.variants]
            if has_value:
                cands = [v for v in cands if _is(value, self.types_of(v))]
            for v in cands:
                c = self.child(v, s)
                if c is not None:
                    return c
            return None
        if s == "*":
            if n.names is not None:
                return n.names[1]
            if n.items is not None:
                return n.items
        elif n.properties and s in n.properties:
            return n.properties[s]
        elif n.names is not None:
            return n.names[1]
        # Внутри непроверяемого места (список без items, opaque, any или без type) — любое значение.
        types = n.types or ["any"]
        if "any" in types or n.opaque or (s == "*" and "array" in types and n.items is None):
            return ANY
        return None

    def node_at(self, segs):
        n = self.root
        for s in segs:
            n = self.child(n, s)
            if n is None:
                return None
        return n

    def class_positions(self):
        """[(шаблон пути, класс)] для x-class: '*' — имя автора или элемент; длинные раньше."""
        out = []

        def walk(n, path, stack):
            x = n.notes.get("x-class")
            if x:
                out.append((tuple(path), x))
            if n.ref is not None:
                if n.ref not in stack:
                    walk(self.defs[n.ref], path, stack | {n.ref})
                return
            for k, c in (n.properties or {}).items():
                walk(c, path + [k], stack)
            if n.names is not None:
                walk(n.names[1], path + ["*"], stack)
            if n.items is not None:
                walk(n.items, path + ["*"], stack)
            for v in n.variants or []:
                walk(v, path, stack)

        walk(self.root, [], frozenset())
        out.sort(key=lambda t: -len(t[0]))
        return out


def _jt(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def _is(v, types):
    t = _jt(v)
    return "any" in types or t in types or (t == "integer" and "number" in types)


def _scalar_list(v, where, word):
    if not isinstance(v, list) or not all(x is None or isinstance(x, (str, int, float, bool)) for x in v):
        raise SourceError("%s: %s must be a list of scalars" % (where, word))
    return v


def _keys(v, where, word):
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise SourceError("%s: %s must be a list of key names" % (where, word))
    return v


def parse_node(d, where, defs_names):
    if not isinstance(d, dict):
        raise SourceError("%s: node must be a mapping" % where)
    bad = set(d) - NODE_WORDS
    if bad:
        raise SourceError("%s: words outside the dialect: %s" % (where, sorted(bad)))
    n = Node(where)
    for k in NOTE_WORDS & set(d):
        n.notes[k] = d[k]
    if "x-class" in d and d["x-class"] not in CLASSES:
        raise SourceError("%s: x-class %r" % (where, d["x-class"]))
    if "ref" in d:
        if set(d) - NOTE_WORDS - {"ref"}:
            raise SourceError("%s: ref with facets %s" % (where, sorted(set(d) - NOTE_WORDS - {"ref"})))
        if d["ref"] not in defs_names:
            raise SourceError("%s: unknown ref %r" % (where, d["ref"]))
        n.ref = d["ref"]
        return n
    if "type" in d:
        t = d["type"] if isinstance(d["type"], list) else [d["type"]]
        if not t or not all(isinstance(x, str) for x in t) or set(t) - TYPES:
            raise SourceError("%s: type %r" % (where, d["type"]))
        n.types = t
    for k in ("enum", "not_enum"):
        if k in d:
            setattr(n, k, _scalar_list(d[k], where, k))
    for k in ("pattern", "not_pattern"):
        if k in d:
            setattr(n, k, check_pattern(d[k], "%s.%s" % (where, k)))
    for k in ("minimum", "maximum", "exclusive_minimum"):
        if k in d:
            if isinstance(d[k], bool) or not isinstance(d[k], (int, float)):
                raise SourceError("%s: %s must be a number" % (where, k))
            setattr(n, k, d[k])
    if "properties" in d:
        if not isinstance(d["properties"], dict):
            raise SourceError("%s: properties must be a mapping" % where)
        n.properties = {k: parse_node(v, "%s.%s" % (where, k), defs_names) for k, v in d["properties"].items()}
    if "names" in d:
        nm = d["names"]
        if not isinstance(nm, dict) or set(nm) != {"key", "value"}:
            raise SourceError("%s: names must be {key, value}" % where)
        n.names = (parse_node(nm["key"], where + ".{name}", defs_names),
                   parse_node(nm["value"], where + ".*", defs_names))
    for k in ("opaque", "ordered", "unique_items"):
        if k in d:
            if d[k] is not True:
                raise SourceError("%s: %s: true only" % (where, k))
            setattr(n, k, True)
    if "required" in d:
        n.required = _keys(d["required"], where, "required")
    if "items" in d:
        n.items = parse_node(d["items"], where + "[]", defs_names)
    if "min_items" in d:
        if isinstance(d["min_items"], bool) or not isinstance(d["min_items"], int) or d["min_items"] < 0:
            raise SourceError("%s: min_items must be an integer ≥ 0" % where)
        n.min_items = d["min_items"]
    if "variants" in d:
        if "type" in d or not isinstance(d["variants"], list) or not d["variants"]:
            raise SourceError("%s: variants must be a nonempty list, without type" % where)
        n.variants = [parse_node(v, "%s|%d" % (where, i), defs_names) for i, v in enumerate(d["variants"])]
    if "rules" in d:
        if not isinstance(d["rules"], list):
            raise SourceError("%s: rules must be a list" % where)
        n.rules = [parse_rule(r, "%s.rules[%d]" % (where, i), defs_names) for i, r in enumerate(d["rules"])]
    is_object = bool(n.types and "object" in n.types)
    if is_object and not (n.properties is not None or n.names is not None or n.opaque):
        raise SourceError("%s: object needs properties, names or opaque" % where)
    if n.opaque and (n.properties is not None or n.names is not None):
        raise SourceError("%s: opaque with properties or names" % where)
    if (n.properties is not None or n.names is not None or n.opaque) and not is_object:
        raise SourceError("%s: properties/names/opaque need type object" % where)
    if n.ordered and n.names is None:
        raise SourceError("%s: ordered needs names (ADR-0089: author order of names)" % where)
    if (n.items is not None or n.min_items is not None or n.unique_items) and not (n.types and "array" in n.types):
        raise SourceError("%s: items/min_items/unique_items need type array" % where)
    for k in n.required:
        if n.names is None and k not in (n.properties or {}):
            raise SourceError("%s: required %r is not a property" % (where, k))
    return n


def parse_rule(r, where, defs_names):
    if not isinstance(r, dict) or set(r) - RULE_WORDS:
        raise SourceError("%s: rule words outside the dialect: %s" % (where, sorted(set(r or {}) - RULE_WORDS)))
    x = Rule(where)
    if "ref" in r:
        if set(r) != {"ref"} or r["ref"] not in defs_names:
            raise SourceError("%s: rule ref" % where)
        x.ref = r["ref"]
        return x
    w = r.get("when", {})
    if not isinstance(w, dict) or set(w) - WHEN_WORDS:
        raise SourceError("%s: when words %s" % (where, sorted(set(w) - WHEN_WORDS)))
    for k in ("present", "absent"):
        if k in w:
            _keys(w[k], where, k)
    for k in ("is", "is_not"):
        if k in w and (not isinstance(w[k], dict) or not all(isinstance(v, list) for v in w[k].values())):
            raise SourceError("%s: %s must map keys to lists" % (where, k))
    for k in ("name_pattern", "name_not_pattern"):
        if k in w:
            check_pattern(w[k], "%s.%s" % (where, k))
    x.when = w
    for k in ("require", "forbid", "one_of", "any_of"):
        setattr(x, k, _keys(r.get(k, []), where, k))
    x.check = {k: parse_node(v, "%s.check.%s" % (where, k), defs_names) for k, v in (r.get("check") or {}).items()}
    x.reject = r.get("reject")
    x.xclass = r.get("x-class")
    if x.xclass is not None and x.xclass not in CLASSES:
        raise SourceError("%s: x-class" % where)
    if not (x.require or x.forbid or x.one_of or x.any_of or x.check or x.reject):
        raise SourceError("%s: rule without action" % where)
    return x


def read_text(path_or_bytes):
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    return data


def load_form(src):
    """`*.form.yaml` → Form. Слой текста Н1.1 (доп. (4) В1): то, что он отказывает, — ошибка источника."""
    try:
        d, numbers, empties = textlayer.load_text(read_text(src))
    except textlayer.TextRefused as exc:
        raise SourceError("form: text layer Н1.1: %s" % exc)
    if numbers or empties:
        raise SourceError("form: numbers out of range %s or keys without a value %s" % (numbers, empties))
    if set(d) != {"dialect", "root", "defs"} or d["dialect"] != "m10-form/1":
        raise SourceError("form: top level must be {dialect: m10-form/1, root, defs}")
    if not isinstance(d["defs"], dict):
        raise SourceError("form: defs must be a mapping")
    names = set(d["defs"])
    defs = {}
    for k, v in d["defs"].items():
        if isinstance(v, dict) and "rules" in v and set(v) <= {"rules"} | NOTE_WORDS:   # определение только из правил
            n = Node("defs." + k)
            n.rules = [parse_rule(r, "defs.%s.rules[%d]" % (k, i), names) for i, r in enumerate(v["rules"])]
            n.rules_only = True
            defs[k] = n
        else:
            defs[k] = parse_node(v, "defs." + k, names)
    form = Form(parse_node(d["root"], "root", names), defs)

    def expand(rules, seen=()):
        out = []
        for r in rules:
            if r.ref is not None:
                if r.ref in seen:
                    raise SourceError("rule ref cycle at %s" % r.ref)
                out += expand(defs[r.ref].rules, seen + (r.ref,))
            else:
                out.append(r)
        return out

    nodes = all_nodes(form)
    for n in nodes:
        n.rules = expand(n.rules)
    for n in nodes:
        if n.variants:
            seen = set()
            for v in n.variants:
                t = set(form.types_of(v))
                if "number" in t:
                    t.add("integer")
                if t & seen or "any" in t:
                    raise SourceError("%s: variants overlap by type" % n.where)
                seen |= t
        if n.ordered:
            v = form.deref(n.names[1])
            if not (v.types == ["object"] and v.names is None and "name" not in (v.properties or {})):
                raise SourceError("%s: ordered: the value must be an object of properties without key name "
                                  "(ADR-0089 доп. (1))" % n.where)
        if not n.rules_only:
            for r in n.rules:
                _check_rule_keys(form, n, r)
    return form


def _check_rule_keys(form, n, r):
    """Ключи правила — ключи этого отображения (доп. (1) Р2): иначе правило молча не срабатывало бы."""
    t = form.deref(n)
    keys = list(r.require) + list(r.forbid) + list(r.one_of) + list(r.any_of) + list(r.check)
    keys += list(r.when.get("present", [])) + list(r.when.get("absent", []))
    keys += list((r.when.get("is") or {})) + list((r.when.get("is_not") or {}))
    for k in keys:
        if t.names is None and k not in (t.properties or {}):
            raise SourceError("%s (at %s): rule names key %r that the mapping does not have" % (r.where, n.where, k))


def all_nodes(form):
    out, stack, seen = [], [form.root] + list(form.defs.values()), set()
    while stack:
        n = stack.pop()
        if n.id in seen:
            continue
        seen.add(n.id)
        out.append(n)
        stack += list((n.properties or {}).values())
        if n.names:
            stack += list(n.names)
        if n.items:
            stack.append(n.items)
        stack += n.variants or []
        for r in n.rules:
            if r.ref is None:
                stack += list(r.check.values())
    return sorted(out, key=lambda n: n.id)


# ---------------------------------------------------------------- TSV (доп. (6): UTF-8 без BOM, LF, TAB, «#» — комментарий)

def read_tsv(src, name, width, header):
    data = read_text(src)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SourceError("%s: not UTF-8" % name)
    if text.startswith("﻿") or "\r" in text:
        raise SourceError("%s: BOM or CR" % name)
    rows = []
    for no, line in enumerate(text.split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != width:
            raise SourceError("%s:%d: expected %d columns: %s" % (name, no, width, ", ".join(header)))
        if cols == header:
            continue
        rows.append((no, cols))
    return rows


def load_scalars(src, name="scalars.tsv"):
    rows, limits = [], {}
    for no, (kind, pat, _norm) in read_tsv(src, name, 3, ["kind", "pattern", "norm"]):
        if kind == "limit":
            k, _, v = pat.partition("=")
            try:
                limits[k] = {"int_max": int, "float_max": float}[k](v)
            except (KeyError, ValueError):
                raise SourceError("%s:%d: limit %r" % (name, no, pat))
            continue
        if kind not in SCALAR_KINDS:
            raise SourceError("%s:%d: kind %r" % (name, no, kind))
        rows.append((kind, check_pattern(pat, "%s:%d" % (name, no))))
    if not rows or rows[-1] != ("string", ".*") or set(limits) != {"int_max", "float_max"}:
        raise SourceError("%s: last row must be string .*, limits int_max and float_max" % name)
    return rows, limits


# ---------------------------------------------------------------- references.tsv: пути и выражения (диалект § 6)

class Seg:
    """kind: key(имя) | star | bind(var) | names | each | each_bind(var) | dyn(терм)."""

    def __init__(self, kind, val=None):
        self.kind, self.val = kind, val

    def __repr__(self):
        return "%s:%r" % (self.kind, self.val)


class Parser:
    def __init__(self, s, where):
        self.s, self.i, self.where = s, 0, where

    def err(self, msg):
        raise SourceError("%s: %s at %d in %r" % (self.where, msg, self.i, self.s))

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] == " ":
            self.i += 1

    def at_end(self):
        self.ws()
        return self.i >= len(self.s)

    def peek_word(self):
        self.ws()
        m = re.match(r"[^ (),|&{}]+", self.s[self.i:])
        return m.group(0) if m else ""

    def take(self, lit):
        self.ws()
        if self.s.startswith(lit, self.i):
            self.i += len(lit)
            return True
        return False

    def expect(self, lit):
        if not self.take(lit):
            self.err("expected %r" % lit)

    def word(self):
        w = self.peek_word()
        if not w:
            self.err("expected a word")
        self.i += len(w)
        return w

    def quoted(self):
        self.ws()
        if self.s[self.i:self.i + 1] != '"':
            self.err("expected a quoted string")
        j = self.s.find('"', self.i + 1)
        if j < 0:
            self.err("unclosed quote")
        v = self.s[self.i + 1:j]
        self.i = j + 1
        return v

    def raw_path(self):
        """Путь до пробела, ')', ',', '}' или '?' на верхнем уровне скобок."""
        self.ws()
        depth, j, q = 0, self.i, False
        while j < len(self.s):
            c = self.s[j]
            if q:
                q = c != '"'
            elif c == '"':
                q = True
            elif c in "{[(":
                depth += 1
            elif c in "}])":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and c in " ,?":
                break
            j += 1
        p = self.s[self.i:j]
        self.i = j
        if not p:
            self.err("expected a path")
        return parse_path(p, self.where)

    def term(self):
        """term := '.' | $var | @path | split(term "sep" n) | "str" | WORD."""
        self.ws()
        s = self.s[self.i:]
        if s.startswith('"'):
            return ("lit", self.quoted())
        if s.startswith("split("):
            self.i += 6
            t = self.term()
            sep = self.quoted()
            n = self.word()
            if not n.isdigit():
                self.err("split part number")
            self.expect(")")
            return ("split", t, sep, int(n))
        if s.startswith("@"):
            self.i += 1
            return ("at", self.raw_path())
        if s.startswith("$"):
            return ("var", self.word()[1:])
        w = self.word()
        if w == ".":
            return ("cur",)
        if w in ("true", "false"):
            return ("lit", w == "true")
        return ("lit", w)

    def set_(self):
        atoms = [self.set_atom()]
        while self.take("|"):
            atoms.append(self.set_atom())
        return ("set", atoms)

    def set_atom(self):
        self.ws()
        if self.take("{"):
            terms = [self.term()]
            while self.take(","):
                terms.append(self.term())
            self.expect("}")
            return ("lits", terms)
        for fn in ("keys", "values", "text"):
            if self.s.startswith(fn + "(", self.i):
                self.i += len(fn) + 1
                p = self.raw_path()
                filt = []
                if fn == "keys" and self.take("?"):
                    filt.append(self.filt())
                    while self.take("&"):
                        filt.append(self.filt())
                self.expect(")")
                return (fn, p, filt)
        self.err("expected a set")

    def regex(self):
        """Регулярное выражение — только строка в кавычках (доп. (4) В2); без кавычек — ошибка построения."""
        self.ws()
        if self.s[self.i:self.i + 1] != '"':
            self.err("a regular expression is a quoted string (ADR-0087 доп. (4) В2)")
        return check_pattern(self.quoted(), self.where)

    def filt(self):
        w = self.word()
        if w == "has":
            return ("has", self.word())
        if w == "name":
            if self.take("!~"):
                return ("name!~", self.regex())
            if self.take("~"):
                return ("name~", self.regex())
            if self.take("!="):
                return ("name!=", self.term())
            self.err("name ~|!~|!=")
        if self.take("!="):
            return ("attr!=", w, self.term())
        if self.take("="):
            return ("attr=", w, self.term())
        if self.peek_word() == "in":
            self.word()
            return ("attrin", w, self.set_())
        self.err("filter")

    def pred(self):
        w = self.peek_word()
        if w in ("exists", "absent"):
            self.word()
            return (w, self.term())
        if w in ("empty", "unique", "prefix_free"):
            self.word()
            return (w, self.set_())
        if w == "depth":
            self.word()
            t = self.term()
            self.expect("<=")
            n = self.word()
            if not n.isdigit():
                self.err("depth bound")
            return ("depth", t, int(n))
        if w == "template":
            self.word()
            t = self.term()
            if self.word() != "plain":
                self.err("template … plain")
            plain = self.set_()
            if self.word() != "int":
                self.err("template … int")
            ints = self.set_()
            bare = False
            if self.peek_word() == "bare":
                self.word()
                bare = True
            return ("template", t, plain, ints, bare)
        t = self.term()
        for op in ("!=", "<=", "=", "!~", "~"):
            if self.take(op):
                if op in ("~", "!~"):
                    return (op, t, self.regex())
                return (op, t, self.term())
        if self.peek_word() == "not":
            self.word()
            if self.word() != "in":
                self.err("not in")
            return ("not in", t, self.set_())
        if self.peek_word() == "in":
            self.word()
            return ("in", t, self.set_())
        self.err("expected a predicate")

    def relation(self):
        conds = []
        if self.peek_word() == "when":
            self.word()
            conds.append(self.pred())
            while self.take("&"):
                conds.append(self.pred())
            self.expect(":")
        check = self.pred()
        if not self.at_end():
            self.err("trailing text")
        return conds, check


def parse_path(p, where):
    """Сегменты через '.' на верхнем уровне скобок."""
    parts, depth, cur, q = [], 0, "", False
    for c in p:
        if q:
            q = c != '"'
        elif c == '"':
            q = True
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if c == "." and depth == 0 and not q:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    parts.append(cur)
    segs = []
    for s in parts:
        if s == "*":
            segs.append(Seg("star"))
        elif s == "{}":
            segs.append(Seg("names"))
        elif s.startswith("{") and s.endswith("}"):
            ps = Parser(s[1:-1], where)
            t = ps.term()
            if not ps.at_end():
                ps.err("dynamic segment")
            segs.append(Seg("dyn", t))
        elif re.fullmatch(r"\$[a-z]+", s):
            segs.append(Seg("bind", s[1:]))
        else:
            m = re.fullmatch(r"([a-z_][a-z0-9_]*)(\[\]|\[\$([a-z]+)\])?", s)
            if not m:
                raise SourceError("%s: path segment %r" % (where, s))
            segs.append(Seg("key", m.group(1)))
            if m.group(2) == "[]":
                segs.append(Seg("each"))
            elif m.group(2):
                segs.append(Seg("each_bind", m.group(3)))
    return segs


def form_segs(segs):
    """Сегменты отношения → путь формы ('*' на месте имени автора, элемента, переменной, динамики)."""
    return [s.val if s.kind == "key" else "*" for s in segs]


class Row:
    def __init__(self, no, path_text, path, conds, check, cls, norm, text):
        self.no, self.path_text, self.path = no, path_text, path
        self.conds, self.check, self.cls, self.norm, self.text = conds, check, cls, norm, text


def load_references(src, form, name="references.tsv"):
    rows = []
    for no, (p, rel, cls, norm) in read_tsv(src, name, 4, ["path", "relation", "class", "norm"]):
        where = "%s:%d" % (name, no)
        if cls not in ("reference", "value"):
            raise SourceError("%s: class %r" % (where, cls))
        conds, check = Parser(rel, where).relation()
        r = Row(no, p, parse_path(p, where), conds, check, cls, norm, rel)
        _check_row_paths(form, r, where)
        rows.append(r)
    return rows


def _check_row_paths(form, r, where):
    """Каждый путь строки — место формы (доп. (1) Р2): несуществующий путь — ошибка сборки, а не пустой набор."""
    def need(segs, what):
        if form.node_at(form_segs(segs)) is None:
            raise SourceError("%s: %s %s is not a place of the form" % (where, what, ".".join(form_segs(segs))))

    def term(t):
        if t[0] == "at":
            need(t[1], "@path")
            segs_terms(t[1])
        elif t[0] == "split":
            term(t[1])

    def segs_terms(segs):
        for s in segs:
            if s.kind == "dyn":
                term(s.val)

    def set_(s):
        for a in s[1]:
            if a[0] == "lits":
                for t in a[1]:
                    term(t)
            else:
                need(a[1], a[0] + "()")
                segs_terms(a[1])
                for f in a[2]:
                    if f[0] in ("has", "attr=", "attr!=", "attrin"):
                        need(a[1] + [Seg("star"), Seg("key", f[1])], "filter key")
                    if f[0] in ("attr=", "attr!=", "name!="):
                        term(f[-1])
                    if f[0] == "attrin":
                        set_(f[2])

    def pred(p):
        k = p[0]
        if k in ("exists", "absent", "depth"):
            term(p[1])
        elif k in ("empty", "unique", "prefix_free"):
            set_(p[1])
        elif k == "template":
            term(p[1])
            set_(p[2])
            set_(p[3])
        elif k in ("=", "!=", "<="):
            term(p[1])
            term(p[2])
        elif k in ("~", "!~"):
            term(p[1])
        elif k in ("in", "not in"):
            term(p[1])
            set_(p[2])

    need(r.path, "row path")
    segs_terms(r.path)
    for c in r.conds:
        pred(c)
    pred(r.check)


class Source:
    def __init__(self, form, rows, scalars):
        self.form, self.rows, self.scalars = form, rows, scalars


def load_source(form, references, scalars):
    """Три файла источника (пути или байты) → Source; SourceError — ошибка построения."""
    f = load_form(form)
    rows = load_references(references, f, _name(references, "references.tsv"))
    sc = load_scalars(scalars, _name(scalars, "scalars.tsv"))
    _check_scalars(sc)
    return Source(f, rows, sc)


def _name(src, default):
    return Path(src).name if not isinstance(src, bytes) else default


# Слой текста check_spec распознаёт скаляры своей таблицей; источник — scalars.tsv. Они обязаны совпадать.
_SCALAR_PROBES = ["", "null", "Null", "NULL", "~", "nUll", "true", "True", "TRUE", "tRuE", "false", "FALSE", "0", "-0",
                  "+4", "007", "0x10", "0o7", "1_000", "1.5", ".5", "5.", "1e3", "1E-3", "+1.5e+3", "1.", ".inf", "-.Inf",
                  "+.INF", ".iNf", "inf", ".nan", ".NaN", "-.nan", "NaN", "word", "-", "1e", "e3", "9007199254740991",
                  "9007199254740992"]


def _check_scalars(scalars):
    rows, limits = scalars
    for s in _SCALAR_PROBES:
        kind = next(k for k, p in rows if re.fullmatch(p, s, re.S))
        v = textlayer.resolve_plain(s)
        got = ("null" if v is None else "true" if v is True else "false" if v is False
               else "nonfinite" if isinstance(v, textlayer.NonFinite) else "int" if isinstance(v, int)
               else "float" if isinstance(v, float) else "string")
        if kind == "nonfinite" and got == "int":
            got = kind                       # не бывает: целое длиннее 16 знаков — NonFinite слоя текста
        if got != kind and not (got == "nonfinite" and kind == "int"):
            raise SourceError("scalars.tsv and the text layer disagree on %r: %s vs %s" % (s, kind, got))
    if limits["int_max"] != textlayer.MAX_INT:
        raise SourceError("scalars.tsv int_max %d is not the text layer's %d" % (limits["int_max"], textlayer.MAX_INT))
