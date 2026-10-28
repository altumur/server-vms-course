"""Проверки `check_spec` на стандартных файлах В7 (PLAN-TRANSITION п. 1.3): семьи каталога, исходы по местам схемы,
самодостаточность схем, переносимость `pattern`, корпус P/02.1 и связи CEL, пакет `family-read`.

Режим выбирается файлами: у главы есть `<база>.schema.json` — проверка В7, иначе — диалект (`form_source`). Ошибки —
SpecError с сообщением; check_spec называет файл.
"""
import json
import re
from pathlib import Path

from v7 import regex

CATALOG = Path("Platform/common/data/catalog.tsv")
SCHEMA_PATH = re.compile(r"([0-9]{2})-[a-z][a-z-]*/data/([^/]+)\.schema\.json")
OUTCOME_HEADER = ["path", "reader", "outcome", "priority", "unit", "norm"]
# Читатель строки исходов (решение владельца 2026-10-28): роль по грамматике `readers` каталога; у пути "" — строка на
# каждого читателя семьи, `*` нельзя; у полей `*` — все читатели. Читатели семьи — `readers` ∪ писатели с `cas`/`guard`.
READER = re.compile(r"(?:console|resource|domainagent|domainconsole|domain|admin|configstore-door|"
                    r"<s>(?:controller|worker|domain)|proc:[0-9]{2}-[a-z][a-z-]*)")
UNITS = ("строка", "поле", "элемент")
KINDS = ("row", "object", "file")


class SpecError(Exception):
    pass


def read_catalog(root):
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


def is_v7_family(row):
    return row.get("schema", "").endswith(".schema.json")


# ---------------------------------------------------------------- схема: самодостаточность, места

def refs(doc):
    """Все значения `$ref` документа."""
    out = []

    def rec(x):
        if isinstance(x, dict):
            if isinstance(x.get("$ref"), str):
                out.append(x["$ref"])
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    rec(doc)
    return out


def self_contained(doc):
    """Ошибки: `$ref` вне файла или на место, которого нет (решение «Архитектора» 2026-10-27: схема самодостаточна)."""
    bad = []
    for r in refs(doc):
        if not r.startswith("#/"):
            bad.append("$ref %s points outside the file: a schema holds copies of what it needs in $defs" % r)
            continue
        at = doc
        for seg in r[2:].split("/"):
            seg = seg.replace("~1", "/").replace("~0", "~")
            if not isinstance(at, dict) or seg not in at:
                bad.append("$ref %s names no place of the file" % r)
                break
            at = at[seg]
    return bad


def unpointer(p):
    return [s.replace("~1", "/").replace("~0", "~") for s in p.split("/")[1:]]


class Places:
    """Места схемы по пути JSON Pointer (индекс списка — цифры; `*` — любое имя автора или любой элемент)."""

    def __init__(self, doc):
        self.doc = doc

    def resolve(self, s, seen=()):
        """[схема] места: само место, цель `$ref` и ветви `allOf`/`then` (варианты, правила по имени)."""
        out = []
        if not isinstance(s, dict):
            return out
        out.append(s)
        r = s.get("$ref")
        if isinstance(r, str) and r.startswith("#/") and r not in seen:
            at = self.doc
            for seg in r[2:].split("/"):
                at = at.get(seg.replace("~1", "/").replace("~0", "~"), {}) if isinstance(at, dict) else {}
            out += self.resolve(at, seen + (r,))
        for e in s.get("allOf", []):
            if isinstance(e, dict):
                out += self.resolve(e.get("then", {}) if "if" in e else e, seen)
        return out

    def child(self, chain, seg, wild, i):
        if any(s.get("x-opaque") for s in chain):          # отображение без проверки ключей: любое имя — место
            return [{}]
        if seg == "*":
            for s in chain:
                ap = s.get("additionalProperties")
                if isinstance(ap, dict) or ap is True:
                    if wild is not None:
                        wild[i] = frozenset(s.get("properties") or ())
                    return self.resolve(ap if isinstance(ap, dict) else {})
            for s in chain:
                if isinstance(s.get("items"), dict):
                    if wild is not None:
                        wild[i] = frozenset()
                    return self.resolve(s["items"])
            return None
        for s in chain:
            if seg in (s.get("properties") or {}):
                return self.resolve(s["properties"][seg])
        if re.fullmatch(r"0|[1-9][0-9]*", seg):
            for s in chain:
                if isinstance(s.get("items"), dict):
                    return self.resolve(s["items"])
        for s in chain:
            for pat, ps in (s.get("patternProperties") or {}).items():
                if regex.search(pat, seg):
                    return self.resolve(ps)
            ap = s.get("additionalProperties")
            if isinstance(ap, dict) or ap is True:
                return self.resolve(ap if isinstance(ap, dict) else {})
        return None

    def place(self, p, wild=None):
        """Место по пути исхода (пустой путь — корень); None — такого места нет."""
        chain = self.resolve(self.doc)
        for i, seg in enumerate(unpointer(p) if p else []):
            chain = self.child(chain, seg, wild, i)
            if not chain:
                return None
        return chain


# ---------------------------------------------------------------- семьи

def tsv_rows(path, width, header):
    out = []
    for no, line in enumerate(Path(path).read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if cols == header:
            continue
        if len(cols) != width:
            raise SpecError("%s:%d: expected %d TSV columns, got %d" % (Path(path).name, no, width, len(cols)))
        out.append((no, cols))
    return out


class Outcome:
    """Строка исходов: wild — {номер сегмента `*`: ключи `properties` того места}: `*` — любое имя автора, кроме них,
    или любой элемент списка."""

    def __init__(self, path, reader, outcome, priority, unit, norm, wild=None):
        self.path, self.reader, self.outcome, self.priority, self.unit, self.norm = (path, reader, outcome, priority,
                                                                                     unit, norm)
        self.segs, self.wild = unpointer(path) if path else [], wild or {}

    def covers(self, q):
        """Путь исхода — префикс пути отказа q (JSON Pointer); `*` совпадает с одним сегментом своего места."""
        if not self.path:
            return True
        qs = unpointer(q) if q.startswith("/") else None
        if qs is None or len(qs) < len(self.segs):
            return False
        return all(qs[i] not in self.wild[i] if i in self.wild else qs[i] == s for i, s in enumerate(self.segs))


def outcomes_for(outcomes, paths, reader=None):
    """Исходы набора путей отказа у читателя reader (строки с его ролью и `*`; None — все строки): у каждого пути —
    строки, чей путь его префикс; если глубже всех из них строка с единицей `поле` или `элемент`, действует только она
    (и равные ей по глубине), иначе — все; из строк всех путей действуют строки с наименьшим приоритетом (в порядке
    файла). Нет отказа — нет исхода."""
    if reader is not None:
        outcomes = [o for o in outcomes if o.reader in (reader, "*")]
    keep = set()
    for q in paths:
        cov = [o for o in outcomes if o.covers(q)]
        deep = max((len(o.segs) for o in cov), default=0)
        top = [o for o in cov if len(o.segs) == deep]
        keep.update(id(o) for o in (top if any(o.unit != "строка" for o in top) else cov))
    hit = [o for o in outcomes if id(o) in keep]
    if not paths or not hit:
        return []
    low = min(o.priority for o in hit)
    return [o for o in hit if o.priority == low]


def load_outcomes(path, doc):
    """`<семья>.outcomes.tsv` → [Outcome]: путь — место схемы, (путь, читатель) не повторяется, у пустого пути читатель
    — роль (не `*`), пустой путь есть."""
    name = Path(path).name
    if not Path(path).is_file():
        raise SpecError("%s: no outcomes file next to the schema (ADR-0088 доп. (2) С11)" % name)
    text = Path(path).read_bytes().decode("utf-8", "replace")
    first = next((ln for ln in text.split("\n") if ln and not ln.startswith("#")), None)
    if first is None or first.split("\t") != OUTCOME_HEADER:
        raise SpecError("%s: header must be %s" % (name, "<TAB>".join(OUTCOME_HEADER)))
    places, out, seen = Places(doc), [], set()
    for no, (p, reader, outcome, priority, unit, norm) in tsv_rows(path, 6, OUTCOME_HEADER):
        if (p, reader) in seen:
            raise SpecError("%s:%d: path %r with reader %r repeated" % (name, no, p, reader))
        seen.add((p, reader))
        if not (READER.fullmatch(reader) or (reader == "*" and p)):
            raise SpecError("%s:%d: reader is a role of the catalog grammar%s" % (
                name, no, "; the whole row (empty path) is named for each reader, not *" if not p else " or *"))
        wild = {}
        if p and (not p.startswith("/") or places.place(p, wild) is None):
            raise SpecError("%s:%d: path %r is not a place of the schema%s" % (
                name, no, p, " (segment * only at names or items)" if "*" in p.split("/") else ""))
        if not re.fullmatch(r"0|[1-9][0-9]*", priority):
            raise SpecError("%s:%d: priority must be an integer ≥ 0" % (name, no))
        if unit not in UNITS:
            raise SpecError("%s:%d: unit is one of %s" % (name, no, ", ".join(UNITS)))
        if not outcome.strip() or not norm.strip():
            raise SpecError("%s:%d: outcome and norm must be said" % (name, no))
        out.append(Outcome(p, reader, outcome, int(priority), unit, norm, wild))
    if not any(p == "" for p, _ in seen):
        raise SpecError("%s: no outcome for the whole row or object (empty path; ADR-0088 доп. (1) Р7)" % name)
    return out


def check_schema(doc, name):
    """Схема — JSON Schema 2020-12 (метасхема), самодостаточна, выражения переносимы."""
    import jsonschema
    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except jsonschema.SchemaError as exc:
        raise SpecError("%s: not a JSON Schema 2020-12: %s" % (name, str(exc).split("\n")[0]))
    bad = self_contained(doc)
    if bad:
        raise SpecError("%s: %s" % (name, bad[0]))
    bad = unportable(doc)
    if bad:
        raise SpecError("%s: %s" % (name, bad[0]))


def load_family(root, row):
    """Строка каталога со схемой `.schema.json` → (row, путь схемы, схема, путь исходов, [исход])."""
    m = SCHEMA_PATH.fullmatch(row["schema"])
    if not m:
        raise SpecError("catalog %s: schema %s is not NN-<процесс>/data/<имя>.schema.json" % (row["key"], row["schema"]))
    if row["kind"] not in KINDS:
        raise SpecError("catalog %s: a schema is only for row, JSON object and JSON file" % row["key"])
    if not re.fullmatch(r"P/%s(\.(?:0|[1-9][0-9]?))?" % m.group(1), row["owner"]):
        raise SpecError("catalog %s: schema %s is not in the lesson of its owner %s" % (row["key"], row["schema"],
                                                                                   row["owner"]))
    path = Path(root) / "Platform" / row["schema"]
    if not path.is_file():
        raise SpecError("catalog %s: schema %s is not a file" % (row["key"], row["schema"]))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SpecError("%s: not JSON: %s" % (path.name, exc))
    check_schema(doc, path.name)
    layers = path.with_name(path.name[:-len(".schema.json")] + ".layers.tsv")
    from v7 import schema as gen
    if not layers.is_file() or layers.read_text(encoding="utf-8") != gen.layer_table(doc):
        raise SpecError("%s: is not the table of the x-* words of %s (rebuild: python -m v7.layers Platform/%s)"
                        % (layers.name, path.name, row["schema"]))
    root_s = Places(doc).resolve(doc)
    if row["kind"] == "row" and not any("properties" in s for s in root_s):
        raise SpecError("%s: the root of a row schema is an object of properties (items)" % path.name)
    if row["kind"] == "file" and not any(s.get("x-encoding") in ("json", "jcs") for s in root_s):
        raise SpecError("%s: a file schema is for JSON content: its root has x-encoding json or jcs" % path.name)
    name = path.name[:-len(".schema.json")]
    if row["kind"] != "file" and name.endswith("." + row["kind"]):
        name = name[:-len(row["kind"]) - 1]
    outcomes_path = path.with_name(name + ".outcomes.tsv")
    return row, path, doc, outcomes_path, load_outcomes(outcomes_path, doc)


# ---------------------------------------------------------------- переносимость выражений (ADR-0092 п. 14)

def patterns(doc):
    """[(место, выражение)]: `pattern` и ключи `patternProperties`."""
    out = []

    def rec(x, p):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "pattern" and isinstance(v, str):
                    out.append((p + "/pattern", v))
                if k == "patternProperties" and isinstance(v, dict):
                    out.extend((p + "/patternProperties", pat) for pat in v)
                rec(v, p + "/" + k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                rec(v, "%s/%d" % (p, i))
    rec(doc, "")
    return out


def unportable(doc):
    """Выражения вне ECMA-262 `u` ∩ RE2 (ADR-0092 п. 14): синтаксис переносимого подмножества (regex.check) и компиляция
    Python. Подмножество выбрано так, что его смысл у ECMA-262 `u`, RE2 и Python (`regex.search`, ASCII-смысл) один;
    компиляции в RE2 и ECMA здесь нет — её держат тесты стека (Go `v7check`) и набор А на двух языках."""
    bad = []
    for where, p in patterns(doc):
        why = regex.check(p)
        if why:
            bad.append("pattern at %s: %s" % (where or "#", why))
    return bad


# ---------------------------------------------------------------- пакет family-read

FAMILY_READ = Path("Platform/common/vectors/family-read")
FR_HEADER = ["case", "family", "kind", "mode", "who", "text", "verdict", "paths", "outcome", "note"]


def who_of(row, mode):
    """«Кто исполняет» по каталогу: писатель — роли операций `ops`, читатель — `readers`."""
    s = re.sub(r"\([^()]*\)", "", row["ops"] if mode == "writer" else row["readers"])
    if mode != "writer":
        return [r for r in s.split(", ") if r]
    out = []
    for part in s.split("; "):
        for r in part.partition("=")[2].split(", "):
            if r and r not in out:
                out.append(r)
    return out


def family_read(root, catalog, judge=True):
    """Проверка пакета: README, таблица `NN.tsv` на урок-владельца, строка по форме, семья и `who` — по каталогу, каждая
    семья урока — в своей таблице; judge — исход строки равен исходу стека В7 (Python). → (ошибки [(путь, сообщение)],
    счёты)."""
    import json as _json
    errors, stats = [], {"family_read_rows": 0, "family_read_tables": 0}
    d = Path(root) / FAMILY_READ
    if not d.is_dir():
        stats["family_read"] = "absent"
        return errors, stats
    stats["family_read"] = "present"
    if not (d / "README.md").is_file():
        errors.append((FAMILY_READ, "family-read: the package needs README.md (the format)"))
    by_key = {(r["key"], r["kind"]): r for r in catalog if is_v7_family(r)}       # ключ каталога — пара (key, kind)
    fams = {}
    for p in sorted(d.iterdir()):
        if p.name in ("README.md", ".DS_Store"):
            continue
        m = re.fullmatch(r"([0-9]{2})\.tsv", p.name)
        if not m:
            errors.append((FAMILY_READ / p.name, "family-read: only README.md and NN.tsv (one table per owner lesson)"))
            continue
        lesson = m.group(1)
        stats["family_read_tables"] += 1
        lines = [ln for ln in p.read_text(encoding="utf-8").split("\n") if ln]
        if not lines or lines[0].split("\t") != FR_HEADER:
            errors.append((FAMILY_READ / p.name, "family-read: header must be %s" % "<TAB>".join(FR_HEADER)))
            continue
        seen, covered = set(), set()
        for no, ln in enumerate(lines[1:], 2):
            where = FAMILY_READ / p.name
            cols = ln.split("\t")
            if len(cols) != len(FR_HEADER):
                errors.append((where, "line %d: expected %d TSV columns" % (no, len(FR_HEADER))))
                continue
            case, key, kind, mode, who, text, verdict, paths, outcome, _note = cols
            if case in seen or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", case):
                errors.append((where, "line %d: case %r is not unique or not [A-Za-z0-9][A-Za-z0-9_.-]*" % (no, case)))
            seen.add(case)
            row = by_key.get((key, kind))
            if row is None:
                errors.append((where, "line %d: %s (%s) is not a family of the catalog with a schema" % (no, key, kind)))
                continue
            if row["owner"][2:4] != lesson:
                errors.append((where, "line %d: %s belongs to the table of %s" % (no, key, row["owner"][2:4])))
            covered.add((key, kind))
            if mode not in ("writer", "reader"):
                errors.append((where, "line %d: mode is writer or reader" % no))
                continue
            want = who_of(row, mode) if mode == "writer" else family_readers(root, row, fams)
            try:
                got_who = _json.loads(who)
            except ValueError:
                got_who = None
            if got_who != want:
                errors.append((where, "line %d: who — JSON array of roles by the catalog and the outcomes (%s)"
                               % (no, _json.dumps(want, ensure_ascii=False))))
                continue
            try:
                ps, outs = _json.loads(paths), _json.loads(outcome)
            except ValueError:
                errors.append((where, "line %d: paths and outcome are JSON arrays" % no))
                continue
            if verdict not in ("ok", "refused") or not isinstance(ps, list) \
                    or (verdict == "ok") != (not ps) or (mode == "writer" and outs != []) \
                    or (mode == "reader" and not (isinstance(outs, dict)
                                                  and all(isinstance(v, list) for v in outs.values()))):
                errors.append((where, "line %d: verdict ok has no paths, refused has; a writer has outcome [], a reader "
                                      "— {role: [paths of outcome rows]}" % no))
                continue
            stats["family_read_rows"] += 1
            if judge:
                why = judge_row(root, row, kind, mode, text, ps, outs, fams)
                if why:
                    errors.append((where, "line %d (%s): %s" % (no, case, why)))
        for k, row in sorted(by_key.items()):
            if row["owner"][2:4] == lesson and k not in covered:
                errors.append((FAMILY_READ / p.name, "family-read: no row reads the family %s (%s)" % k))
    return errors, stats


def readers_of(outcomes):
    """Читатели, названные строками пустого пути, в порядке файла."""
    out = []
    for o in outcomes:
        if o.path == "" and o.reader not in out:
            out.append(o.reader)
    return out


def family_readers(root, row, cache):
    k = (row["key"], row["kind"])
    if k not in cache:
        from v7 import stack
        _, _, doc, _, outcomes = load_family(root, row)
        cache[k] = (stack.Family(doc, row["kind"]), outcomes)
    return readers_of(cache[k][1])


def reading_roles(row, star=None):
    """Читатели семьи по каталогу (решение владельца 2026-10-28): `readers` (у `*` — star: роли глав, чей абзац
    «Данные» читает ключ) ∪ роли операций `cas` и `guard` (они читают строку перед записью). row — строка каталога
    check_spec (`reader_roles`, `ops` разобраны). → множество ролей или None (`*` без star)."""
    roles = set(row["reader_roles"]) if row["reader_roles"] is not None else (set(star) if star is not None else None)
    if roles is None:
        return None
    for op in ("cas", "guard"):
        roles |= set(row["ops"].get(op, ()))
    return roles


def judge_row(root, row, kind, mode, text, paths, outs, cache):
    """Исход строки на стеке В7 (Python) против ожидания; → причина расхождения или None."""
    import json as _json

    from v7 import stack
    k = (row["key"], row["kind"])
    if k not in cache:
        _, _, doc, _, outcomes = load_family(root, row)
        cache[k] = (stack.Family(doc, kind), outcomes)
    fam, outcomes = cache[k]
    if kind == "row":
        try:
            value = _json.loads(text)
        except ValueError:
            value = text
    elif kind == "file":
        value = text.encode("utf-8")
    else:
        value = text
    v = fam.judge(value, mode)
    got = ({r: [o.path for o in outcomes_for(outcomes, v["paths"], r)] for r in readers_of(outcomes)}
           if mode == "reader" else [])
    if v["verdict"] != ("refused" if paths else "ok") or sorted(v["paths"]) != sorted(paths) or got != outs:
        return "expected %s %s %s, the V7 stack gives %s %s %s" % ("refused" if paths else "ok", paths, outs,
                                                                v["verdict"], v["paths"], got)
    return None


# ---------------------------------------------------------------- файл связей: формат и пути строк (ревью Codex RВ7-02)

RELATION_FIELDS = {"no": int, "path": str, "relation": str, "class": str, "norm": str, "cel": str, "own": list}
RELATION_CLASSES = ("reference", "value")


def row_place(path):
    """Путь строки связей (грамматика пути диалекта: сегменты через `.` на верхнем уровне скобок; `*`, `{}` — имя автора,
    `{…}` — динамика, `$x` — переменная, `key[]`, `key[$x]` — элемент) → JSON Pointer места формы (`*` — любое имя или
    элемент); None — не по грамматике."""
    parts, depth, cur, q = [], 0, "", False
    for c in path:
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
        if s == "*" or (s.startswith("{") and s.endswith("}")) or re.fullmatch(r"\$[a-z]+", s):
            segs.append("*")
            continue
        m = re.fullmatch(r"([a-z_][a-z0-9_]*)(\[\]|\[\$[a-z]+\])?", s)
        if not m:
            return None
        segs.append(m.group(1))
        if m.group(2):
            segs.append("*")
    return "/" + "/".join(segs)


def relations_errors(rel, schema_doc):
    """Формат `.relations.json` и место пути каждой строки в форме. CEL исполняется слоем связей; проза `relation` —
    документ строки, её смысл с CEL не сверяется (сверяет корпус: строка держит случаи)."""
    out = []
    if not isinstance(rel, dict) or set(rel) != {"env", "rows", "untranslated"}:
        return ["relations: top level is {env, rows, untranslated}"]
    if rel["untranslated"]:
        out.append("relations: untranslated rows %s" % [r.get("no") for r in rel["untranslated"]])
    env = rel["env"]
    if not (isinstance(env, dict) and isinstance(env.get("name"), str) and isinstance(env.get("extensions"), list)
            and isinstance(env.get("variables"), list) and isinstance(env.get("functions"), list)):
        out.append("relations: env is {name, extensions, variables, functions} of the CEL environment")
    if not isinstance(rel["rows"], list) or not rel["rows"]:
        return out + ["relations: rows is a non-empty list"]
    places, seen = Places(schema_doc), set()
    for i, r in enumerate(rel["rows"]):
        where = "relations: row %s" % (r.get("no", "#%d" % i) if isinstance(r, dict) else "#%d" % i)
        if not isinstance(r, dict):
            out.append(where + ": not an object")
            continue
        extra, missing = set(r) - set(RELATION_FIELDS) - {"x-implied-by"}, set(RELATION_FIELDS) - set(r)
        if extra or missing:
            out.append("%s: fields %s (unknown %s, missing %s)" % (where, sorted(RELATION_FIELDS), sorted(extra),
                                                                 sorted(missing)))
            continue
        bad = [k for k, ty in RELATION_FIELDS.items() if type(r[k]) is not ty or (ty is str and not r[k].strip())]
        if bad:
            out.append("%s: %s of the wrong type or empty" % (where, ", ".join(bad)))
            continue
        if r["no"] in seen:
            out.append(where + ": repeated no")
        seen.add(r["no"])
        if r["class"] not in RELATION_CLASSES:
            out.append("%s: class %r is not one of %s" % (where, r["class"], ", ".join(RELATION_CLASSES)))
        ptr = row_place(r["path"])
        if ptr is None:
            out.append("%s: path %r is not a path of a relation row" % (where, r["path"]))
        elif not places.place(ptr):
            out.append("%s: path %s is not a place of the form (ADR-0087 доп. (1) Р2)" % (where, r["path"]))
    return out


# ---------------------------------------------------------------- корпус P/02.1 и связи (форма манифеста)

def manifest_check(root, norms, text, base, acceptance, verdicts, classes, manifests, strict=False, implied=None):
    """Глава со стандартными файлами формы манифеста: файлы годны, раздел «Форма» между маркерами — построенный,
    корпус — вердикт и класс (слой) строго, пути `diagnostics.tsv` — сведение (ADR-0092 п. 5), манифесты курса
    принимаются, строки связей держат случаи (строка — единственная причина отказа хоть одного случая; строго — со
    strict). implied — значения реестра исключений вида `implied` — «номер:путь» строки связей, чью пометку
    `x-implied-by` разрешило решение (перенумерация или иное выражение под тем же номером — красное, повторное ревью
    Claude М-1); None — без реестра (тесты). → (ошибки, счёты; `implied_marked` — «номер:путь» помеченных строк)."""
    from v7 import schema as gen
    from v7 import section, stack, textv7
    errors, stats = [], {"form_cases": 0, "form_manifests": 0, "form_rows": 0, "form_rows_held": 0,
                         "form_diagnostics_differ": 0}
    base = Path(base)
    files = {s: Path(str(base) + s) for s in (".schema.json", ".relations.json", ".scalars.tsv", ".layers.tsv")}
    for s, p in files.items():
        if not p.is_file():
            errors.append((p, "standard files of the form: %s is missing (ADR-0092)" % p.name))
    if errors:
        return errors, stats
    try:
        sch = json.loads(files[".schema.json"].read_text(encoding="utf-8"))
        rel = json.loads(files[".relations.json"].read_text(encoding="utf-8"))
        check_schema(sch, files[".schema.json"].name)
    except (ValueError, SpecError) as exc:
        return [(files[".schema.json"], "form: %s" % exc)], stats
    if files[".layers.tsv"].read_text(encoding="utf-8") != gen.layer_table(sch):
        errors.append((files[".layers.tsv"], "is not the table of the x-* words of the schema (rebuild: cd "
                                             "skills/lesson-spec/scripts && python -m v7.layers %s)"
                       % files[".schema.json"].relative_to(root)))
    bad = relations_errors(rel, sch)
    if bad:
        return errors + [(files[".relations.json"], why) for why in bad], stats
    textv7.use_scalars(files[".scalars.tsv"])
    try:
        loader = stack.Manifest(sch, rel)
    except Exception as exc:                                # noqa: BLE001 — выражение CEL не строится
        return errors + [(files[".relations.json"], "relations: %s" % exc)], stats
    if text is not None:
        lines = text.split("\n")
        b = [i for i, ln in enumerate(lines) if ln == section.FORM_BEGIN]
        e = [i for i, ln in enumerate(lines) if ln == section.FORM_END]
        if len(b) != 1 or len(e) != 1 or e[0] < b[0]:
            errors.append((norms, "form: the norms hold the built section once, between %s and %s"
                           % (section.FORM_BEGIN, section.FORM_END)))
        else:
            said = "\n".join(lines[b[0] + 1:e[0]]) + "\n"
            built = section.build_form_section(sch, rel, textv7.load_scalars(files[".scalars.tsv"]))
            if said != built:
                old, new = said.splitlines(), built.splitlines()
                at = next((i for i, (x, y) in enumerate(zip(old, new)) if x != y), min(len(old), len(new)))
                errors.append((norms, "form: the section differs from the built one at its line %d (rebuild: python "
                                      "skills/lesson-spec/scripts/v7/sections.py %s)" % (at + 1, norms.relative_to(root))))
    if verdicts is None:
        errors.append((files[".schema.json"], "form without verdicts.tsv: nothing to check it against"))
        return errors, stats
    diagnostics = {}
    if (acceptance / "diagnostics.tsv").is_file():
        for ln in (acceptance / "diagnostics.tsv").read_text(encoding="utf-8").split("\n"):
            cols = ln.split("\t")
            if len(cols) == 3 and not ln.startswith("#") and cols[0] != "case":
                try:
                    diagnostics[cols[0]] = json.loads(cols[1])
                except ValueError:
                    pass
    held, fired_sets = set(), []
    for case, expected in sorted(verdicts.items()):
        path = acceptance / "cases" / ("%s.subsystem.yaml" % case)
        try:
            got = loader.judge(path.read_bytes())
        except OSError:
            continue
        except Exception as exc:                            # noqa: BLE001
            errors.append((path, "form: loader failed: %r" % exc))
            continue
        stats["form_cases"] += 1
        why = "layer %s, paths %s" % (got["layer"], json.dumps(got["paths"], ensure_ascii=False)[:200])
        if got["verdict"] != expected:
            errors.append((path, "form: verdict expected %s, got %s (%s)" % (expected, got["verdict"], why)))
        elif case in classes and got["layer"] != classes[case]:
            errors.append((path, "form: class expected %s, got %s (%s)" % (classes[case], got["layer"], why)))
        elif case in diagnostics and sorted(map(json.dumps, diagnostics[case])) != sorted(map(json.dumps, got["paths"])):
            stats["form_diagnostics_differ"] += 1             # подсказка, не норма (ADR-0092 п. 5)
        if got.get("layer") == "relations":
            fired_sets.append(frozenset(got.get("rows", [])))
            if len(got.get("rows", [])) == 1:
                held.add(got["rows"][0])
    for path in sorted(manifests):
        got = loader.judge(path.read_bytes())
        if got["verdict"] != "ok":
            errors.append((path, "form: course manifest refused %s (paths %s)" % (got["layer"], got["paths"])))
        stats["form_manifests"] += 1
    stats["form_rows"] = len(rel["rows"])
    stats["form_rows_held"] = len({r["no"] for r in rel["rows"]} & held)
    nos = {r["no"] for r in rel["rows"]}
    marked = set()
    for r in rel["rows"]:
        by = r.get("x-implied-by")
        if by is None:
            continue
        tag = "%d:%s" % (r["no"], r["path"])
        marked.add(tag)
        where = files[".relations.json"]
        if not (isinstance(by, list) and by and all(i in nos and i != r["no"] for i in by)):
            errors.append((where, "row %d: x-implied-by names other rows of the file" % r["no"]))
            continue
        if implied is not None and tag not in implied:
            errors.append((where, "row %s: x-implied-by without the exception implied %s of the registry (a decision "
                                  "of the «Архитектор»)" % (tag, tag)))
        group = {r["no"], *by}
        # групповая мутация (решение «Архитектора» 2026-10-28): снятие строки вместе с теми, из которых она следует,
        # меняет вердикт случая, а строка одна при снятых тех этот вердикт держит — случай, где сработали только строки
        # группы и среди них она; и импликация по корпусу (ревью Claude С-4): где сработала строка, сработала и строка
        # пометки. Красное и без --strict-coverage.
        if any(r["no"] in f and f <= group for f in fired_sets):
            stats["form_rows_implied"] = stats.get("form_rows_implied", 0) + 1
            held.add(r["no"])
        else:
            errors.append((where, "row %d: x-implied-by %s — no corpus case where only rows of the group fire and this "
                                  "row among them (the group mutation)" % (r["no"], by)))
        alone = [f for f in fired_sets if r["no"] in f and not f & set(by)]
        if alone:
            errors.append((where, "row %d: x-implied-by %s — %d corpus case(s) fire this row without any row it is "
                                  "implied by" % (r["no"], by, len(alone))))
    stats["implied_marked"] = marked
    if strict:
        for r in rel["rows"]:
            if r["no"] not in held and r.get("x-implied-by") is None:
                errors.append((files[".relations.json"], "row %d: no corpus case has this row as its sole cause "
                                                         "(ADR-0087 доп. (1) Р10)" % r["no"]))
    return errors, stats


def families_check(root, norms, text, prefix, catalog):
    """Семьи главы-владельца со схемами `.schema.json`: схема, слои и исходы годны; раздел между маркерами —
    построенный. → (ошибки, счёты)."""
    from v7 import section
    errors, stats = [], {"family_schemas": 0, "family_outcomes": 0, "families_with_section": 0,
                         "families_without_section": 0}
    rows = [r for r in catalog if r["owner"] == prefix and is_v7_family(r)]
    lines = text.split("\n") if text is not None else []
    marks = section.FAMILIES_BEGIN, section.FAMILIES_END
    if not rows and not any(ln in marks for ln in lines):
        return errors, stats
    built = []
    for r in rows:
        try:
            built.append(load_family(root, r))
        except (SpecError, OSError) as exc:
            errors.append((Path(root) / "Platform" / r["schema"], "families: %s" % exc))
            continue
        stats["family_schemas"] += 1
        stats["family_outcomes"] += len(built[-1][4])
    if text is None:
        return errors, stats
    b = [i for i, ln in enumerate(lines) if ln == marks[0]]
    e = [i for i, ln in enumerate(lines) if ln == marks[1]]
    if not b and not e:
        stats["families_without_section"] += len(rows)
        return errors, stats
    if len(b) != 1 or len(e) != 1 or e[0] < b[0]:
        return errors + [(norms, "families: the norms hold the built section once, between %s and %s" % marks)], stats
    if not rows:
        return errors + [(norms, "families: section markers, but the catalog gives this chapter no family with a "
                                 "schema")], stats
    if len(built) != len(rows):
        return errors, stats
    said = "\n".join(lines[b[0] + 1:e[0]]) + "\n"
    new = section.build_families_section(Path(norms).resolve(), Path(root).resolve(), built)
    if said != new:
        o, n = said.splitlines(), new.splitlines()
        at = next((i for i, (x, y) in enumerate(zip(o, n)) if x != y), min(len(o), len(n)))
        errors.append((norms, "families: the section differs from the built one at its line %d (rebuild: python "
                              "skills/lesson-spec/scripts/v7/sections.py %s)" % (at + 1, Path(norms).relative_to(root))))
    else:
        stats["families_with_section"] += len(rows)
    return errors, stats
