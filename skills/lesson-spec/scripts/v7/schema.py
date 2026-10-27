"""Форма диалекта (`m10-form/1`, `data-form/1`) → JSON Schema 2020-12 словами стандарта (ADR-0092 п. 12) и пометки
своих слоёв `x-*` (ADR-0092 «Свой остаток»; доп. (5) ADR-0087 — на расширения `x-*`).

Слова стандарта: `type`, `enum`, `not`, `pattern`, `minimum`, `maximum`, `exclusiveMinimum`, `properties`,
`additionalProperties`, `patternProperties`, `propertyNames`, `required`, `items`, `minItems`, `maxItems`,
`uniqueItems`, `maxProperties`, `allOf`, `anyOf`, `if`/`then`, `$ref`, `$defs`, `default`, `description`.

Перевод слов диалекта (DIALECT § 2–4):
- `variants` — цепочка `allOf: [{if: {type: T_i}, then: V_i}]` и `type` — объединение типов (типы вариантов не
  пересекаются — проверка построителя), отказ «ни один» — `type` на пути значения;
- `names` — `propertyNames` (ключи `properties` — исключением `anyOf: [{enum: [ключи]}, имя]`) и
  `additionalProperties`; правило с `name_pattern` / `name_not_pattern` — на месте `names` родителя:
  `patternProperties` с выражением или его дополнением (MANUAL, regex.py);
- правило — `if` (условие, у объекта) / `then` (действие): `require` — `required`, `forbid` — `properties: {k: false}`,
  `one_of` — `anyOf` из `required` и `properties: {k_j: false}` при одном раньше сказанном, `any_of` — `anyOf`,
  `check` — `properties: {k: узел}`, `reject` — `then: false`; `is`/`is_not` — с умолчанием `default` ключа;
- `opaque` — объект без проверки ключей; `any` и узел без `type` — без `type`;
- `default` — аннотация `default` (статическое умолчание; проекция — слой 6).

Пометки слоёв (их исполняет каждая реализация, таблица — layers.tsv рядом со схемой):
- `x-class` — класс отказа диалекта (только для сверки с эталоном набора А; нормой класс — по слою, п. 6);
- `x-ordered` — проекция канонического вида (слой 6);
- `x-integer-place` — целое место манифеста: приведение `4.0` → `4` (слой 2);
- семьи (слой 3): `x-time` (время Н0, запись писателя или читателя), `x-whole` (целый знак и у читателя), `x-integer`
  (целое по точному десятичному значению записи), `x-max-bytes`, `x-max-names` (имена вне `properties`), `x-encoding`
  (`json`/`jcs`: значение места — разбор текста JSON), `x-codec` (типы поля строки по порядку — кодек `items`);
- `x-complement-of` — дополнение `name_not_pattern`, переведено вручную (п. 12).
Ограничения писателя семей — `$defs.writer` (п. 15): писатель проверяет схему и `$defs.writer`, читатель — схему.
"""
import json
from pathlib import Path

from . import regex

SCHEMA = "https://json-schema.org/draft/2020-12/schema"
INT53 = 2 ** 53 - 1
JSON_TYPES = ("object", "array", "string", "integer", "number", "boolean", "null")


# «Ключа быть не должно»: `{"not": {}}`, а не `false` — у Python `jsonschema` 4.26.0 ошибка схемы `false` под
# `properties` теряет имя ключа в пути (`descend` выходит раньше, чем добавит путь; дефект закреплённой версии, п. 9).
NEVER = {"not": {}}


class SchemaError(Exception):
    pass


def ptr(segs):
    return "".join("/" + str(s).replace("~", "~0").replace("/", "~1") for s in segs)


class Gen:
    """Gen(form, data=False).schema() → JSON Schema; data — схема семьи (`data-form/1`)."""

    def __init__(self, form, data=False):
        self.f, self.data = form, data

    # ---------------------------------------------------------------- типы
    def json_types(self, types):
        out = []
        for t in types:
            if t == "time":
                out += ["number", "string"]          # запись времени — число или строка (слой 3 — грамматика)
            elif t != "any":
                out.append(t)
        return sorted(set(out), key=JSON_TYPES.index)

    def static_types(self, n):
        """Типы JSON значения узла (после `ref` и вариантов); None — любое значение."""
        ts = self.f.types_of(n)
        return None if "any" in ts else self.json_types(ts)

    def default(self, n, k):
        """Умолчание ключа k в properties узла n (DIALECT § 3: и через ref): (есть ли, значение)."""
        t = self.f.deref(n)
        if t.properties and k in t.properties and self.f.has_note(t.properties[k], "default"):
            return True, self.f.note(t.properties[k], "default")
        return False, None

    # ---------------------------------------------------------------- узел
    def notes(self, n, s):
        nt = n.notes
        if "description" in nt:
            s["description"] = nt["description"]
        if "default" in nt:
            s["default"] = nt["default"]
        if "owner" in nt:
            s["x-owner"] = nt["owner"]
        if "default_text" in nt:
            s["x-default-text"] = nt["default_text"]
        if "x-class" in nt:
            s["x-class"] = nt["x-class"]
        if "whole" in nt:
            s["x-whole"] = True
        return s

    def node(self, n):
        f = self.f
        if n.ref is not None:
            return self.notes(n, {"$ref": "#/$defs/" + n.ref})
        s = self.notes(n, {})
        if n.variants is not None:
            types, chain = [], []
            for v in n.variants:
                vt = self.static_types(v)
                types += vt
                chain.append({"if": {"type": vt[0] if len(vt) == 1 else vt}, "then": self.node(v)})
            s["type"] = sorted(set(types), key=JSON_TYPES.index)
            s["allOf"] = chain
            return s
        if n.types:
            jt = self.json_types(n.types)
            if "any" not in n.types:
                s["type"] = jt[0] if len(jt) == 1 else jt
            if "time" in n.types:
                s["x-time"] = True
            if "integer" in n.types and "number" not in n.types:
                if self.data:
                    s["x-integer"] = True
                else:
                    s["x-integer-place"] = True       # п. 8: целое по значению, границы ±(2^53 − 1), приведение
                    lo, hi = n.minimum, n.maximum
                    s["minimum"] = -INT53 if lo is None else max(lo, -INT53)
                    s["maximum"] = INT53 if hi is None else min(hi, INT53)
        self.scalar_words(n, s)
        if n.opaque:
            s["x-opaque"] = True
        if n.properties is not None:
            s["properties"] = {k: self.node(c) for k, c in n.properties.items()}
        if n.names is not None:
            key = self.node(n.names[0])
            s["propertyNames"] = {"anyOf": [{"enum": list(n.properties)}, key]} if n.properties else key
            s["additionalProperties"] = self.node(n.names[1])
            pp = self.name_rules(n.names[1])
            if pp:
                if n.properties:
                    raise SchemaError("%s: name rules with properties next to names" % n.where)
                s["patternProperties"] = pp
        elif n.properties is not None:
            s["additionalProperties"] = False
        if n.required:
            s["required"] = list(n.required)
        if n.items is not None:
            s["items"] = self.node(n.items)
        if n.min_items is not None:
            s["minItems"] = n.min_items
        if n.unique_items:
            s["uniqueItems"] = True
        if n.max_items is not None:
            if "array" in (n.types or []):
                s["maxItems"] = n.max_items
            if "object" in (n.types or []):
                if n.properties is None:
                    s["maxProperties"] = n.max_items
                else:
                    s["x-max-names"] = n.max_items
        if n.max_bytes is not None:
            s["x-max-bytes"] = n.max_bytes
        if n.encoding is not None:
            s["x-encoding"] = n.encoding
        if n.ordered:
            s["x-ordered"] = True
        rules = [self.rule(n, r) for r in n.rules if not self.named(r)]
        if rules:
            s.setdefault("allOf", []).extend(rules)
        return s

    def scalar_words(self, n, s):
        if n.enum is not None:
            s["enum"] = list(n.enum)
        nots = []
        if n.not_enum is not None:
            nots.append({"enum": list(n.not_enum)})
        if n.not_pattern is not None:
            nots.append({"type": "string", "pattern": regex.anchored(n.not_pattern)})
        if nots:
            s["not"] = nots[0] if len(nots) == 1 else {"anyOf": nots}
        if n.pattern is not None:
            s["pattern"] = regex.anchored(n.pattern)
        for k, w in (("minimum", "minimum"), ("maximum", "maximum"), ("exclusive_minimum", "exclusiveMinimum")):
            if getattr(n, k) is not None and w not in s:
                s[w] = getattr(n, k)
        return s

    # ---------------------------------------------------------------- правила
    @staticmethod
    def named(r):
        return "name_pattern" in r.when or "name_not_pattern" in r.when

    def name_rules(self, value):
        """Правила с условием на имя у значения имён автора → patternProperties места `names` (DIALECT § 3)."""
        t = self.f.deref(value)
        out = {}
        for r in t.rules:
            if not self.named(r):
                continue
            if "name_pattern" in r.when and "name_not_pattern" in r.when:
                raise SchemaError("%s: name_pattern with name_not_pattern" % r.where)
            if "name_pattern" in r.when:
                key = regex.anchored(r.when["name_pattern"])
            else:
                key = "^(?:%s)$" % regex.complement(r.when["name_not_pattern"])
            ent = out.setdefault(key, {"allOf": [self.node(value)]})
            if "name_not_pattern" in r.when:
                ent["x-complement-of"] = regex.anchored(r.when["name_not_pattern"])
            ent["allOf"].append(self.rule(t, r))
        return out

    def cond(self, n, w):
        parts = [{"type": "object"}]
        if w.get("present"):
            parts.append({"required": list(w["present"])})
        for k in w.get("absent", []):
            parts.append({"not": {"required": [k]}})
        for k, vals in (w.get("is") or {}).items():
            parts.append(self.is_cond(n, k, vals))
        for k, vals in (w.get("is_not") or {}).items():
            parts.append({"not": self.is_cond(n, k, vals)})
        return parts[0] if len(parts) == 1 else {"allOf": parts}

    def is_cond(self, n, k, vals):
        """Значение ключа k (или его default, если ключа нет) из vals (DIALECT § 3; null — значение)."""
        here = {"required": [k], "properties": {k: {"enum": list(vals)}}}
        has, d = self.default(n, k)
        if has and _in(d, vals):
            return {"anyOf": [here, {"not": {"required": [k]}}]}
        return here

    def rule(self, n, r):
        then = []
        if r.require:
            then.append({"required": list(r.require)})
        if r.forbid:
            then.append({"properties": {k: NEVER for k in r.forbid}})
        if r.one_of:
            ks = r.one_of
            then.append({"anyOf": [{"required": [k]} for k in ks]})
            for j in range(1, len(ks)):          # второй сказанный по списку правила — путь (DIALECT § 3, Ф15)
                then.append({"if": exactly_one(ks[:j]), "then": {"properties": {ks[j]: NEVER}}})
        if r.any_of:
            then.append({"anyOf": [{"required": [k]} for k in r.any_of]})
        if r.check:
            then.append({"properties": {k: self.node(c) for k, c in r.check.items()}})
        if r.reject:
            then.append(False)
        act = then[0] if len(then) == 1 else {"allOf": then}
        out = {"if": self.cond(n, r.when), "then": act}
        if r.xclass:
            out["x-class"] = r.xclass
        if r.reject:
            out["description"] = r.reject
        return out

    # ---------------------------------------------------------------- писатель (п. 15)
    def writer(self, n, memo, stack=()):
        """Схема ограничений писателя для места n (зеркало обхода); None — ниже n их нет."""
        f = self.f
        if n.ref is not None:
            if n.ref in stack:
                return None
            if n.ref not in memo:
                memo[n.ref] = None
                memo[n.ref] = self.writer(f.defs[n.ref], memo, stack + (n.ref,))
            return {"$ref": "#/$defs/writer/$defs/" + n.ref} if memo[n.ref] is not None else None
        s = {}
        if n.writer is not None:
            w = n.writer
            self.scalar_words(w, s)
            if w.min_items is not None:
                s["minItems"] = w.min_items
            if w.unique_items:
                s["uniqueItems"] = True
            if w.max_items is not None:
                if "array" in (n.types or []):
                    s["maxItems"] = w.max_items
                if "object" in (n.types or []):
                    if n.properties is None:
                        s["maxProperties"] = w.max_items
                    else:
                        s["x-max-names"] = w.max_items
            if w.max_bytes is not None:
                s["x-max-bytes"] = w.max_bytes
        if n.variants is not None:
            chain = []
            for v in n.variants:
                x = self.writer(v, memo, stack)
                if x is not None:
                    vt = self.static_types(v)
                    chain.append({"if": {"type": vt[0] if len(vt) == 1 else vt}, "then": x})
            if chain:
                s["allOf"] = chain
        props = {}
        for k, c in (n.properties or {}).items():
            x = self.writer(c, memo, stack)
            if x is not None:
                props[k] = x
        if n.names is not None:
            x = self.writer(n.names[1], memo, stack)
            if x is not None:
                s["additionalProperties"] = x
                for k in n.properties or {}:     # ключи properties — не имена автора: значение имени их не судит
                    props.setdefault(k, True)
            kx = self.writer(n.names[0], memo, stack)
            if kx is not None:
                s["propertyNames"] = {"anyOf": [{"enum": list(n.properties)}, kx]} if n.properties else kx
        if props:
            s["properties"] = props
        if n.items is not None:
            x = self.writer(n.items, memo, stack)
            if x is not None:
                s["items"] = x
        return s or None

    # ---------------------------------------------------------------- схема
    def schema(self, title=None):
        f = self.f
        s = {"$schema": SCHEMA}
        if title:
            s["title"] = title
        s.update(self.node(f.root))
        defs = {}
        for k, d in sorted(f.defs.items()):
            if d.rules_only:
                continue                         # определение только из правил вставлено в узлы (load_form)
            defs[k] = self.node(d)
        if self.data:
            memo = {}
            w = self.writer(f.root, memo)
            wd = {k: v for k, v in sorted(memo.items()) if v is not None}
            if w is not None or wd:
                w = dict(w or {})
                if wd:
                    w["$defs"] = wd
                defs["writer"] = w
        if defs:
            s["$defs"] = defs
        return s


def exactly_one(ks):
    """Ровно один ключ из ks сказан."""
    if len(ks) == 1:
        return {"required": [ks[0]]}
    return {"anyOf": [{"required": [k], "not": {"anyOf": [{"required": [x]} for x in ks if x != k]}} for k in ks]}


def _in(x, vals):
    """Равенство диалекта (числа по значению, bool не число) — то же, что `enum` JSON Schema."""
    def same(a, b):
        if isinstance(a, bool) or isinstance(b, bool):
            return type(a) is type(b) and a == b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a == b
        if type(a) is not type(b):
            return False
        if isinstance(a, list):
            return len(a) == len(b) and all(same(p, q) for p, q in zip(a, b))
        if isinstance(a, dict):
            return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
        return a == b
    return any(same(x, v) for v in vals)


def dumps(schema):
    """Детерминированный текст: ключи по порядку, отступ 1, UTF-8 без экранирования, перевод строки в конце."""
    return json.dumps(schema, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- таблица слоёв

LAYER_WORDS = {
    "x-integer-place": "2", "x-time": "3", "x-whole": "3", "x-integer": "3", "x-max-bytes": "3", "x-max-names": "3",
    "x-encoding": "3", "x-codec": "3", "x-ordered": "6", "x-complement-of": "п. 12", "x-class": "А",
}


def layer_table(schema):
    """Строки `place<TAB>layer<TAB>word<TAB>value`: каждая пометка `x-*` схемы по месту в схеме (JSON Pointer)."""
    rows = []

    def rec(s, p):
        if isinstance(s, dict):
            for k in sorted(s):
                if k in LAYER_WORDS:
                    rows.append((ptr(p) or "#", LAYER_WORDS[k], k, json.dumps(s[k], ensure_ascii=False)))
                rec(s[k], p + [k])
        elif isinstance(s, list):
            for i, x in enumerate(s):
                rec(x, p + [i])
    rec(schema, [])
    return "".join("%s\t%s\t%s\t%s\n" % r for r in [("place", "layer", "word", "value")] + rows)
