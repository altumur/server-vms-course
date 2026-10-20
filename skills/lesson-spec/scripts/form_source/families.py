"""Схемы семей данных (ADR-0088): семьи главы по каталогу, исходы нечитаемого, раздел «Семьи данных» норм главы-владельца
и судья экземпляра {key, row} / {key, object} с кодеком писателя и читателя.

Семья — строка каталога `Platform/common/data/catalog.tsv` с колонкой `schema` = `NN-<процесс>/data/<семья>.form.yaml`
(`dialect: data-form/1`, определения `common.<имя>` — `Platform/common/data/common.form.yaml`); рядом —
`<семья>.outcomes.tsv` (DIALECT § 9). Раздел главы — семьи, чей `owner` в каталоге — эта глава (`P/NN.K`), в порядке
каталога; текст между маркерами BEGIN и END норм главы — ровно build_families_section().
"""
import json
import math
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from .judge import Loader, canonical_paths, jcs_number, pointer
from .section import Section, cell
from .source import SourceError, load_common, load_form, read_tsv

BEGIN = "<!-- families:begin -->"
END = "<!-- families:end -->"

CATALOG = Path("Platform/common/data/catalog.tsv")
COMMON = Path("Platform/common/data/common.form.yaml")
CODEC = Path("Platform/common/data/codec.tsv")
DIALECT = Path("Platform/common/DIALECT.md")
SCHEMA_PATH = re.compile(r"([0-9]{2})-[a-z][a-z-]*/data/([^/]+)\.form\.yaml")
OUTCOME_HEADER = ["path", "outcome", "priority", "unit", "norm"]
UNITS = ("строка", "поле", "элемент")
KIND_WORD = {"row": "строка", "object": "объект", "file": "файл"}
UNREADABLE = {"row": "нечитаемой строки", "object": "нечитаемого объекта", "file": "нечитаемого файла"}
INT_MAX = 2 ** 53 - 1


# ---------------------------------------------------------------- каталог и семьи

def read_catalog(root):
    """Строки каталога словарями по заголовку (порядок файла). Проверку каталога делает check_spec."""
    rows, header = [], None
    for line in (Path(root) / CATALOG).read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if header is None:
            header = cols
            continue
        rows.append(dict(zip(header, cols)))
    return rows


def chapter_prefix(norms):
    """`spec/02.3-installer.norms.md` → `P/02.3`; `spec/02-installer.norms.md` → `P/02`."""
    m = re.fullmatch(r"([0-9]{2})(?:\.(0|[1-9][0-9]?))?-[a-z][a-z-]*\.norms\.md", Path(norms).name)
    if not m:
        raise SourceError("%s: not the norms of a Platform lesson or chapter" % norms)
    return "P/%s" % m.group(1) + (".%s" % m.group(2) if m.group(2) else "")


def schema_place(row):
    """Колонка schema строки каталога → (номер урока NN, имя семьи) или SourceError."""
    m = SCHEMA_PATH.fullmatch(row["schema"])
    if not m:
        raise SourceError("catalog %s: schema %s is not NN-<процесс>/data/<семья>.form.yaml (ADR-0088 п. 1)"
                          % (row["key"], row["schema"]))
    if row["kind"] not in KIND_WORD:
        raise SourceError("catalog %s: a schema is only for row, JSON object and JSON file (ADR-0088 доп. (1) Р2, "
                          "ADR-0083 доп. (11))" % row["key"])
    if not re.fullmatch(r"P/%s(\.(?:0|[1-9][0-9]?))?" % m.group(1), row["owner"]):
        raise SourceError("catalog %s: schema %s is not in the lesson of its owner %s" % (row["key"], row["schema"],
                                                                                     row["owner"]))
    return m.group(1), m.group(2)


class Outcome:
    """wild — {номер сегмента `*`: ключи `properties` того места} (DIALECT § 9): `*` — любое имя автора, кроме них,
    или любой элемент списка."""

    def __init__(self, no, path, outcome, priority, unit, norm, wild=None):
        self.no, self.path, self.outcome, self.priority, self.unit, self.norm = no, path, outcome, priority, unit, norm
        self.segs, self.wild = unpointer(path) if path else [], wild or {}

    def covers(self, q):
        """Путь исхода — префикс пути отказа q (JSON Pointer); `*` совпадает с одним сегментом своего места."""
        if not self.path:
            return True
        qs = unpointer(q) if q.startswith("/") else None
        if qs is None or len(qs) < len(self.segs):
            return False
        return all(qs[i] not in self.wild[i] if i in self.wild else qs[i] == s for i, s in enumerate(self.segs))


def unpointer(p):
    return [s.replace("~1", "/").replace("~0", "~") for s in p.split("/")[1:]]


def star(form, n):
    """Место сегмента `*` пути исхода: (узел значения, ключи properties) у `names`, (элемент, ∅) у `items`; при
    вариантах — первый вариант с таким местом; None — у места нет ни `names`, ни `items`."""
    t = form.deref(n)
    if t.variants:
        return next((c for c in (star(form, v) for v in t.variants) if c is not None), None)
    if t.names is not None:
        return t.names[1], frozenset(t.properties or ())
    if t.items is not None:
        return t.items, frozenset()
    return None


def place(form, p, wild=None):
    """Узел формы по пути отказа JSON Pointer (индекс списка — цифры); None — такого места нет. Сегмент `*` — любое
    имя автора или любой элемент (DIALECT § 9): только на месте `names` или `items`; wild получает ключи properties
    этого места по номеру сегмента."""
    n = form.root
    for i, s in enumerate(unpointer(p)):
        t = form.deref(n)
        if s == "*":
            hit = star(form, n)
            if hit is None:
                return None
            n, keys = hit
            if wild is not None:
                wild[i] = keys
            continue
        if t.items is not None and re.fullmatch(r"0|[1-9][0-9]*", s):
            s = "*"
        n = form.child(n, s)
        if n is None:
            return None
    return n


def load_outcomes(path, form):
    """`<семья>.outcomes.tsv` (DIALECT § 9, ADR-0088 доп. (2) С11) → [Outcome]; путь — место формы, строка целиком
    названа (доп. (1) Р7: путь без исхода записывается нынешним поведением)."""
    name = Path(path).name
    if not Path(path).is_file():
        raise SourceError("%s: no outcomes file next to the schema (ADR-0088 доп. (2) С11)" % name)
    text = Path(path).read_bytes().decode("utf-8", "replace")
    first = next((ln for ln in text.split("\n") if ln and not ln.startswith("#")), None)
    if first is None or first.split("\t") != OUTCOME_HEADER:
        raise SourceError("%s: header must be %s" % (name, "<TAB>".join(OUTCOME_HEADER)))
    out, seen = [], set()
    for no, (p, outcome, priority, unit, norm) in read_tsv(path, name, 5, OUTCOME_HEADER):
        if p in seen:
            raise SourceError("%s:%d: path %r repeated" % (name, no, p))
        seen.add(p)
        wild = {}
        if p and (not p.startswith("/") or place(form, p, wild) is None):
            if p.startswith("/") and "*" in unpointer(p):
                raise SourceError("%s:%d: path %r is not a place of the schema (segment * only at names or items)"
                                  % (name, no, p))
            raise SourceError("%s:%d: path %r is not a place of the schema" % (name, no, p))
        if not re.fullmatch(r"0|[1-9][0-9]*", priority):
            raise SourceError("%s:%d: priority must be an integer ≥ 0" % (name, no))
        if unit not in UNITS:
            raise SourceError("%s:%d: unit is one of %s" % (name, no, ", ".join(UNITS)))
        if not outcome.strip() or not norm.strip():
            raise SourceError("%s:%d: outcome and norm must be said" % (name, no))
        out.append(Outcome(no, p, outcome, int(priority), unit, norm, wild))
    if "" not in seen:
        raise SourceError("%s: no outcome for the whole row or object (empty path; ADR-0088 доп. (1) Р7)" % name)
    return out


class Family:
    def __init__(self, row, schema, outcomes_path, form, outcomes):
        self.row, self.schema, self.outcomes_path, self.form, self.outcomes = row, schema, outcomes_path, form, outcomes
        self.key, self.kind = row["key"], row["kind"]


def load_family(root, row, common=None):
    """Строка каталога со схемой → Family; SourceError — схема не строится или исходы не по форме."""
    root = Path(root)
    _, name = schema_place(row)
    schema = root / "Platform" / row["schema"]
    if not schema.is_file():
        raise SourceError("catalog %s: schema %s is not a file" % (row["key"], row["schema"]))
    if common is None:
        common = load_common(root / COMMON)
    form = load_form(schema, common)
    if form.dialect != "data-form/1":
        raise SourceError("%s: a family schema is dialect: data-form/1" % schema.name)
    t = form.deref(form.root)
    if row["kind"] == "row" and not (t.types == ["object"] and t.properties is not None):
        raise SourceError("%s: the root of a row schema is an object of properties (items)" % schema.name)
    # Файл со схемой — файл с содержимым JSON (ADR-0083 доп. (11), замок присутствия): корень схемы — разбор текста
    # файла, `encoding: json` или `jcs`; файл без JSON схемы не имеет.
    if row["kind"] == "file" and t.encoding not in ("json", "jcs"):
        raise SourceError("%s: a file schema is for JSON content: its root has encoding: json or jcs" % schema.name)
    outcomes_path = schema.with_name(name + ".outcomes.tsv")
    return Family(row, schema, outcomes_path, form, load_outcomes(outcomes_path, form))


def chapter_families(root, prefix, catalog=None, common=None):
    """Семьи главы в порядке каталога: [Family]; SourceError — первая, что не строится."""
    catalog = read_catalog(root) if catalog is None else catalog
    # `spec` — форма строки задаётся манифестом подсистемы, семьи в data/ нет (check_spec SPEC_FORMS).
    rows = [r for r in catalog if r.get("owner") == prefix and r.get("schema", "-") not in ("-", "spec")]
    if rows and common is None:
        common = load_common(Path(root) / COMMON)
    return [load_family(root, r, common) for r in rows]


# ---------------------------------------------------------------- раздел

class FamilySection(Section):
    """Таблица семьи тем же языком, что раздел формы манифеста (section.py): общие определения раскрыты на месте."""

    def __init__(self, form):
        super().__init__(SimpleNamespace(form=form, rows=[], scalars=None))
        self.own = [k for k in self.own if not k.startswith("common.") or (k in self.recursive and self.uses.get(k))]

    def expand(self, path, n, rows, rules, stack, own=False):
        """Строка значения имён автора (`names`) несёт и имя (разбор ревью стадии B 3–5, №22): у корня семьи строки
        отображения нет, и грамматика имени, отличная от простой строки, идёт в «Тип и границы» строки значения
        («имя — …; значение — …», как у вложенного отображения); своё пояснение имени (`description` узла `key`, не
        определения по ссылке) — в «Смысл» на любой глубине."""
        before = len(rows)
        super().expand(path, n, rows, rules, stack, own)
        if n.ref is not None and n.ref in self.own and not own:
            return
        t = self.f.deref(n)
        if t.names is None:
            return
        label = "%s.<имя>" % path
        at = next((i for i in range(before, len(rows)) if rows[i][0] == label), None)
        if at is None:
            return
        key = t.names[0]
        p, kind, need, owner, desc, xclass = rows[at]
        name = self.kind(key)
        if not path and name != "строка":
            kind = "имя — %s; значение — %s" % (name, kind)
        note = key.notes.get("description")          # своё пояснение имени, не определения по ссылке
        if note:
            desc = "имя: %s; %s" % (note, desc) if desc else "имя: %s" % note
        rows[at] = (p, kind, need, owner, desc, xclass)

    def body(self):
        f = self.f
        rows, rules = [], []
        self.expand("", f.root, rows, rules, (), own=True)
        root = f.deref(f.root)
        if root.rules:
            rules.insert(0, ("", root))
        out = self.table(rows) + [""]
        if rules:
            out += ["Правила:", ""] + self.rules_text(rules) + [""]
        for k in self.own:
            d = f.defs[k]
            out += ["**`%s`**%s" % (k, (" — " + cell(d.notes["description"])) if d.notes.get("description") else ""), ""]
            if d.rules_only:
                out += ["Правила (вставляются ссылкой):", ""] + ["- %s" % self.rule_text(r) for r in d.rules] + [""]
                continue
            rows, rules = [("<%s>" % k, self.kind(d), "", d.notes.get("owner") or "", "", d.notes.get("x-class") or "")], []
            if d.rules:
                rules.append(("<%s>" % k, d))
            self.expand("<%s>" % k, d, rows, rules, (k,), own=True)
            out += self.table(rows) + [""]
            if rules:
                out += ["Правила:", ""] + self.rules_text(rules) + [""]
        return out


def _link(norms, root, target):
    return os.path.relpath(Path(root) / target, Path(norms).parent).replace(os.sep, "/")


def build_families_section(norms, root, families):
    """Текст раздела между маркерами BEGIN и END норм главы `norms` (сами маркеры — в нормах)."""
    if not families:
        raise SourceError("%s: the chapter owns no family with a schema in the catalog" % Path(norms).name)
    link = lambda t: _link(norms, root, t)   # noqa: E731
    files = any(fam.kind == "file" for fam in families)
    out = ["### Семьи данных (построены из источника)", "",
           "Форма строк и объектов%s, которыми глава владеет по [каталогу](%%s), — из схем семей на [диалекте](%%s) "
           "(ADR-0088). Экземпляр строки — `{key, row}`, объекта — `{key, object}`%s; ключ — грамматика колонки `key` "
           "каталога. Поля `row` — значения `items` после [кодека](%%s): писатель пишет строго, читатель читает терпимо "
           "(DIALECT § 8). Ключ вне таблицы — отказ `key`, иной отказ — `value`. Нечитаемо — строка не раскодировалась "
           "или не прошла схему в режиме читателя; исход — по таблице исходов семьи (DIALECT § 9): путь — префикс пути "
           "отказа (пустой — строка целиком), при нескольких путях отказа действует исход с наименьшим приоритетом."
           % (" и файлов JSON" if files else "",
              ", файла — `{key, file}` (текст файла UTF-8; корень схемы — его разбор, `encoding`)" if files else "")
           % (link(CATALOG), link(DIALECT), link(CODEC)), ""]
    for fam in families:
        r = fam.row
        out += ["#### `%s` — %s" % (fam.key, KIND_WORD[fam.kind]), "",
                "Схема — [`%s`](%s), исходы — [`%s`](%s); версия формы %s; норма — %s." % (
                    fam.schema.name, link(fam.schema.relative_to(root)), fam.outcomes_path.name,
                    link(fam.outcomes_path.relative_to(root)), r["version"], r["norm"]), ""]
        out += FamilySection(fam.form).body()
        out += ["Исходы %s:" % UNREADABLE[fam.kind], "",
                "| Путь отказа | Исход | Приоритет | Единица | Норма |", "|---|---|---|---|---|"]
        for o in fam.outcomes:
            out.append("| %s | %s | %d | %s | %s |" % ("`%s`" % cell(o.path) if o.path else "%s целиком" % KIND_WORD[fam.kind],
                                                   cell(o.outcome), o.priority, o.unit, cell(o.norm)))
        out.append("")
    return "\n".join(out)


def build_for_norms(norms, root=None):
    """Раздел для норм главы: семьи — по каталогу корня (по умолчанию — корень над Platform/ норм)."""
    norms = Path(norms).resolve()
    root = Path(root).resolve() if root else norms.parents[3]
    return build_families_section(norms, root, chapter_families(root, chapter_prefix(norms)))


# ---------------------------------------------------------------- судья экземпляра (кодек + форма)

NUM = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?")
INT = re.compile(r"-?(0|[1-9][0-9]*)")
DEC = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
TIME = {"writer": re.compile(r"(0|[1-9][0-9]*)(\.[0-9]{1,3})?"), "reader": re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?")}


class CodecError(Exception):
    pass


def strict_json(text):
    """Текст JSON по грамматике значений json (codec.tsv): без NaN и бесконечностей, без повтора ключей."""
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise CodecError("json: repeated key %r" % k)
            d[k] = v
        return d

    def constant(c):
        raise CodecError("json: %s" % c)
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError as exc:
        raise CodecError("json: %s" % exc)


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
    """Кратчайшая десятичная запись без экспоненты, восстанавливающая число (codec.tsv number, писатель)."""
    s = format(Decimal(repr(float(x))), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def list_text(items):
    """Список урока 3 (codec.tsv array, писатель)."""
    if not items:
        return ""
    if any(not isinstance(e, str) or e == "" or "," in e for e in items) or items[0].startswith("["):
        return json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return ",".join(items)


class Judge(Loader):
    """Судья схемы семьи: тот же обход формы, что у загрузчика формы 2.1 (judge.Loader.node), плюс кодек строки
    (`items` → значения) и слова схем семей. mode — `writer` (строгий) или `reader` (терпимый), DIALECT § 8."""

    def __init__(self, form, mode="reader"):
        if mode not in ("writer", "reader"):
            raise ValueError(mode)
        self.form, self.rows, self.scalars, self.mode = form, [], None, mode
        self.classes = form.class_positions()
        self._decoded = set()

    # ---- кодек строки: items (строки) → значения JSON
    def decode(self, node, text):
        f, t = self.form, self.form.deref(node)
        whole = f.has_note(node, "whole")
        if t.encoding:
            v = strict_json(text)
            if t.encoding == "jcs" and self.mode == "writer" and jcs(v) != text:
                raise CodecError("jcs: the text is not canonical")
            return v
        why = "no type to decode"
        for ty in f.types_of(node):
            try:
                return self.decode_as(ty, text, whole)
            except CodecError as exc:
                why = str(exc)
        raise CodecError(why)

    def decode_as(self, ty, text, whole):
        w = self.mode == "writer"
        if ty in ("string", "any"):
            return text
        if ty == "integer":
            if w or whole:
                if not INT.fullmatch(text):
                    raise CodecError("integer: not an integer sign")
                v = int(text)
                if w and abs(v) > INT_MAX:
                    raise CodecError("integer: beyond 2^53 − 1")
                return v
            if not NUM.fullmatch(text):
                raise CodecError("integer: not a decimal number")
            try:
                d = Decimal(text)
            except InvalidOperation:
                raise CodecError("integer: not a decimal number")
            if d != d.to_integral_value():
                raise CodecError("integer: not equal to an integer")
            return int(d)
        if ty == "number":
            if not (DEC if w else NUM).fullmatch(text):
                raise CodecError("number: not a decimal record")
            x = float(text)
            if not math.isfinite(x):
                raise CodecError("number: not finite")
            if w and plain_decimal(x) != text:
                raise CodecError("number: not the shortest record")
            return int(x) if INT.fullmatch(text) else x
        if ty == "boolean":
            if text not in ("true", "false"):
                raise CodecError("boolean: not true or false")
            return text == "true"
        if ty == "time":
            if not TIME[self.mode].fullmatch(text):
                raise CodecError("time: not a %s record" % self.mode)
            return float(text)
        if ty == "array":
            if text == "":
                v = []
            elif text.startswith("["):
                v = strict_json(text)
                if not isinstance(v, list):
                    raise CodecError("array: not a JSON array")
            else:
                v = text.split(",")
            if w and list_text(v) != text:
                raise CodecError("array: not the writer's list record")
            return v
        raise CodecError("%s: no record in items without encoding" % ty)

    # ---- слова схем семей поверх обхода формы
    def node(self, n, v, p, nm, out):
        f, t = self.form, self.form.deref(n)
        if t.encoding and isinstance(v, str) and tuple(p) not in self._decoded:
            try:
                v = self.decode(n, v)
            except CodecError as exc:
                return self.fail(out, p, "value", "codec: %s" % exc)
        if t.variants is None and t.types and "time" in t.types:
            if self.is_time(v):
                return
            if t.types == ["time"]:
                return self.fail(out, p, "value", "type: expected time")
        if t.types and "integer" in t.types and isinstance(v, float) and v.is_integer():
            if self.mode == "reader" and not f.has_note(n, "whole"):
                v = int(v)                          # читатель — по значению (codec.tsv integer)
        self.limits(t, v, p, out)
        if self.mode == "writer" and t.writer is not None:
            Loader.node(self, t.writer, v, p, nm, out)
            self.limits(t.writer, v, p, out, t.properties)   # имена вне properties узла, не узла writer
        Loader.node(self, n, v, p, nm, out)

    def is_time(self, v):
        if isinstance(v, bool):
            return False
        if isinstance(v, (int, float)):
            return math.isfinite(v) and v >= 0 and (self.mode == "reader" or round(v, 3) == v)
        return isinstance(v, str) and TIME[self.mode].fullmatch(v) is not None

    def limits(self, t, v, p, out, properties=None):
        """properties — ключи узла, которому принадлежит writer: `max_items` отображения с `names` считает имена вне них."""
        if t.max_bytes is not None and isinstance(v, str) and len(v.encode("utf-8")) > t.max_bytes:
            self.fail(out, p, "value", "max_bytes")
        if t.max_items is not None:
            if isinstance(v, list) and len(v) > t.max_items:
                self.fail(out, p, "value", "max_items")
            if isinstance(v, dict) and len([k for k in v if k not in (t.properties or properties or {})]) > t.max_items:
                self.fail(out, p, "value", "max_items: names")

    def judge(self, value, kind="row"):
        """value — `row` (объект строк items), `object` (значение JSON) или `file` (байты или текст файла JSON; корень
        схемы с `encoding` его разбирает) → {verdict, paths, why}."""
        out, self._decoded = [], set()
        if kind == "row":
            value = self.decode_row(value, out)
        elif kind == "file" and isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                self.fail(out, [], "value", "file: not UTF-8")
                value = None
        if value is not None:
            self.node(self.form.root, value, [], None, out)
        paths = canonical_paths([p for _, p, _ in out])
        return {"verdict": "refused" if out else "ok", "paths": [pointer(p) for p in paths],
                "why": [w for _, _, w in out]}

    def decode_row(self, row, out):
        if not isinstance(row, dict):
            self.fail(out, [], "value", "row: not an object of items")
            return None
        t, decoded = self.form.deref(self.form.root), {}
        for k, text in row.items():
            node = (t.properties or {}).get(k) or (t.names[1] if t.names is not None else None)
            if node is None:
                decoded[k] = text                   # незнакомый ключ — отказ key обходом формы
                continue
            if not isinstance(text, str):
                self.fail(out, [k], "value", "row: an items value is a string")
                continue
            try:
                decoded[k] = self.decode(node, text)
                self._decoded.add((k,))
            except CodecError as exc:
                self.fail(out, [k], "value", "codec: %s" % exc)
        return decoded


def outcomes_for(outcomes, paths):
    """Исходы набора путей отказа (DIALECT § 9): строки, чей путь — префикс хоть одного пути отказа (`*` — любой один
    сегмент своего места, Outcome.covers); из них действуют строки с наименьшим приоритетом (в порядке файла). Нет
    отказа — нет исхода."""
    hit = [o for o in outcomes if any(o.covers(q) for q in paths)]
    if not paths or not hit:
        return []
    low = min(o.priority for o in hit)
    return [o for o in hit if o.priority == low]

