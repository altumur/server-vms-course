"""Раздел формы урока, построенный из источника (ADR-0087 п. 3, доп. (1) Р4): полная проекция — каждый узел, правила
каждого узла (и корня), таблица скаляров, отношения. Определение, на которое ссылаются один раз и не рекурсивно,
раскрыто на месте; прочие — своей таблицей в «Определениях». Текст между маркерами урока — ровно build_section().
"""
from .source import all_nodes, load_source

BEGIN = "<!-- form:begin -->"
END = "<!-- form:end -->"


def code(x):
    if x is None:
        return "`null`"
    if isinstance(x, bool):
        return "`%s`" % ("true" if x else "false")
    if x == "":
        return '`""`'
    return "`%s`" % x


def key(k):
    """Подпись ключа: пустой ключ — `""`, иначе — сам ключ (без пустого места в пути и в обратных кавычках)."""
    return '""' if k == "" else k


def key_code(k):
    return "`%s`" % key(k)


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


class Section:
    def __init__(self, src):
        self.f, self.rows, self.scalars = src.form, src.rows, src.scalars
        uses = {}
        for n in all_nodes(self.f):
            for c in self.children(n):
                if c.ref:
                    uses[c.ref] = uses.get(c.ref, 0) + 1
            for r in n.rules:
                for c in r.check.values():
                    if c.ref:
                        uses[c.ref] = uses.get(c.ref, 0) + 1
        self.uses = uses
        self.recursive = {k for k in self.f.defs if self.reaches(k, k)}
        self.own = [k for k in self.f.defs if self.f.defs[k].rules_only or uses.get(k, 0) != 1 or k in self.recursive]

    @staticmethod
    def children(n):
        return list((n.properties or {}).values()) + ([n.items] if n.items else []) + list(n.names or []) + \
            list(n.variants or [])

    def reaches(self, start, target, seen=None):
        seen = seen or set()
        stack = [self.f.defs[start]]
        while stack:
            n = stack.pop()
            for c in self.children(n) + [x for r in n.rules for x in r.check.values()]:
                if c.ref == target:
                    return True
                if c.ref and c.ref not in seen:
                    seen.add(c.ref)
                    stack.append(self.f.defs[c.ref])
                elif not c.ref:
                    stack.append(c)
        return False

    # ---- тип и границы одного узла (без раскрытия свойств — они строками ниже)
    def kind(self, n):
        s = self.kind_of(n)
        if n.notes.get("whole"):                     # схема семьи: пометка позиции (ADR-0088 доп. (2) С9)
            s += "; целый знак и у читателя (whole)"
        return s

    def kind_of(self, n):
        if n.ref is not None:
            if n.ref in self.own:
                return "по определению `%s`" % n.ref
            return self.kind(self.f.defs[n.ref])
        if n.variants is not None:
            return " или ".join("(%s)" % self.kind(v) for v in n.variants)
        parts = [self.type_word(n, t) for t in n.types or ([] if n.enum is not None else ["any"])]
        s = " или ".join(parts)
        extra = []
        if n.enum is not None:
            extra.append("одно из: " + ", ".join(code(x) for x in n.enum))
        if n.not_enum is not None:
            extra.append("не из: " + ", ".join(code(x) for x in n.not_enum))
        if n.pattern is not None:
            extra.append("целиком `%s`" % n.pattern)
        if n.not_pattern is not None:
            extra.append("не целиком `%s`" % n.not_pattern)
        for k, w in (("minimum", "≥"), ("exclusive_minimum", ">"), ("maximum", "≤")):
            if getattr(n, k) is not None:
                extra.append("%s %s" % (w, getattr(n, k)))
        extra += self.data_words(n)
        return "; ".join(([s] if s else []) + extra)

    def data_words(self, n):
        """Слова схем семей (ADR-0088 доп. (2)); у формы манифеста их нет."""
        out = []
        if n.max_bytes is not None:
            out.append("не длиннее %d байт UTF-8" % n.max_bytes)
        if n.encoding == "json":
            out.append("в `items` — текст JSON (encoding: json)")
        elif n.encoding == "jcs":
            out.append("в `items` — текст JSON, у писателя — JCS (encoding: jcs)")
        if n.writer is not None:
            w = n.writer
            ws = []
            if w.enum is not None:
                ws.append("одно из: " + ", ".join(code(x) for x in w.enum))
            if w.not_enum is not None:
                ws.append("не из: " + ", ".join(code(x) for x in w.not_enum))
            if w.pattern is not None:
                ws.append("целиком `%s`" % w.pattern)
            if w.not_pattern is not None:
                ws.append("не целиком `%s`" % w.not_pattern)
            for k, word in (("minimum", "≥"), ("exclusive_minimum", ">"), ("maximum", "≤")):
                if getattr(w, k) is not None:
                    ws.append("%s %s" % (word, getattr(w, k)))
            if w.max_bytes is not None:
                ws.append("не длиннее %d байт UTF-8" % w.max_bytes)
            if w.min_items is not None:
                ws.append("не короче %d" % w.min_items)
            if w.max_items is not None:
                ws.append("не длиннее %d" % w.max_items)
            if w.unique_items:
                ws.append("без повторов")
            out.append("только у писателя: " + ", ".join(ws))
        return out

    def type_word(self, n, t):
        if t == "array":
            s = "список"
            if n.min_items is not None:
                s += ", не короче %d" % n.min_items
            if n.max_items is not None:
                s += ", не длиннее %d" % n.max_items
            if n.unique_items:
                s += ", без повторов"
            if n.items is not None:
                s += ", элемент — %s" % self.kind(n.items)
            return s
        if t == "object":
            if n.opaque:
                return "отображение, opaque"
            s = "отображение"
            if n.properties is not None:
                s += " `{%s}`" % ", ".join(key(k) if k in n.required else key(k) + "?" for k in n.properties)
            if n.names is not None:
                s += (" и прочие" if n.properties else "") + " имена автора: имя — %s, значение — %s" % (
                    self.kind(n.names[0]), self.kind(n.names[1]))
                if n.ordered:
                    s += "; порядок автора (ordered)"
                if n.max_items is not None:
                    s += "; не больше %d имён" % n.max_items
            elif n.required and n.properties is None:
                s += "; обязательны " + ", ".join(key_code(k) for k in n.required)
            return s
        return {"string": "строка", "integer": "целое", "number": "число", "boolean": "bool", "null": "null",
                "any": "любое значение", "time": "время (P/01.1 Н0 «Время в строке»)"}[t]

    def need(self, parent, k, n):
        req = parent is not None and k in self.f.deref(parent).required
        d = self.f.has_note(n, "default")
        dt = self.f.note(n, "default_text")
        out = "обязателен" if req else "необязателен"
        if d:
            out += "; умолчание %s" % code(self.f.note(n, "default"))
        if dt:
            out += "; умолчание словами: %s" % dt
        return out

    # ---- строки таблицы и правила
    def walk(self, path, parent, key, n, rows, rules, stack=()):
        f = self.f
        rows.append((path, self.kind(n), self.need(parent, key, n), f.note(n, "owner") or "",
                     f.note(n, "description") or "", f.note(n, "x-class") or ""))
        if n.ref is not None and n.ref in self.own:
            return
        if n.ref is not None:
            if n.ref in stack:
                return
            stack = stack + (n.ref,)
        t = f.deref(n)
        if t.rules:
            rules.append((path, t))
        for i, v in enumerate(t.variants or []):
            vt = f.deref(v)
            if vt.properties or vt.names or vt.items is not None:
                self.expand("%s ⟨вариант %d⟩" % (path, i + 1), v, rows, rules, stack)
        self.expand(path, n, rows, rules, stack, own=True)

    def expand(self, path, n, rows, rules, stack, own=False):
        f = self.f
        if n.ref is not None and n.ref in self.own and not own:
            return
        t = f.deref(n)
        if not own and t.rules:
            rules.append((path, t))
        for k, c in (t.properties or {}).items():
            self.walk("%s.%s" % (path, key(k)) if path else key(k), t, k, c, rows, rules, stack)
        if t.names is not None:
            self.walk("%s.<имя>" % path, None, None, t.names[1], rows, rules, stack)
        if t.items is not None:
            self.walk("%s[]" % path, None, None, t.items, rows, rules, stack)

    def table(self, rows):
        out = ["| Ключ | Тип и границы | Обязательность | Урок | Смысл |", "|---|---|---|---|---|"]
        for p, k, need, owner, desc, xclass in rows:
            if xclass:
                desc = (desc + "; " if desc else "") + "класс отказа `%s`" % xclass
            out.append("| `%s` | %s | %s | %s | %s |" % (cell(p), cell(k), cell(need), cell(owner), cell(desc)))
        return out

    def rules_text(self, holders):
        out = []
        for path, n in holders:
            for r in n.rules:
                out.append("- `%s`: %s" % (path or "<корень>", self.rule_text(r)))
        return out

    def rule_text(self, r):
        w = r.when
        cond = []
        for k in w.get("present", []):
            cond.append("есть %s" % key_code(k))
        for k in w.get("absent", []):
            cond.append("нет %s" % key_code(k))
        for k, v in (w.get("is") or {}).items():
            cond.append("%s — %s" % (key_code(k), ", ".join(code(x) for x in v)))
        for k, v in (w.get("is_not") or {}).items():
            cond.append("%s не %s" % (key_code(k), ", ".join(code(x) for x in v)))
        if "name_pattern" in w:
            cond.append("имя целиком `%s`" % w["name_pattern"])
        if "name_not_pattern" in w:
            cond.append("имя не целиком `%s`" % w["name_not_pattern"])
        act = []
        if r.require:
            act.append("обязательны " + ", ".join(key_code(k) for k in r.require) + " (путь — недостающий ключ)")
        if r.forbid:
            act.append("запрещены " + ", ".join(key_code(k) for k in r.forbid) + " (путь — запрещённый ключ)")
        if r.one_of:
            act.append("ровно один из " + ", ".join(key_code(k) for k in r.one_of)
                       + " (нет — путь отображения; больше — путь второго по списку)")
        if r.any_of:
            act.append("хотя бы один из " + ", ".join(key_code(k) for k in r.any_of) + " (путь отображения)")
        for k, c in r.check.items():
            act.append("%s — ещё и %s" % (key_code(k), self.kind(c)))
        if r.reject:
            act.append("отказ с путём отображения: %s" % r.reject)
        if r.xclass:
            act.append("класс отказа `%s`" % r.xclass)
        return ("если " + " и ".join(cond) + ": " if cond else "") + "; ".join(act) + "."

    def build(self):
        f = self.f
        out = ["### Форма (построена из источника)", "",
               "Ключ вне таблицы — `refused:key`; отказ значения — `refused:value`; класс отказа места с пометкой — его "
               "класс (по ближайшему месту на пути): "
               + (", ".join("`%s` — `%s`" % (".".join(p) or "<корень>", c) for p, c in reversed(f.class_positions()))
                  or "нет") + ".", ""]
        rows, rules = [], []
        self.expand("", f.root, rows, rules, (), own=True)
        root = f.deref(f.root)
        if root.rules:
            rules.insert(0, ("", root))
        out += ["#### Корень", ""] + self.table(rows) + [""]
        if rules:
            out += ["Правила:", ""] + self.rules_text(rules) + [""]
        if self.own:
            out += ["#### Определения", ""]
            for k in self.own:
                d = f.defs[k]
                out += ["**`%s`**%s" % (k, (" — " + cell(d.notes["description"])) if d.notes.get("description") else ""), ""]
                if d.rules_only:
                    out += ["Правила (вставляются ссылкой):", ""] + ["- %s" % self.rule_text(r) for r in d.rules] + [""]
                    continue
                rows, rules = [], []
                rows.append(("<%s>" % k, self.kind(d), "", d.notes.get("owner") or "", "", d.notes.get("x-class") or ""))
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
        rows_sc, limits = self.scalars
        out += ["#### Таблица скаляров (Н1.1)", "", "Простой скаляр — по первой совпавшей строке сверху; в кавычках и "
                "блочный — строка.", "", "| Вид | Образец (целиком) |", "|---|---|"]
        out += ["| %s | `%s` |" % (k, cell(p) if p else "") for k, p in rows_sc]
        # Класс — как у отказа значения: x-class ближайшего места с пометкой на пути, иначе value (свод Ф1, judge).
        out += ["", "Пределы: целое по модулю не больше %d; дробное по модулю не больше %r; вне пределов и nonfinite — "
                "отказ на пути значения, где бы ни остановился обход; класс — места с пометкой, ближайшего на пути "
                "(перечень в начале раздела), иначе `refused:value`." % (limits["int_max"], limits["float_max"]), ""]
        out += ["#### Ссылки и отношения (Н1.4)", "", "Только при чистой форме (Н3: значения раньше ссылок).", "",
                "| № | Путь | Отношение | Класс | Норма |", "|---|---|---|---|---|"]
        for r in self.rows:
            out.append("| %d | `%s` | `%s` | %s | %s |" % (r.no, cell(r.path_text), cell(r.text), r.cls, cell(r.norm)))
        return "\n".join(out) + "\n"


def build_section(form, references, scalars):
    """Текст раздела урока между маркерами BEGIN и END (сами маркеры — в уроке)."""
    return Section(load_source(form, references, scalars)).build()
