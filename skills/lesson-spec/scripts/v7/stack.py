"""Стандартный стек В7 на Python (ADR-0092): JSON Schema 2020-12 (`jsonschema`), CEL (`cel-expr-python`) и свои слои.

Слои (ADR-0092 «Свой остаток»):
1. текст — `textv7.py` (Python: ruamel.yaml 0.19.1) и `go/text.go` (Go: go.yaml.in/yaml/v3 v3.0.5): готовый парсер
   и тонкая проверка (п. 2–4); числа вне `scalars.tsv` и пустые значения — отказ формы, как у эталона (открытый вопрос);
2. целые манифеста: границы — в схеме (`minimum`/`maximum`), приведение `4.0` → `4` на месте `x-integer-place`;
3. кодек строк семей (`x-codec`, `x-encoding`, `x-time`, `x-integer`, `x-whole`, `x-max-bytes`, `x-max-names`);
4. место отказа (`norm_errors`): `required` — путь недостающего ключа, `additionalProperties: false` — путь лишнего,
   `propertyNames` — путь имени, `uniqueItems` — путь каждого повтора; ниже имени не по форме — отказов нет (DIALECT § 2:
   «имя не по форме — значение не проверяется»);
5. полное совпадение `pattern` у Python `jsonschema` (`regex.python_full`: `$` → `\\Z`);
6. проекция — `project.py`; связи — над деревом загрузчика со статическими умолчаниями (в выражениях CEL);
7. три свои функции CEL — `OWN` ниже.
"""
import copy
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import jsonschema
from jsonschema import ValidationError, validators
from jsonschema._utils import equal

from . import regex


# ---------------------------------------------------------------- JSON Schema + слой 5

def _pattern(validator, patrn, instance, schema):
    if validator.is_type(instance, "string") and not re.search(regex.python_full(patrn), instance):
        yield ValidationError("%r does not match %r" % (instance, patrn))


def _pattern_properties(validator, pp, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    for p, sub in pp.items():
        for k, v in instance.items():
            if re.search(regex.python_full(p), k):
                yield from validator.descend(v, sub, path=k, schema_path=p)


def _additional_properties(validator, ap, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    extras = [k for k in instance if k not in schema.get("properties", {})
              and not any(re.search(regex.python_full(p), k) for p in schema.get("patternProperties", {}))]
    if ap is False:
        if extras:
            yield ValidationError("additional properties %r" % extras, validator_value=ap)
    elif isinstance(ap, dict):
        for k in extras:
            yield from validator.descend(instance[k], ap, path=k)


V7Validator = validators.extend(jsonschema.Draft202012Validator, {
    "pattern": _pattern, "patternProperties": _pattern_properties, "additionalProperties": _additional_properties})


def validator_for(schema):
    return V7Validator(schema)


# ---------------------------------------------------------------- слой 4: место отказа

def norm(records, instance):
    """records — [(путь, слово, данные)] библиотеки (Python или Go) → пути отказа диалекта (DIALECT § 3, § 5)."""
    out, bad_names = [], []
    for path, kw, extra in records:
        path = list(path)
        if kw == "required":
            out += [path + [k] for k in extra]
        elif kw == "additionalProperties":
            out += [path + [k] for k in extra]
        elif kw == "propertyNames":
            out.append(path + [extra])
            bad_names.append(path + [extra])
        elif kw == "uniqueItems":
            out += [path + [i] for i in extra]
        else:
            out.append(path)
    return [p for p in out if not any(len(p) > len(b) and p[:len(b)] == b for b in bad_names)]


def at(value, path):
    for s in path:
        value = value[s]
    return value


def repeats(lst):
    return [i for i in range(len(lst)) if any(equal(lst[i], lst[j]) for j in range(i))]


def py_records(validator, instance, schema=None):
    """Ошибки Python `jsonschema` → записи (путь, слово, данные) для norm."""
    recs = []
    errs = validator.iter_errors(instance) if schema is None else validator.evolve(schema=schema).iter_errors(instance)
    for e in errs:
        path = list(e.absolute_path)
        if "propertyNames" in e.absolute_schema_path:
            recs.append((path, "propertyNames", e.instance))
        elif e.validator == "required":
            obj = at(instance, path)
            recs.append((path, "required", [k for k in e.validator_value if k not in obj]))
        elif e.validator == "additionalProperties" and e.validator_value is False:
            obj, s = at(instance, path), e.schema
            recs.append((path, "additionalProperties",
                         [k for k in obj if k not in s.get("properties", {}) and not any(
                             re.search(regex.python_full(p), k) for p in s.get("patternProperties", {}))]))
        elif e.validator == "uniqueItems":
            recs.append((path, "uniqueItems", repeats(at(instance, path))))
        else:
            recs.append((path, e.validator, None))
    return recs


def pointer(path):
    return "".join("/" + str(s).replace("~", "~0").replace("/", "~1") for s in path)


def canonical(paths):
    seen = {}
    for p in paths:
        seen.setdefault(pointer(p), list(p))
    return [seen[k] for k in sorted(seen, key=lambda k: k.encode("utf-8"))]


# ---------------------------------------------------------------- обход схемы и значения (слои 2, 3, 6)

class Schema:
    """Схема с разрешением `$ref` по `#/$defs/…` и выбором места для значения."""

    def __init__(self, doc):
        self.doc = doc
        self.v = validator_for(doc)

    def resolve(self, s):
        """[узлы] по цепочке `$ref` (первый — место ссылки: его пометки важнее)."""
        out = []
        while isinstance(s, dict):
            out.append(s)
            for x in s.get("allOf", []):         # место имён с правилами по имени: allOf [значение, правила…]
                if isinstance(x, dict) and "$ref" in x and "if" not in x:
                    out += self.resolve(x)
            r = s.get("$ref")
            if r is None:
                break
            s = self.sub(r)
        return out

    def sub(self, ref):
        s = self.doc
        for seg in ref[2:].split("/"):
            s = s[seg.replace("~1", "/").replace("~0", "~")]
        return s

    def word(self, chain, k, default=None):
        for s in chain:
            if k in s:
                return s[k]
        return default

    def valid(self, sub, value):
        return self.v.evolve(schema=sub).is_valid(value)

    def variant(self, chain, value):
        """Цепочка вариантов (`allOf` из `if: {type}` / `then`): узел выбранного варианта или None."""
        for s in chain:
            for x in s.get("allOf", []):
                if isinstance(x, dict) and set(x.get("if", {})) == {"type"} and "then" in x:
                    if self.valid(x["if"], value):
                        return x["then"]
        return None

    def child(self, chain, value, k):
        """Узел места ключа k (отображение) или индекса k (список); None — места нет или имя не по форме."""
        for s in chain:
            if isinstance(value, dict):
                props = s.get("properties", {})
                if k in props:
                    return props[k]
                for p, sub in s.get("patternProperties", {}).items():
                    if re.search(regex.python_full(p), k):
                        return sub
                if isinstance(s.get("additionalProperties"), dict):
                    pn = s.get("propertyNames")
                    if pn is not None and not self.valid(pn, k):
                        return None
                    return s["additionalProperties"]
            elif isinstance(value, list) and isinstance(s.get("items"), dict):
                return s["items"]
        return None


def walk(sch, s, value, path, visit):
    """visit(chain, value, path) → новое значение места (или то же); затем — дети нового значения."""
    chain = sch.resolve(s)
    v = sch.variant(chain, value)
    if v is not None:
        chain = chain + sch.resolve(v)
    value = visit(chain, value, path)
    if isinstance(value, dict) and not sch.word(chain, "x-opaque"):
        for k in list(value):
            c = sch.child(chain, value, k)
            if c is not None:
                value[k] = walk(sch, c, value[k], path + [k], visit)
    elif isinstance(value, list):
        for i in range(len(value)):
            c = sch.child(chain, value, i)
            if c is not None:
                value[i] = walk(sch, c, value[i], path + [i], visit)
    return value


# ---------------------------------------------------------------- манифест (P/02.1)

class Manifest:
    """Загрузчик манифеста В7: текст → форма (JSON Schema) → целые (слой 2) → связи (CEL)."""

    def __init__(self, schema_doc, relations_doc, cel_runner=None, text=None):
        if text is None:
            from v7 import textv7 as text
        self.text = text                     # слой 1: v7.textv7 (свой) или textlayer эталона (для сравнения)
        self.sch = Schema(schema_doc)
        self.rel = relations_doc
        self.cel = cel_runner or PyCel(relations_doc)

    def judge(self, data):
        try:
            tree, numbers, empties, lines = self.text.load_text_map(data)
        except self.text.TextRefused as exc:
            return {"verdict": "refused", "layer": "text", "paths": [list(exc.path)] if exc.path is not None else [],
                    "rows": []}
        if numbers or empties:                   # отказ формы на своём пути; прочие отказы формы — тоже (DIALECT § 5)
            clean = self.nonfinite(tree)
            paths = [p for p, _ in numbers] + list(empties) + norm(py_records(self.sch.v, clean), clean)
            return {"verdict": "refused", "layer": "form", "paths": canonical(paths), "rows": []}
        return self.judge_tree(tree)

    @staticmethod
    def nonfinite(x):
        """Число вне JSON (слой текста: NonFinite) → null: его место уже отказано."""
        if isinstance(x, dict):
            return {k: Manifest.nonfinite(v) for k, v in x.items()}
        if isinstance(x, list):
            return [Manifest.nonfinite(v) for v in x]
        return x if isinstance(x, (str, int, float, bool, type(None))) else None

    def judge_tree(self, tree, records=None):
        recs = py_records(self.sch.v, tree) if records is None else records
        if recs:
            return {"verdict": "refused", "layer": "form", "paths": canonical(norm(recs, tree)), "rows": []}
        tree = self.integers(tree)
        fired = self.cel.run(tree)
        if fired:
            cls = "value" if any(self.cls[no] == "value" for no, _ in fired) else "reference"
            return {"verdict": "refused", "layer": "relations", "paths": canonical(p for _, p in fired),
                    "rows": sorted({no for no, _ in fired}), "fired": fired, "relations_class": cls}
        return {"verdict": "ok", "layer": None, "paths": [], "rows": [], "tree": tree}

    @property
    def cls(self):
        return {r["no"]: r["class"] for r in self.rel["rows"]}

    def integers(self, tree):
        """Слой 2 (п. 8): на целом месте значение с целым значением — целое (`4.0` → `4`)."""
        def visit(chain, v, path):
            if (self.sch.word(chain, "x-integer-place") and isinstance(v, float) and not isinstance(v, bool)
                    and v.is_integer()):
                return int(v)
            return v
        return walk(self.sch, self.sch.doc, copy.deepcopy(tree), [], visit)


# ---------------------------------------------------------------- связи: CEL (Python) и свои функции (слой 7)

def depth(x):
    if isinstance(x, dict):
        return 1 + max([depth(v) for v in x.values()] or [0])
    if isinstance(x, list):
        return 1 + max([depth(v) for v in x] or [0])
    return 0


def jcs_number(x):
    """RFC 8785 § 3.2.2.3 (ECMAScript Number.toString)."""
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        raise ValueError("not finite")
    if x == 0:
        return "0"
    r = repr(x)
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


def text(lst):
    out = []
    for v in lst:
        if isinstance(v, bool):
            out.append("true" if v else "false")
        elif isinstance(v, (int, float)):
            out.append(jcs_number(v))
        else:
            out.append(v)
    return out


def _same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b and type(a) is type(b) or (isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b)


def template(t, plain, ints, bare):
    if not isinstance(t, str):
        return False
    inl = lambda x, s: any(_same(x, y) for y in s)   # noqa: E731
    if bare and "{" not in t:
        return inl(t, plain)
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
        if not inl(name, ints if sep else plain):
            return False
        i = b + 1


def collect(v, out):
    """Пути нарушений из вложенного списка `{"p": путь}`."""
    if isinstance(v, dict):
        out.append(list(v["p"]))
    elif isinstance(v, list):
        for x in v:
            collect(x, out)
    return out


class PyCel:
    """Строки связей на cel-expr-python: run(tree) → [(номер строки, путь)]."""

    def __init__(self, rel):
        from cel_expr_python import cel
        self.celmod = cel
        ext = rel["env"]["extensions"]
        yaml = "name: relations\n" + ("extensions:\n" + "".join("  - name: %s\n" % e["name"] for e in ext) if ext else "")
        cfg = cel.NewEnvConfigFromYaml(yaml)
        T = cel.Type
        # У cel-expr-python 0.1.3 перегрузка с параметром dyn не совпадает при исполнении ни с одним значением
        # («No matching overloads found : depth(map)»): параметр dyn — перегрузкой на каждый конкретный тип.
        kinds = {"map": T.Map(T.DYN, T.DYN), "list": T.List(T.DYN), "string": T.STRING, "int": T.INT,
                 "double": T.DOUBLE, "bool": T.BOOL, "null": T.NULL}
        fns = [cel.FunctionDecl("depth", [cel.Overload("depth_" + k, T.INT, [t], impl=depth)
                                          for k, t in kinds.items()]),
               cel.FunctionDecl("template", [cel.Overload("template_%s_list_list_bool" % k, T.BOOL,
                                                          [t, T.List(T.DYN), T.List(T.DYN), T.BOOL], impl=template)
                                             for k, t in kinds.items()]),
               cel.FunctionDecl("text", [cel.Overload("text_list", T.List(T.DYN), [T.List(T.DYN)], impl=text)])]
        self.env = cel.NewEnv(config=cfg, variables={"doc": T.DYN}, functions=fns)
        self.rows = [(r["no"], self.env.compile(r["cel"])) for r in rel["rows"]]

    def run(self, tree):
        out = []
        for no, e in self.rows:
            v = e.eval(data={"doc": tree})
            if v.type() == self.celmod.Type.ERROR:
                raise RuntimeError("references.tsv:%d: CEL error: %s" % (no, v.value()))
            for p in collect(v.plain_value(), []):
                out.append((no, p))
        return out


# ---------------------------------------------------------------- семьи (слой 3)

NUM = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?")
INT = re.compile(r"-?(0|[1-9][0-9]*)")
DEC = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
TIME = {"writer": re.compile(r"(0|[1-9][0-9]*)(\.[0-9]{1,3})?"), "reader": re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?")}
INT_MAX = 2 ** 53 - 1


class Bad(Exception):
    pass


class LexInt(int):
    def __new__(cls, t):
        v = int.__new__(cls, t)
        v.lex = t
        return v


class LexFloat(float):
    def __new__(cls, t):
        v = float.__new__(cls, t)
        v.lex = t
        return v


def strict_json(text_, finite=False):
    """JSON по грамматике json `codec.tsv`: без NaN, без повтора ключей; числа с записью. finite — текст места
    `encoding` (codec.tsv: «без NaN и бесконечностей»): число вне binary64 (`1e400`) — отказ кодека места; у объекта
    и файла такое число — отказ своего места (Family.finite)."""
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise Bad("json: repeated key %r" % k)
            d[k] = v
        return d

    def const(c):
        raise Bad("json: %s" % c)
    def num(t):
        v = LexFloat(t)
        if finite and not math.isfinite(v):
            raise Bad("json: %s is not finite in binary64" % t)
        return v
    try:
        return json.loads(text_, object_pairs_hook=pairs, parse_constant=const, parse_int=LexInt, parse_float=num)
    except RecursionError:
        raise Bad("json: nesting too deep")
    except ValueError as exc:
        raise Bad("json: %s" % exc)


def jcs(v):
    if v is None or isinstance(v, bool):
        return json.dumps(v)
    if isinstance(v, (int, float)):
        return jcs_number(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(jcs(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(v[k])
                          for k in sorted(v, key=lambda k: k.encode("utf-16-be"))) + "}"


def plain_decimal(x):
    s = format(Decimal(repr(float(x))), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def list_text(items):
    if not items:
        return ""
    if any(not isinstance(e, str) or e == "" or "," in e for e in items) or items[0].startswith("["):
        return json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return ",".join(items)


def exact_integer(v):
    lex = getattr(v, "lex", None)
    if lex is None:
        return float(v).is_integer()
    d = Decimal(lex)
    return d == d.to_integral_value()


class Family:
    """Чтение семьи В7: Family(schema_doc, kind).judge(текст или значение, mode) → {verdict, paths}."""

    def __init__(self, schema_doc, kind):
        self.sch = Schema(schema_doc)
        self.kind = kind
        self.writer = schema_doc.get("$defs", {}).get("writer")

    # ---- кодек строки (codec.tsv)
    def decode(self, chain, text_, mode):
        enc = self.sch.word(chain, "x-encoding")
        if enc:
            v = strict_json(text_, finite=True)
            if enc == "jcs" and mode == "writer" and jcs(v) != text_:
                raise Bad("jcs: the text is not canonical")
            return v
        why = "no type to decode"
        for ty in self.sch.word(chain, "x-codec", []):
            try:
                return self.decode_as(ty, text_, mode, bool(self.sch.word(chain, "x-whole")))
            except Bad as exc:
                why = str(exc)
        raise Bad(why)

    def decode_as(self, ty, t, mode, whole):
        w = mode == "writer"
        if ty in ("string", "any"):
            return t
        if ty == "integer":
            if w or whole:
                if not INT.fullmatch(t):
                    raise Bad("integer sign")
                v = int(t)
                if w and abs(v) > INT_MAX:
                    raise Bad("integer beyond 2^53 − 1")
                return v
            if not NUM.fullmatch(t):
                raise Bad("integer: not a decimal number")
            try:
                d = Decimal(t)
            except InvalidOperation:
                raise Bad("integer: not a decimal number")
            if d != d.to_integral_value():
                raise Bad("integer: not equal to an integer")
            return int(d)
        if ty == "number":
            if not (DEC if w else NUM).fullmatch(t):
                raise Bad("number record")
            x = float(t)
            if not math.isfinite(x):
                raise Bad("number: not finite")
            if w and plain_decimal(x) != t:
                raise Bad("number: not the shortest record")
            return int(x) if INT.fullmatch(t) else x
        if ty == "boolean":
            if t not in ("true", "false"):
                raise Bad("boolean")
            return t == "true"
        if ty == "time":
            if not TIME[mode].fullmatch(t):
                raise Bad("time record")
            return float(t)
        if ty == "array":
            if t == "":
                v = []
            elif t.startswith("["):
                v = strict_json(t)
                if not isinstance(v, list):
                    raise Bad("array: not a JSON array")
            else:
                v = t.split(",")
            if w and list_text(v) != t:
                raise Bad("array: not the writer's list record")
            return v
        raise Bad("%s: no record in items" % ty)

    def is_time(self, v, mode):
        if isinstance(v, bool):
            return False
        if isinstance(v, (LexInt, LexFloat)):
            return TIME[mode].fullmatch(v.lex) is not None and math.isfinite(float(v.lex))
        if isinstance(v, (int, float)):
            return math.isfinite(v) and v >= 0 and (mode == "reader" or round(v, 3) == v)
        return isinstance(v, str) and TIME[mode].fullmatch(v) is not None

    # ---- проход
    def judge(self, value, mode="reader"):
        fails, decoded = [], set()
        if not isinstance(value, (str, bytes)):
            value = copy.deepcopy(value)
        if self.kind == "object" and isinstance(value, (str, bytes)):
            try:
                value = strict_json(value.decode("utf-8") if isinstance(value, bytes) else value)
            except (Bad, UnicodeDecodeError):
                return self.result([[]])
        if self.kind == "file" and isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                return self.result([[]])
        if self.kind == "row":
            if not isinstance(value, dict):
                return self.result([[]])
            root = self.sch.resolve(self.sch.doc)
            value = dict(value)
            for k, t in list(value.items()):
                c = self.sch.child(root, value, k)
                if c is None:
                    continue
                if not isinstance(t, str):
                    fails.append([k])
                    del value[k]
                    continue
                try:
                    value[k] = self.decode(self.sch.resolve(c), t, mode)
                    decoded.add((k,))
                except Bad:
                    fails.append([k])
                    del value[k]                 # не прочитано — как у эталона: ключа нет в разобранной строке
        value = self.layer3(value, mode, decoded, fails)
        recs = py_records(self.sch.v, value)
        if mode == "writer" and self.writer is not None:
            recs += py_records(self.sch.v, value, self.writer)
        return self.result(fails + norm(recs, value), value)

    def result(self, paths, value=None):
        ps = canonical(paths)
        return {"verdict": "refused" if ps else "ok", "paths": [pointer(p) for p in ps], "value": value}

    def layer3(self, value, mode, decoded, fails):
        """Кодек мест (`x-encoding`), время, целое по записи, `max_bytes`, имена сверх `max_items` (писатель — и по
        `$defs.writer`)."""
        sch, wmap = self.sch, {}
        if mode == "writer" and self.writer is not None:
            self.writer_places(self.writer, value, [], wmap)

        def visit(chain, v, path):
            enc = sch.word(chain, "x-encoding")
            if enc and isinstance(v, str) and tuple(path) not in decoded:
                try:
                    t, v = v, strict_json(v, finite=True)
                    if enc == "jcs" and mode == "writer" and jcs(v) != t:
                        raise Bad("jcs: the text is not canonical")
                except Bad:
                    fails.append(path)
                    return None                  # место не прочитано: отказ уже записан, путь тот же
            if isinstance(v, float) and not math.isfinite(v):
                fails.append(path)               # `1e400`: число вне binary64 — не по грамматике (codec.tsv), отказ места
                return None
            if sch.word(chain, "x-time") and not self.is_time(v, mode):
                fails.append(path)
            if sch.word(chain, "x-integer") and isinstance(v, float) and not isinstance(v, bool) and v.is_integer():
                if mode == "writer" or sch.word(chain, "x-whole") or not exact_integer(v):
                    fails.append(path)
            self.limits(chain, v, path, fails)
            mains[tuple(path)] = chain
            return v
        mains = {}
        value = walk(sch, sch.doc, value, [], visit)
        value = self.finite(value, [], fails)
        for path, chain in wmap.items():
            try:
                v = at(value, list(path))
            except (KeyError, IndexError, TypeError):
                continue
            self.limits(chain, v, list(path), fails, mains.get(path, []))
        return value

    def finite(self, v, path, fails):
        """Число вне binary64 и там, куда схема не ведёт (opaque, any, лишний ключ): отказ своего места."""
        if isinstance(v, float) and not math.isfinite(v):
            fails.append(path)
            return None
        if isinstance(v, dict):
            return {k: self.finite(x, path + [k], fails) for k, x in v.items()}
        if isinstance(v, list):
            return [self.finite(x, path + [i], fails) for i, x in enumerate(v)]
        return v

    def limits(self, chain, v, path, fails, owner=None):
        """owner — узлы места в схеме (у ограничений писателя): имена `properties` считаются от них (DIALECT § 2)."""
        mb = self.sch.word(chain, "x-max-bytes")
        if mb is not None and isinstance(v, str) and len(v.encode("utf-8")) > mb:
            fails.append(path)
        mn = self.sch.word(chain, "x-max-names")
        if mn is not None and isinstance(v, dict):
            props = set()
            for s in chain + (owner or []):
                props |= set(s.get("properties", {}))
            if len([k for k in v if k not in props]) > mn:
                fails.append(path)

    def writer_places(self, s, value, path, out):
        """Места схемы `$defs.writer` с пометками слоя 3 (`x-max-bytes`, `x-max-names`)."""
        chain = self.sch.resolve(s)
        v = self.sch.variant(chain, value)
        if v is not None:
            chain = chain + self.sch.resolve(v)
        if any("x-max-bytes" in c or "x-max-names" in c for c in chain):
            out[tuple(path)] = chain
        if isinstance(value, dict):
            for k in value:
                c = self.sch.child(chain, value, k)
                if c is not None:
                    self.writer_places(c, value[k], path + [k], out)
        elif isinstance(value, list):
            for i, x in enumerate(value):
                c = self.sch.child(chain, value, i)
                if c is not None:
                    self.writer_places(c, x, path + [i], out)

