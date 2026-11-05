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
import re
from pathlib import Path

INT53 = 2 ** 53 - 1
NEVER = {"not": {}}

FORM_BEGIN, FORM_END = "<!-- form:begin -->", "<!-- form:end -->"
FAMILIES_BEGIN, FAMILIES_END = "<!-- families:begin -->", "<!-- families:end -->"

TYPE_WORD = {"string": "строка", "integer": "целое", "number": "число", "boolean": "bool", "null": "null",
             "object": "отображение", "array": "список"}
TYPE_WORD_EN = {"string": "string", "integer": "integer", "number": "number", "boolean": "bool", "null": "null",
                "object": "map", "array": "list"}
LANGS = ("ru", "en")


def tr(lang, ru, en):
    """The word of a block in its language (ADR-0121 addendum (3) item 1): the source carries the English block, `ru/` —
    the Russian one; the values (keys, roles, outcomes, numbers) are the same in both."""
    if lang not in LANGS:
        raise ValueError("language of a built block: one of %s, not %r" % (", ".join(LANGS), lang))
    return en if lang == "en" else ru


def lang_of(norms, root):
    """The language of the block of a norms file: `en` for the source of a lesson in the layout of ADR-0124 (the lesson
    holds `ru/`, the file is outside it), `ru` for its translation `ru/…` and for a lesson of the former layout."""
    try:
        parts = Path(norms).resolve().relative_to(Path(root).resolve()).parts
    except ValueError:
        return "ru"
    if len(parts) >= 3 and parts[0] in ("Platform", "VMS") and (Path(root) / parts[0] / parts[1] / "ru").is_dir():
        return "ru" if parts[2] == "ru" else "en"
    return "ru"


def code(x):
    if isinstance(x, str):
        return '`""`' if x == "" else "`%s`" % shown(x)
    return "`%s`" % json.dumps(x, ensure_ascii=False)


def key(k):
    return '""' if k == "" else k


def key_code(k):
    return "`%s`" % key(k)


def code_cell(s):
    """A cell that the table wraps in a code span: only `|` escaped, one line."""
    return str(s).replace("|", "\\|").replace("\n", " ")


def cell(s):
    """A table cell: `|` escaped, one line; a `<` before a Latin letter outside code spans is escaped (`\\<member>`): an
    English placeholder in plain text is not raw HTML (ADR-0121 addendum (5) item 3)."""
    parts = re.split(r"(`[^`]*`)", str(s).replace("|", "\\|").replace("\n", " "))
    return "".join(p if p.startswith("`") else re.sub(r"(?<!\\)<(?=[A-Za-z/!?])", r"\\<", p) for p in parts)


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

    def __init__(self, doc, family=False, lang="ru"):
        self.doc, self.family, self.lang = doc, family, lang
        tr(lang, "", "")
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

    def t(self, ru, en):
        return tr(self.lang, ru, en)

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

    _MISSING = object()

    def note(self, s, k, default=None):
        """Пометка места (`description`, `default`, `x-default-text`, `x-owner`): своя, иначе у цели ссылки — по цепочке
        `$ref` (как пометка позиции диалекта: генератор кладёт пометки определения на определение)."""
        seen = set()
        while isinstance(s, dict):
            if k in s:
                return s[k]
            n = ref_name(s)
            if n is None or n not in self.defs or n in seen:
                return default
            seen.add(n)
            s = self.defs[n]
        return default

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
            return self.t("любое значение", "any value")
        if s is False or s == NEVER:
            return self.t("значения нет", "no value")
        n = ref_name(s)
        if n is not None:
            own = {k: v for k, v in s.items() if k not in ("$ref", "description", "default", "x-owner",
                                                            "x-default-text", "x-step", "x-default", "x-class")}
            base = self.t("по определению `%s`", "by the definition `%s`") % n if n in self.own else self.kind(self.defs[n])
            more = self.kind(dict(own, type=[])) if own else ""
            return base + ("; " + more if more and more != self.t("любое значение", "any value") else "")
        vs = variants(s)
        if vs is not None:
            return self.t(" или ", " or ").join("(%s)" % self.kind(v) for v in vs)
        ts = s.get("type")
        ts = [ts] if isinstance(ts, str) else list(ts or [])
        parts = []
        if s.get("x-time"):
            parts.append(self.t("время (P/01.1 N0 «Время в строке»)", "time (P/01.1 N0 «Time in a row»)"))
            ts = [t for t in ts if t not in ("number", "string")]
        parts += [self.type_word(s, t) for t in ts]
        if not parts and "enum" not in s and "anyOf" not in s and "type" not in s:
            parts.append(self.t("любое значение", "any value"))
        if "anyOf" in s and not ts:
            parts.append(self.t(" или ", " or ").join("(%s)" % self.kind(x) for x in s["anyOf"]))
        extra = []
        if "enum" in s:
            extra.append(self.t("одно из: ", "one of: ") + ", ".join(code(x) for x in s["enum"]))
        if "not" in s:
            extra.append(self.not_words(s["not"]))
        if "pattern" in s:
            extra.append(self.t("целиком `%s`", "matching `%s` in full") % bare(s["pattern"]))
        integer_place = s.get("x-integer-place")
        for k, w in (("minimum", "≥"), ("exclusiveMinimum", ">"), ("maximum", "≤")):
            if k in s and not (integer_place and abs(s[k]) == INT53):
                extra.append("%s %s" % (w, s[k]))
        if integer_place:
            extra.append(self.t("целое по значению (`4.0` — `4`, x-integer-place)", "integral by value (`4.0` is `4`, x-integer-place)"))
        if s.get("x-whole"):
            extra.append(self.t("целый знак и у читателя (x-whole)", "the whole sign for the reader too (x-whole)"))
        if "x-max-bytes" in s:
            extra.append(self.t("не длиннее %d байт UTF-8 (x-max-bytes)", "at most %d bytes of UTF-8 (x-max-bytes)") % s["x-max-bytes"])
        if s.get("x-encoding") == "json":
            extra.append(self.t("в `items` — текст JSON (x-encoding: json)", "in `items` — a JSON text (x-encoding: json)"))
        elif s.get("x-encoding") == "jcs":
            extra.append(self.t("в `items` — текст JSON, у писателя — JCS (x-encoding: jcs)", "in `items` — a JSON text, JCS at the writer (x-encoding: jcs)"))
        return "; ".join([self.t(" или ", " or ").join(parts)] + extra if parts else extra)

    def not_words(self, x):
        if isinstance(x, dict) and set(x) == {"anyOf"}:
            return "; ".join(self.not_words(y) for y in x["anyOf"])
        if isinstance(x, dict) and set(x) == {"enum"}:
            return self.t("не из: ", "not one of: ") + ", ".join(code(v) for v in x["enum"])
        if isinstance(x, dict) and set(x) <= {"type", "pattern"} and "pattern" in x:
            return self.t("не целиком `%s`", "not matching `%s` in full") % bare(x["pattern"])
        return self.t("не (%s)", "not (%s)") % self.kind(x)

    def type_word(self, s, t):
        if t == "array":
            w = self.t("список", "list")
            if "minItems" in s:
                w += self.t(", не короче %d", ", at least %d items") % s["minItems"]
            if "maxItems" in s:
                w += self.t(", не длиннее %d", ", at most %d items") % s["maxItems"]
            if s.get("uniqueItems"):
                w += self.t(", без повторов", ", without repeats")
            if "items" in s:
                w += self.t(", элемент — %s", ", element — %s") % self.kind(s["items"])
            return w
        if t == "object":
            if s.get("x-opaque"):
                return self.t("отображение, opaque", "map, opaque")
            w = self.t("отображение", "map")
            props, req = s.get("properties"), s.get("required", [])
            if props is not None:
                w += " `{%s}`" % ", ".join(key(k) if k in req else key(k) + "?" for k in props)
            ap = s.get("additionalProperties")
            if isinstance(ap, dict) or ap is True:
                names = s.get("propertyNames")
                if isinstance(names, dict) and props and set(names) == {"anyOf"}:
                    names = names["anyOf"][1]
                w += (self.t(" и прочие", " and other") if props else "") + self.t(
                    " имена автора: имя — %s, значение — %s", " author names: name — %s, value — %s") % (
                    self.kind(names) if names is not None else self.t("строка", "string"), self.kind(ap))
                if s.get("x-ordered"):
                    w += self.t("; порядок автора (x-ordered)", "; the author's order (x-ordered)")
                if "maxProperties" in s:
                    w += self.t("; не больше %d имён", "; at most %d names") % s["maxProperties"]
                if "x-max-names" in s:
                    w += self.t("; не больше %d имён (x-max-names)", "; at most %d names (x-max-names)") % s["x-max-names"]
            elif req and props is None:
                w += self.t("; обязательны ", "; required ") + ", ".join(key_code(k) for k in req)
            return w
        return (TYPE_WORD_EN if self.lang == "en" else TYPE_WORD)[t]

    def need(self, parent, k, s):
        req = parent is not None and k in parent.get("required", [])
        out = self.t("обязателен", "required") if req else self.t("необязателен", "optional")
        d = self.note(s, "default", self._MISSING)
        if d is not self._MISSING:
            out += self.t("; умолчание %s", "; default %s") % code(d)
        dt = self.note(s, "x-default-text")
        if dt:
            out += self.t("; умолчание словами: %s", "; default in words: %s") % dt
        return out

    # ---- условия и действия правил
    def cond(self, c):
        if not isinstance(c, dict):
            return json.dumps(c, ensure_ascii=False)
        if c == {"type": "object"}:
            return None
        if set(c) == {"allOf"}:
            parts = [self.cond(x) for x in c["allOf"]]
            return self.t(" и ", " and ").join(p for p in parts if p)
        if set(c) == {"required"}:
            return self.t(" и ", " and ").join(self.t("есть %s", "%s present") % key_code(k) for k in c["required"])
        if set(c) == {"not"} and isinstance(c["not"], dict) and set(c["not"]) == {"required"}:
            return self.t(" и ", " and ").join(self.t("нет %s", "%s absent") % key_code(k) for k in c["not"]["required"])
        if set(c) == {"required", "properties"} and len(c["required"]) == 1 and list(c["properties"]) == c["required"]:
            k = c["required"][0]
            v = c["properties"][k]
            if set(v) == {"enum"}:
                return "%s — %s" % (key_code(k), ", ".join(code(x) for x in v["enum"]))
        if set(c) == {"anyOf"}:
            one = self.exactly_one(c)
            if one is not None:
                return self.t("сказан ровно один из %s", "exactly one of %s stated") % ", ".join(key_code(k) for k in one)
            alts = c["anyOf"]
            if len(alts) == 2 and alts[1] == {"not": {"required": alts[0].get("required", [None])}}:
                return self.t("%s (или ключа нет — умолчание)", "%s (or the key absent — the default)") % self.cond(alts[0])
            return self.t(" или ", " or ").join("(%s)" % self.cond(x) for x in alts)
        if set(c) == {"not"}:
            inner = self.cond(c["not"])
            if " — " in inner and self.t(" и ", " and ") not in inner and self.t(" или ", " or ") not in inner:
                k, v = inner.split(" — ", 1)
                return self.t("%s не %s", "%s not %s") % (k, v)
            return self.t("не (%s)", "not (%s)") % inner
        if set(c) == {"required", "not"} and len(c["required"]) == 1:
            return self.t("%s без прочих", "%s without others") % key_code(c["required"][0])
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
            return self.t("отказ", "refused") + (": %s" % description if description else "")
        if not isinstance(t, dict):
            return "`%s`" % json.dumps(t, ensure_ascii=False)
        out = []
        for x in t.get("allOf", []):
            out.append(self.act(x))
        if "required" in t:
            out.append(self.t("обязательны ", "required ") + ", ".join(key_code(k) for k in t["required"])
                       + self.t(" (путь — недостающий ключ)", " (the path is the missing key)"))
        props = t.get("properties", {})
        never = [k for k, v in props.items() if v == NEVER or v is False]
        if never:
            out.append(self.t("запрещены ", "forbidden ") + ", ".join(key_code(k) for k in never)
                       + self.t(" (путь — запрещённый ключ)", " (the path is the forbidden key)"))
        for k, v in props.items():
            if k not in never:
                out.append(self.t("%s — ещё и %s", "%s — also %s") % (key_code(k), self.kind(v)))
        if "anyOf" in t:
            ks = [x["required"][0] for x in t["anyOf"] if isinstance(x, dict) and set(x) == {"required"}
                  and len(x["required"]) == 1]
            if len(ks) == len(t["anyOf"]):
                out.append(self.t("хотя бы один из ", "at least one of ") + ", ".join(key_code(k) for k in ks)
                           + self.t(" (путь отображения)", " (the path of the map)"))
            else:
                out.append(self.t("одно из: ", "one of: ") + self.t(" или ", " or ").join("(%s)" % self.act(x) for x in t["anyOf"]))
        if "if" in t:
            c = self.cond(t["if"])
            out.append((self.t("если %s: ", "if %s: ") % c if c else "") + self.act(t.get("then", True)))
        rest = set(t) - {"allOf", "required", "properties", "anyOf", "if", "then"}
        if rest:
            out.append(self.t("ещё и %s", "also %s") % self.kind({k: t[k] for k in rest}))
        return "; ".join(out)

    def rule_text(self, r, name=None):
        c = self.cond(r["if"])
        if name is not None:
            c = name + (self.t(" и ", " and ") + c if c else "")
        return (self.t("если ", "if ") + c + ": " if c else "") + self.act(r.get("then", True), r.get("description")) + "."

    # ---- строки таблицы и правила
    def walk(self, path, parent, k, s, rows, rules, stack=()):
        owner = self.note(s, "x-owner", "")
        desc = self.note(s, "description", "")
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
                self.walk_variant(self.t("%s ⟨вариант %d⟩", "%s ⟨variant %d⟩") % (path, i + 1), v, rows, rules, stack)
        for k, c in (t.get("properties") or {}).items():
            self.walk("%s.%s" % (path, key(k)) if path else key(k), t, k, c, rows, rules, stack)
        ap = t.get("additionalProperties")
        if isinstance(ap, dict) or ap is True:
            at = len(rows)
            self.walk(self.t("%s.<имя>", "%s.<name>") % path, None, None, ap if isinstance(ap, dict) else {}, rows, rules, stack)
            if self.family:                      # строка значения имён несёт и имя (как раздел семей диалекта, №22)
                names = t.get("propertyNames")
                if isinstance(names, dict) and set(names) == {"anyOf"}:
                    names = names["anyOf"][1]
                p_, kind, need, owner, desc = rows[at]
                name = self.kind(names) if names is not None else self.t("строка", "string")
                if not path and name != self.t("строка", "string"):
                    kind = self.t("имя — %s; значение — %s", "name — %s; value — %s") % (name, kind)
                note = names.get("description") if isinstance(names, dict) else None   # своё, не определения
                if note:
                    desc = self.t("имя: %s; %s", "name: %s; %s") % (note, desc) if desc else self.t("имя: %s", "name: %s") % note
                rows[at] = (p_, kind, need, owner, desc)
            for pat, ps in (t.get("patternProperties") or {}).items():
                name = (self.t("имя не целиком `%s`", "name not matching `%s` in full") % bare(ps["x-complement-of"])
                        if "x-complement-of" in ps else self.t("имя целиком `%s`", "name matching `%s` in full") % bare(pat))
                for r in ps.get("allOf", []):
                    if isinstance(r, dict) and "if" in r:
                        rules.append((self.t("%s.<имя>", "%s.<name>") % path, r, name))
                    elif isinstance(r, dict) and "description" in r and set(r) == {"description"}:
                        continue
        if "items" in t:
            self.walk("%s[]" % path, None, None, t["items"], rows, rules, stack)

    def walk_variant(self, path, v, rows, rules, stack):
        n = ref_name(v)
        if n is not None and n in self.own:
            return
        self.expand(path, v, rows, rules, stack, own=True)

    def table(self, rows):
        out = [self.t("| Ключ | Тип и границы | Обязательность | Урок | Смысл |",
                      "| Key | Type and bounds | Requirement | Lesson | Meaning |"), "|---|---|---|---|---|"]
        for p, k, need, owner, desc in rows:
            out.append("| `%s` | %s | %s | %s | %s |" % (code_cell(p), cell(k), cell(need), cell(owner), cell(desc)))
        return out

    def rules_text(self, holders):
        out = []
        for path, t, name in holders:
            items = [t] if name is not None else rules_of(t)
            for r in items:
                out.append("- `%s`: %s" % (path or self.t("<корень>", "<root>"), self.rule_text(r, name)))
        return out

    def root_body(self, head=True):
        head = self.t("#### Корень", "#### Root") if head is True else head
        rows, rules = [], []
        self.expand("", self.doc, rows, rules, (), own=True)
        out = ([head, ""] if head else []) + self.table(rows) + [""]
        if rules:
            out += [self.t("Правила:", "Rules:"), ""] + self.rules_text(rules) + [""]
        return out

    def defs_body(self, head=True):
        if not self.own:
            return []
        head = self.t("#### Определения", "#### Definitions") if head is True else head
        out = [head, ""] if head else []
        for k in self.own:
            d = self.defs[k]
            desc = d.get("description") if isinstance(d, dict) else None
            out += ["**`%s`**%s" % (k, (" — " + cell(desc)) if desc else ""), ""]
            rows, rules = [("<%s>" % k, self.kind(d), "", d.get("x-owner", ""), "")], []
            self.expand("<%s>" % k, d, rows, rules, (k,), own=True)
            out += self.table(rows) + [""]
            if rules:
                out += [self.t("Правила:", "Rules:"), ""] + self.rules_text(rules) + [""]
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
                for k, w_ in (("minItems", self.t("не короче %d", "at least %d items")),
                              ("maxItems", self.t("не длиннее %d", "at most %d items")),
                              ("maxProperties", self.t("не больше %d имён", "at most %d names"))):
                    if k in words:
                        ws += "; " + w_ % words[k]
                if words.get("uniqueItems"):
                    ws += self.t("; без повторов", "; without repeats")
                if "x-max-names" in words:
                    ws += self.t("; не больше %d имён (x-max-names)", "; at most %d names (x-max-names)") % words["x-max-names"]
                rows.append((path or self.t("<корень>", "<root>"), ws.strip("; ")))
            if "propertyNames" in s:
                pn = s["propertyNames"]
                if isinstance(pn, dict) and set(pn) == {"anyOf"}:
                    pn = pn["anyOf"][1]
                rows.append((self.t("%s.<имя> (имя)", "%s.<name> (name)") % path, self.kind(pn)))
            for e in s.get("allOf", []):
                rec(e.get("then", {}), path, stack)
            for k, c in (s.get("properties") or {}).items():
                if c is not True:
                    rec(c, "%s.%s" % (path, key(k)) if path else key(k), stack)
            if isinstance(s.get("additionalProperties"), dict):
                rec(s["additionalProperties"], self.t("%s.<имя>", "%s.<name>") % path, stack)
            if isinstance(s.get("items"), dict):
                rec(s["items"], "%s[]" % path, stack)
        rec({k: v for k, v in w.items() if k != "$defs"}, "", ())
        if not rows:
            return []
        out = [self.t("Только у писателя (`$defs.writer`):", "Only at the writer (`$defs.writer`):"), "",
               self.t("| Ключ | Ещё и |", "| Key | Also |"), "|---|---|"]
        out += ["| `%s` | %s |" % (code_cell(p), cell(x)) for p, x in rows]
        return out + [""]


# ---------------------------------------------------------------- раздел «Форма» P/02.1

def link(norms, root, target):
    return os.path.relpath(Path(root) / target, Path(norms).parent).replace(os.sep, "/")


def build_form_section(schema_doc, relations_doc, scalars, lang="ru"):
    """Текст раздела «Форма» между маркерами FORM_BEGIN и FORM_END. scalars — (строки, пределы) v7.textv7.load_scalars;
    lang — язык блока (`en` — источник, `ru` — перевод; ADR-0121 доп. (3) п. 1)."""
    sec = SchemaSection(schema_doc, lang=lang)
    t = sec.t
    out = [t("### Форма (построена из стандартных файлов)", "### Form (built from the standard files)"), "",
           t("Форма — JSON Schema 2020-12 `02.1-installer.schema.json`, связи — CEL `02.1-installer.relations.json`, "
             "слова слоёв — `02.1-installer.layers.tsv` (ADR-0092). Класс отказа — слой, где отказ: `text` (текст, "
             "N1.1), `form` (форма), `relations` (связи — только при чистой форме). Выражение — целиком, как в схеме "
             "(ECMA-262 `u` ∩ RE2, `.` — любой знак). Целое место: границы ±(2^53 − 1), значение с целым значением — "
             "целое.",
             "The form is the JSON Schema 2020-12 `02.1-installer.schema.json`, the relations are the CEL "
             "`02.1-installer.relations.json`, the words of the layers are `02.1-installer.layers.tsv` (ADR-0092). The "
             "class of a refusal is the layer where it is refused: `text` (the text, N1.1), `form` (the form), "
             "`relations` (the relations — only on a clean form). An expression matches in full, as in the schema "
             "(ECMA-262 `u` ∩ RE2, `.` is any character). An integer place: bounds ±(2^53 − 1), a value with an "
             "integral value is an integer."), ""]
    out += sec.root_body()
    out += sec.defs_body()
    rows_sc, limits = scalars
    out += [t("#### Таблица скаляров (N1.1)", "#### Table of scalars (N1.1)"), "",
            t("Простой скаляр — по первой совпавшей строке сверху; в кавычках и блочный — строка.",
              "A plain scalar — by the first matching row from the top; a quoted or block scalar is a string."), "",
            t("| Вид | Образец (целиком) |", "| Kind | Pattern (in full) |"), "|---|---|"]
    for k, p in rows_sc:                         # textv7.load_scalars даёт скомпилированные выражения: в норме — шаблон
        pat = p.pattern if hasattr(p, "pattern") else p
        out.append("| %s | `%s` |" % (k, code_cell(pat) if pat else ""))
    out += ["", t("Пределы: целое по модулю не больше %d; дробное по модулю не больше %r; вне пределов и nonfinite — "
                  "отказ формы на пути значения.",
                  "Limits: an integer of absolute value at most %d; a fraction of absolute value at most %r; out of "
                  "the limits and nonfinite — a form refusal at the path of the value.")
            % (limits["int_max"], limits["float_max"]), ""]
    out += [t("#### Связи (N1.4)", "#### Relations (N1.4)"), "",
            t("Только при чистой форме (N3). Строка — выражение CEL файла связей; отказ — `refused:relations`, путь — "
              "место, которое выражение называет.",
              "Only on a clean form (N3). A row is a CEL expression of the relations file; the refusal is "
              "`refused:relations`, the path is the place that the expression names."), "",
            t("| № | Путь | Отношение | Норма |", "| No. | Path | Relation | Norm |"), "|---|---|---|---|"]
    for r in relations_doc["rows"]:
        implied = r.get("x-implied-by")
        more = t(" (следует из %s)", " (follows from %s)") % ", ".join(map(str, implied)) if implied else ""
        out.append("| %d | `%s` | `%s`%s | %s |" % (r["no"], code_cell(r["path"]), code_cell(r["relation"]), more, cell(r["norm"])))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- раздел «Семьи данных»

KIND_WORD = {"row": "строка", "object": "объект", "file": "файл"}
KIND_WORD_EN = {"row": "row", "object": "object", "file": "file"}
UNREADABLE = {"row": "нечитаемой строки", "object": "нечитаемого объекта", "file": "нечитаемого файла"}
UNREADABLE_EN = {"row": "an unreadable row", "object": "an unreadable object", "file": "an unreadable file"}
UNIT_EN = {"строка": "row", "поле": "field", "элемент": "element"}   # значения `unit` исходов (spec.UNITS) — словами блока
CATALOG = Path("Platform/common/data/catalog.tsv")
CODEC = Path("Platform/common/data/codec.tsv")


def build_families_section(norms, root, families, lang="ru"):
    """families — [(строка каталога, путь схемы, документ схемы, путь исходов, [spec.Outcome])]; lang — язык блока
    (`en` — источник, `ru` — перевод; ADR-0121 доп. (3) п. 1)."""
    lk = lambda t: link(norms, root, t)   # noqa: E731
    t = lambda ru, en: tr(lang, ru, en)   # noqa: E731
    kind_word = KIND_WORD_EN if lang == "en" else KIND_WORD
    files = any(row["kind"] == "file" for row, *_ in families)
    out = [t("### Семьи данных (построены из стандартных файлов)", "### Data families (built from the standard files)"),
           "",
           t("Форма строк и объектов%s, которыми глава владеет по [каталогу](%s), — JSON Schema 2020-12 семьи "
             "(ADR-0092). Экземпляр строки — `{key, row}`, объекта — `{key, object}`%s; ключ — грамматика колонки `key` "
             "каталога. Поля `row` — значения `items` после [кодека](%s): писатель проверяет схему и её "
             "`$defs.writer`, читатель — схему (слой 3 — слова `x-*` схемы). Нечитаемо — строка не раскодировалась или "
             "не прошла схему в режиме читателя; исход — по таблице исходов семьи: путь — префикс пути отказа (пустой "
             "— строка целиком), при нескольких путях отказа действует исход с наименьшим приоритетом.",
             "The form of the rows and objects%s that the chapter owns by the [catalog](%s) is the JSON Schema 2020-12 "
             "of the family (ADR-0092). An instance of a row is `{key, row}`, of an object `{key, object}`%s; the key "
             "is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after "
             "the [codec](%s): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — "
             "the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the "
             "reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path "
             "of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority "
             "applies.")
           % (t(" и файлов JSON", " and JSON files") if files else "", lk(CATALOG),
              t(", файла — `{key, file}` (текст файла UTF-8; корень схемы — его разбор, `x-encoding`)",
                ", of a file `{key, file}` (the text of the file in UTF-8; the root of the schema is its parse, "
                "`x-encoding`)") if files else "",
              lk(CODEC)), ""]
    for row, schema_path, doc, outcomes_path, outcomes in families:
        out += ["#### `%s` — %s" % (row["key"], kind_word[row["kind"]]), "",
                t("Схема — [`%s`](%s), исходы — [`%s`](%s); версия формы %s; норма — %s.",
                  "Schema — [`%s`](%s), outcomes — [`%s`](%s); form version %s; norm — %s.") % (
                    schema_path.name, lk(schema_path.resolve().relative_to(root)), outcomes_path.name,
                    lk(outcomes_path.resolve().relative_to(root)), row["version"], row["norm"]), ""]
        sec = SchemaSection(doc, family=True, lang=lang)
        out += sec.root_body(head=None)
        out += sec.writer_body()
        out += sec.defs_body(head=None)
        out += [t("Исходы %s (читатель — роль; `*` — все читатели семьи):",
                  "Outcomes of %s (the reader is a role; `*` — all readers of the family):")
                % (UNREADABLE_EN if lang == "en" else UNREADABLE)[row["kind"]], "",
                t("| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |",
                  "| Path of refusal | Reader | Outcome | Priority | Unit | Norm |"), "|---|---|---|---|---|---|"]
        for o in outcomes:
            out.append("| %s | %s | %s | %d | %s | %s |" % (
                "`%s`" % code_cell(o.path) if o.path else t("%s целиком", "the whole %s") % kind_word[row["kind"]],
                "`%s`" % o.reader if o.reader != "*" else "*", cell(o.outcome), o.priority,
                UNIT_EN.get(o.unit, o.unit) if lang == "en" else o.unit, cell(o.norm)))
        out.append("")
    return "\n".join(out)
