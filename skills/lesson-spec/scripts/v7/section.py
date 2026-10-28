"""Разделы норм из стандартных файлов В7 (ADR-0092; ADR-0087 п. 3 остаётся; PLAN-TRANSITION п. 1.2): «Форма» P/02.1 —
из `02.1-installer.schema.json`, `.relations.json`, `.scalars.tsv`; «Семьи данных» главы-владельца — из
`<семья>.schema.json` и `.outcomes.tsv`. Текст между маркерами норм — ровно построенный.

Язык таблиц — тот же, что у разделов диалекта (Ключ | Тип и границы | Обязательность | Урок | Смысл), слова — слова
стандарта, прочитанные из схемы: `type`, `enum`, `not`, `pattern` (выражение — как в схеме, с якорями), границы,
`properties`/`required`, `additionalProperties` с `propertyNames` (имена автора), `patternProperties` (правила по имени),
`items`, `allOf` с `if`/`then` (варианты по типу и правила), `default`, `description`, `x-owner`, `x-default-text`, слова
слоёв `x-*`. Определение, на которое ссылаются один раз и не рекурсивно, раскрыто на месте; прочие — своей таблицей.
"""
import json
import os
from pathlib import Path

INT53 = 2 ** 53 - 1
NEVER = {"not": {}}

FORM_BEGIN, FORM_END = "<!-- form:begin -->", "<!-- form:end -->"
FAMILIES_BEGIN, FAMILIES_END = "<!-- families:begin -->", "<!-- families:end -->"

TYPE_WORD = {"string": "строка", "integer": "целое", "number": "число", "boolean": "bool", "null": "null",
             "object": "отображение", "array": "список"}


def code(x):
    if isinstance(x, str):
        return '`""`' if x == "" else "`%s`" % shown(x)
    return "`%s`" % json.dumps(x, ensure_ascii=False)


def key(k):
    return '""' if k == "" else k


def key_code(k):
    return "`%s`" % key(k)


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def ref_name(s):
    r = s.get("$ref") if isinstance(s, dict) else None
    return r[len("#/$defs/"):] if isinstance(r, str) and r.startswith("#/$defs/") else None


def _types(t):
    return [t] if isinstance(t, str) else list(t or [])


def _chain(s):
    """Число первых элементов `allOf` — цепочки вариантов по типу (`[{if: {type: T_i}, then: V_i}]`, перевод
    `variants`): их типы вместе — ровно `type` места. Правило без условия (`if: {type: object}`) — не вариант."""
    n, seen = 0, []
    for e in s.get("allOf", []) if isinstance(s, dict) else []:
        if not (isinstance(e, dict) and set(e) == {"if", "then"} and isinstance(e["if"], dict)
                and set(e["if"]) == {"type"}):
            break
        n += 1
        seen += _types(e["if"]["type"])
    return n if n >= 2 and sorted(seen) == sorted(_types(s.get("type"))) else 0


def variants(s):
    """Варианты места → [then] или None."""
    n = _chain(s)
    return [e["then"] for e in s["allOf"][:n]] if n else None


def rules_of(s):
    """Правила места: элементы `allOf` с `if`/`then` после цепочки вариантов."""
    return [e for e in s.get("allOf", [])[_chain(s):] if isinstance(e, dict) and "if" in e]


def shown(s):
    """Текст значения в норме: непечатный знак (управляющий, формат, разделитель строк, суррогат) — `\\u{HHHH}`
    (запись ECMA-262 `u`; в схеме — сам знак)."""
    return "".join(c if c == " " or c.isprintable() else "\\u{%04X}" % ord(c) for c in s)


def bare(p):
    """`^(?:x)$` → x: выражение без якорей перевода (в тексте — «целиком»), знаки — shown."""
    return shown(p[4:-2] if p.startswith("^(?:") and p.endswith(")$") else p)


class SchemaSection:
    """Таблицы одной схемы. family — схема семьи: определения `common.*` раскрыты на месте (как у диалекта)."""

    def __init__(self, doc, family=False):
        self.doc, self.family = doc, family
        self.defs = {k: v for k, v in doc.get("$defs", {}).items() if k != "writer"}
        uses = {}

        def count(x):
            if isinstance(x, dict):
                n = ref_name(x)
                if n is not None and n in self.defs:
                    uses[n] = uses.get(n, 0) + 1
                for k, v in x.items():
                    if k == "patternProperties":     # правила по имени повторяют значение имён: не второе место
                        ap = x.get("additionalProperties")
                        for e in v.values():
                            count({**e, "allOf": [y for y in e.get("allOf", []) if y != ap]})
                        continue
                    count(v)
            elif isinstance(x, list):
                for v in x:
                    count(v)
        count({k: v for k, v in doc.items() if k != "$defs"})
        for v in self.defs.values():
            count(v)
        self.uses = uses
        self.recursive = {k for k in self.defs if self.reaches(k, k)}
        own = [k for k in self.defs if uses.get(k, 0) != 1 or k in self.recursive]
        if family:
            own = [k for k in own if not k.startswith("common.") or (k in self.recursive and uses.get(k))]
        self.own = sorted(own)

    def reaches(self, start, target):
        seen, stack = set(), [self.defs[start]]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                n = ref_name(x)
                if n == target:
                    return True
                if n is not None and n in self.defs and n not in seen:
                    seen.add(n)
                    stack.append(self.defs[n])
                stack += list(x.values())
            elif isinstance(x, list):
                stack += x
        return False

    def deref(self, s, stack=()):
        n = ref_name(s)
        while n is not None and n in self.defs and n not in stack:
            stack = stack + (n,)
            s = self.defs[n]
            n = ref_name(s)
        return s

    # ---- тип и границы одного места (без раскрытия ключей — они строками ниже)
    def kind(self, s):
        if s is True or s == {}:
            return "любое значение"
        if s is False or s == NEVER:
            return "значения нет"
        n = ref_name(s)
        if n is not None:
            own = {k: v for k, v in s.items() if k not in ("$ref", "description", "default", "x-owner",
                                                            "x-default-text", "x-step", "x-default", "x-class")}
            base = "по определению `%s`" % n if n in self.own else self.kind(self.defs[n])
            more = self.kind(dict(own, type=[])) if own else ""
            return base + ("; " + more if more and more != "любое значение" else "")
        vs = variants(s)
        if vs is not None:
            return " или ".join("(%s)" % self.kind(v) for v in vs)
        ts = s.get("type")
        ts = [ts] if isinstance(ts, str) else list(ts or [])
        parts = []
        if s.get("x-time"):
            parts.append("время (P/01.1 Н0 «Время в строке»)")
            ts = [t for t in ts if t not in ("number", "string")]
        parts += [self.type_word(s, t) for t in ts]
        if not parts and "enum" not in s and "anyOf" not in s and "type" not in s:
            parts.append("любое значение")
        if "anyOf" in s and not ts:
            parts.append(" или ".join("(%s)" % self.kind(x) for x in s["anyOf"]))
        extra = []
        if "enum" in s:
            extra.append("одно из: " + ", ".join(code(x) for x in s["enum"]))
        if "not" in s:
            extra.append(self.not_words(s["not"]))
        if "pattern" in s:
            extra.append("целиком `%s`" % bare(s["pattern"]))
        integer_place = s.get("x-integer-place")
        for k, w in (("minimum", "≥"), ("exclusiveMinimum", ">"), ("maximum", "≤")):
            if k in s and not (integer_place and abs(s[k]) == INT53):
                extra.append("%s %s" % (w, s[k]))
        if integer_place:
            extra.append("целое по значению (`4.0` — `4`, x-integer-place)")
        if s.get("x-whole"):
            extra.append("целый знак и у читателя (x-whole)")
        if "x-max-bytes" in s:
            extra.append("не длиннее %d байт UTF-8 (x-max-bytes)" % s["x-max-bytes"])
        if s.get("x-encoding") == "json":
            extra.append("в `items` — текст JSON (x-encoding: json)")
        elif s.get("x-encoding") == "jcs":
            extra.append("в `items` — текст JSON, у писателя — JCS (x-encoding: jcs)")
        return "; ".join([" или ".join(parts)] + extra if parts else extra)

    def not_words(self, x):
        if isinstance(x, dict) and set(x) == {"anyOf"}:
            return "; ".join(self.not_words(y) for y in x["anyOf"])
        if isinstance(x, dict) and set(x) == {"enum"}:
            return "не из: " + ", ".join(code(v) for v in x["enum"])
        if isinstance(x, dict) and set(x) <= {"type", "pattern"} and "pattern" in x:
            return "не целиком `%s`" % bare(x["pattern"])
        return "не (%s)" % self.kind(x)

    def type_word(self, s, t):
        if t == "array":
            w = "список"
            if "minItems" in s:
                w += ", не короче %d" % s["minItems"]
            if "maxItems" in s:
                w += ", не длиннее %d" % s["maxItems"]
            if s.get("uniqueItems"):
                w += ", без повторов"
            if "items" in s:
                w += ", элемент — %s" % self.kind(s["items"])
            return w
        if t == "object":
            if s.get("x-opaque"):
                return "отображение, opaque"
            w = "отображение"
            props, req = s.get("properties"), s.get("required", [])
            if props is not None:
                w += " `{%s}`" % ", ".join(key(k) if k in req else key(k) + "?" for k in props)
            ap = s.get("additionalProperties")
            if isinstance(ap, dict) or ap is True:
                names = s.get("propertyNames")
                if isinstance(names, dict) and props and set(names) == {"anyOf"}:
                    names = names["anyOf"][1]
                w += (" и прочие" if props else "") + " имена автора: имя — %s, значение — %s" % (
                    self.kind(names) if names is not None else "строка", self.kind(ap))
                if s.get("x-ordered"):
                    w += "; порядок автора (x-ordered)"
                if "maxProperties" in s:
                    w += "; не больше %d имён" % s["maxProperties"]
                if "x-max-names" in s:
                    w += "; не больше %d имён (x-max-names)" % s["x-max-names"]
            elif req and props is None:
                w += "; обязательны " + ", ".join(key_code(k) for k in req)
            return w
        return TYPE_WORD[t]

    def need(self, parent, k, s):
        req = parent is not None and k in parent.get("required", [])
        out = "обязателен" if req else "необязателен"
        if isinstance(s, dict) and "default" in s:
            out += "; умолчание %s" % code(s["default"])
        if isinstance(s, dict) and "x-default-text" in s:
            out += "; умолчание словами: %s" % s["x-default-text"]
        return out

    # ---- условия и действия правил
    def cond(self, c):
        if not isinstance(c, dict):
            return json.dumps(c, ensure_ascii=False)
        if c == {"type": "object"}:
            return None
        if set(c) == {"allOf"}:
            parts = [self.cond(x) for x in c["allOf"]]
            return " и ".join(p for p in parts if p)
        if set(c) == {"required"}:
            return " и ".join("есть %s" % key_code(k) for k in c["required"])
        if set(c) == {"not"} and isinstance(c["not"], dict) and set(c["not"]) == {"required"}:
            return " и ".join("нет %s" % key_code(k) for k in c["not"]["required"])
        if set(c) == {"required", "properties"} and len(c["required"]) == 1 and list(c["properties"]) == c["required"]:
            k = c["required"][0]
            v = c["properties"][k]
            if set(v) == {"enum"}:
                return "%s — %s" % (key_code(k), ", ".join(code(x) for x in v["enum"]))
        if set(c) == {"anyOf"}:
            one = self.exactly_one(c)
            if one is not None:
                return "сказан ровно один из %s" % ", ".join(key_code(k) for k in one)
            alts = c["anyOf"]
            if len(alts) == 2 and alts[1] == {"not": {"required": alts[0].get("required", [None])}}:
                return "%s (или ключа нет — умолчание)" % self.cond(alts[0])
            return " или ".join("(%s)" % self.cond(x) for x in alts)
        if set(c) == {"not"}:
            inner = self.cond(c["not"])
            if " — " in inner and " и " not in inner and " или " not in inner:
                k, v = inner.split(" — ", 1)
                return "%s не %s" % (k, v)
            return "не (%s)" % inner
        if set(c) == {"required", "not"} and len(c["required"]) == 1:
            return "%s без прочих" % key_code(c["required"][0])
        return "`%s`" % json.dumps(c, ensure_ascii=False)

    @staticmethod
    def exactly_one(c):
        ks = []
        for x in c["anyOf"]:
            if not (isinstance(x, dict) and set(x) == {"required", "not"} and len(x["required"]) == 1):
                return None
            ks.append(x["required"][0])
        return ks

    def act(self, t, description=None):
        if t is False:
            return "отказ" + (": %s" % description if description else "")
        if not isinstance(t, dict):
            return "`%s`" % json.dumps(t, ensure_ascii=False)
        out = []
        for x in t.get("allOf", []):
            out.append(self.act(x))
        if "required" in t:
            out.append("обязательны " + ", ".join(key_code(k) for k in t["required"]) + " (путь — недостающий ключ)")
        props = t.get("properties", {})
        never = [k for k, v in props.items() if v == NEVER or v is False]
        if never:
            out.append("запрещены " + ", ".join(key_code(k) for k in never) + " (путь — запрещённый ключ)")
        for k, v in props.items():
            if k not in never:
                out.append("%s — ещё и %s" % (key_code(k), self.kind(v)))
        if "anyOf" in t:
            ks = [x["required"][0] for x in t["anyOf"] if isinstance(x, dict) and set(x) == {"required"}
                  and len(x["required"]) == 1]
            if len(ks) == len(t["anyOf"]):
                out.append("хотя бы один из " + ", ".join(key_code(k) for k in ks) + " (путь отображения)")
            else:
                out.append("одно из: " + " или ".join("(%s)" % self.act(x) for x in t["anyOf"]))
        if "if" in t:
            c = self.cond(t["if"])
            out.append(("если %s: " % c if c else "") + self.act(t.get("then", True)))
        rest = set(t) - {"allOf", "required", "properties", "anyOf", "if", "then"}
        if rest:
            out.append("ещё и %s" % self.kind({k: t[k] for k in rest}))
        return "; ".join(out)

    def rule_text(self, r, name=None):
        c = self.cond(r["if"])
        if name is not None:
            c = name + (" и " + c if c else "")
        return ("если " + c + ": " if c else "") + self.act(r.get("then", True), r.get("description")) + "."

    # ---- строки таблицы и правила
    def walk(self, path, parent, k, s, rows, rules, stack=()):
        owner = s.get("x-owner", "") if isinstance(s, dict) else ""
        desc = s.get("description", "") if isinstance(s, dict) else ""
        rows.append((path, self.kind(s), self.need(parent, k, s), owner, desc))
        n = ref_name(s) if isinstance(s, dict) else None
        if n is not None and (n in self.own or n in stack):
            return
        self.expand(path, s, rows, rules, stack, own=True)

    def expand(self, path, s, rows, rules, stack, own=False):
        if not isinstance(s, dict):
            return
        n = ref_name(s)
        if n is not None and n in self.own and not own:
            return
        t = self.deref(s, stack)
        while n is not None and n in self.defs and n not in stack:
            stack = stack + (n,)
            n = ref_name(self.defs[n])
        if rules_of(t):
            rules.append((path, t, None))
        for i, v in enumerate(variants(t) or []):
            vt = self.deref(v, stack)
            if isinstance(vt, dict) and ("properties" in vt or "additionalProperties" in vt or "items" in vt):
                self.walk_variant("%s ⟨вариант %d⟩" % (path, i + 1), v, rows, rules, stack)
        for k, c in (t.get("properties") or {}).items():
            self.walk("%s.%s" % (path, key(k)) if path else key(k), t, k, c, rows, rules, stack)
        ap = t.get("additionalProperties")
        if isinstance(ap, dict) or ap is True:
            self.walk("%s.<имя>" % path, None, None, ap if isinstance(ap, dict) else {}, rows, rules, stack)
            for pat, ps in (t.get("patternProperties") or {}).items():
                name = ("имя не целиком `%s`" % bare(ps["x-complement-of"]) if "x-complement-of" in ps
                        else "имя целиком `%s`" % bare(pat))
                for r in ps.get("allOf", []):
                    if isinstance(r, dict) and "if" in r:
                        rules.append(("%s.<имя>" % path, r, name))
                    elif isinstance(r, dict) and "description" in r and set(r) == {"description"}:
                        continue
        if "items" in t:
            self.walk("%s[]" % path, None, None, t["items"], rows, rules, stack)

    def walk_variant(self, path, v, rows, rules, stack):
        n = ref_name(v)
        if n is not None and n in self.own:
            return
        self.expand(path, v, rows, rules, stack, own=True)

    @staticmethod
    def table(rows):
        out = ["| Ключ | Тип и границы | Обязательность | Урок | Смысл |", "|---|---|---|---|---|"]
        for p, k, need, owner, desc in rows:
            out.append("| `%s` | %s | %s | %s | %s |" % (cell(p), cell(k), cell(need), cell(owner), cell(desc)))
        return out

    def rules_text(self, holders):
        out = []
        for path, t, name in holders:
            items = [t] if name is not None else rules_of(t)
            for r in items:
                out.append("- `%s`: %s" % (path or "<корень>", self.rule_text(r, name)))
        return out

    def root_body(self, head="#### Корень"):
        rows, rules = [], []
        self.expand("", self.doc, rows, rules, (), own=True)
        out = ([head, ""] if head else []) + self.table(rows) + [""]
        if rules:
            out += ["Правила:", ""] + self.rules_text(rules) + [""]
        return out

    def defs_body(self, head="#### Определения"):
        if not self.own:
            return []
        out = [head, ""] if head else []
        for k in self.own:
            d = self.defs[k]
            desc = d.get("description") if isinstance(d, dict) else None
            out += ["**`%s`**%s" % (k, (" — " + cell(desc)) if desc else ""), ""]
            rows, rules = [("<%s>" % k, self.kind(d), "", d.get("x-owner", ""), "")], []
            self.expand("<%s>" % k, d, rows, rules, (k,), own=True)
            out += self.table(rows) + [""]
            if rules:
                out += ["Правила:", ""] + self.rules_text(rules) + [""]
        return out

    def writer_body(self):
        """Ограничения писателя (`$defs.writer`, ADR-0092 п. 15): место → слова."""
        w = self.doc.get("$defs", {}).get("writer")
        if not w:
            return []
        wdefs = w.get("$defs", {})
        rows = []

        def rec(s, path, stack):
            if not isinstance(s, dict):
                return
            r = s.get("$ref", "")
            if r.startswith("#/$defs/writer/$defs/"):
                n = r.rsplit("/", 1)[1]
                if n not in stack:
                    rec(wdefs[n], path, stack + (n,))
                return
            words = {k: v for k, v in s.items() if k not in ("properties", "additionalProperties", "items", "allOf",
                                                              "$defs", "propertyNames")}
            if words:
                ws = self.kind(dict(words, type=[]))
                for k, w_ in (("minItems", "не короче %d"), ("maxItems", "не длиннее %d"), ("maxProperties",
                                                                                              "не больше %d имён")):
                    if k in words:
                        ws += "; " + w_ % words[k]
                if words.get("uniqueItems"):
                    ws += "; без повторов"
                if "x-max-names" in words:
                    ws += "; не больше %d имён (x-max-names)" % words["x-max-names"]
                rows.append((path or "<корень>", ws.strip("; ")))
            if "propertyNames" in s:
                pn = s["propertyNames"]
                if isinstance(pn, dict) and set(pn) == {"anyOf"}:
                    pn = pn["anyOf"][1]
                rows.append(("%s.<имя> (имя)" % path, self.kind(pn)))
            for e in s.get("allOf", []):
                rec(e.get("then", {}), path, stack)
            for k, c in (s.get("properties") or {}).items():
                if c is not True:
                    rec(c, "%s.%s" % (path, key(k)) if path else key(k), stack)
            if isinstance(s.get("additionalProperties"), dict):
                rec(s["additionalProperties"], "%s.<имя>" % path, stack)
            if isinstance(s.get("items"), dict):
                rec(s["items"], "%s[]" % path, stack)
        rec({k: v for k, v in w.items() if k != "$defs"}, "", ())
        if not rows:
            return []
        out = ["Только у писателя (`$defs.writer`):", "", "| Ключ | Ещё и |", "|---|---|"]
        out += ["| `%s` | %s |" % (cell(p), cell(x)) for p, x in rows]
        return out + [""]


# ---------------------------------------------------------------- раздел «Форма» P/02.1

def link(norms, root, target):
    return os.path.relpath(Path(root) / target, Path(norms).parent).replace(os.sep, "/")


def build_form_section(schema_doc, relations_doc, scalars):
    """Текст раздела «Форма» между маркерами FORM_BEGIN и FORM_END. scalars — (строки, пределы) v7.textv7.load_scalars."""
    sec = SchemaSection(schema_doc)
    out = ["### Форма (построена из стандартных файлов)", "",
           "Форма — JSON Schema 2020-12 `02.1-installer.schema.json`, связи — CEL `02.1-installer.relations.json`, слова "
           "слоёв — `02.1-installer.layers.tsv` (ADR-0092). Класс отказа — слой, где отказ: `text` (текст, Н1.1), `form` "
           "(форма), `relations` (связи — только при чистой форме). Выражение — целиком, как в схеме (ECMA-262 `u` ∩ RE2, "
           "`.` — любой знак). Целое место: границы ±(2^53 − 1), значение с целым значением — целое.", ""]
    out += sec.root_body()
    out += sec.defs_body()
    rows_sc, limits = scalars
    out += ["#### Таблица скаляров (Н1.1)", "", "Простой скаляр — по первой совпавшей строке сверху; в кавычках и "
            "блочный — строка.", "", "| Вид | Образец (целиком) |", "|---|---|"]
    out += ["| %s | `%s` |" % (k, cell(p) if p else "") for k, p in rows_sc]
    out += ["", "Пределы: целое по модулю не больше %d; дробное по модулю не больше %r; вне пределов и nonfinite — "
            "отказ формы на пути значения." % (limits["int_max"], limits["float_max"]), ""]
    out += ["#### Связи (Н1.4)", "", "Только при чистой форме (Н3). Строка — выражение CEL файла связей; отказ — "
            "`refused:relations`, путь — место, которое выражение называет.", "",
            "| № | Путь | Отношение | Норма |", "|---|---|---|---|"]
    for r in relations_doc["rows"]:
        out.append("| %d | `%s` | `%s` | %s |" % (r["no"], cell(r["path"]), cell(r["relation"]), cell(r["norm"])))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- раздел «Семьи данных»

KIND_WORD = {"row": "строка", "object": "объект", "file": "файл"}
UNREADABLE = {"row": "нечитаемой строки", "object": "нечитаемого объекта", "file": "нечитаемого файла"}
CATALOG = Path("Platform/common/data/catalog.tsv")
CODEC = Path("Platform/common/data/codec.tsv")


def build_families_section(norms, root, families):
    """families — [(строка каталога, путь схемы, документ схемы, путь исходов, [spec.Outcome])]."""
    lk = lambda t: link(norms, root, t)   # noqa: E731
    files = any(row["kind"] == "file" for row, *_ in families)
    out = ["### Семьи данных (построены из стандартных файлов)", "",
           "Форма строк и объектов%s, которыми глава владеет по [каталогу](%s), — JSON Schema 2020-12 семьи (ADR-0092). "
           "Экземпляр строки — `{key, row}`, объекта — `{key, object}`%s; ключ — грамматика колонки `key` каталога. "
           "Поля `row` — значения `items` после [кодека](%s): писатель проверяет схему и её `$defs.writer`, читатель — "
           "схему (слой 3 — слова `x-*` схемы). Нечитаемо — строка не раскодировалась или не прошла схему в режиме "
           "читателя; исход — по таблице исходов семьи: путь — префикс пути отказа (пустой — строка целиком), при "
           "нескольких путях отказа действует исход с наименьшим приоритетом."
           % (" и файлов JSON" if files else "", lk(CATALOG),
              ", файла — `{key, file}` (текст файла UTF-8; корень схемы — его разбор, `x-encoding`)" if files else "",
              lk(CODEC)), ""]
    for row, schema_path, doc, outcomes_path, outcomes in families:
        out += ["#### `%s` — %s" % (row["key"], KIND_WORD[row["kind"]]), "",
                "Схема — [`%s`](%s), исходы — [`%s`](%s); версия формы %s; норма — %s." % (
                    schema_path.name, lk(schema_path.relative_to(root)), outcomes_path.name,
                    lk(outcomes_path.relative_to(root)), row["version"], row["norm"]), ""]
        sec = SchemaSection(doc, family=True)
        out += sec.root_body(head=None)
        out += sec.writer_body()
        out += sec.defs_body(head=None)
        out += ["Исходы %s:" % UNREADABLE[row["kind"]], "",
                "| Путь отказа | Исход | Приоритет | Единица | Норма |", "|---|---|---|---|---|"]
        for o in outcomes:
            out.append("| %s | %s | %d | %s | %s |" % ("`%s`" % cell(o.path) if o.path else "%s целиком" % KIND_WORD[row["kind"]],
                                                   cell(o.outcome), o.priority, o.unit, cell(o.norm)))
        out.append("")
    return "\n".join(out)
