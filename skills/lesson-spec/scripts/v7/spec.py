"""Проверки `check_spec` на стандартных файлах В7 (PLAN-TRANSITION п. 1.3): семьи каталога, исходы по местам схемы,
самодостаточность схем, переносимость `pattern`, корпус P/02.1 и связи CEL, пакет `family-read`.

Режим выбирается файлами: у главы есть `<база>.schema.json` — проверка В7, иначе — диалект (`form_source`). Ошибки —
SpecError с сообщением; check_spec называет файл.
"""
import json
import re
from pathlib import Path

CATALOG = Path("Platform/common/data/catalog.tsv")
SCHEMA_PATH = re.compile(r"([0-9]{2})-[a-z][a-z-]*/data/([^/]+)\.schema\.json")
OUTCOME_HEADER = ["path", "outcome", "priority", "unit", "norm"]
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
                if re.search(pat.replace("\\Z", "$"), seg):
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


def load_outcomes(path, doc):
    """`<семья>.outcomes.tsv` → [(path, outcome, priority, unit, norm)]: путь — место схемы, пустой путь есть."""
    name = Path(path).name
    if not Path(path).is_file():
        raise SpecError("%s: no outcomes file next to the schema (ADR-0088 доп. (2) С11)" % name)
    text = Path(path).read_bytes().decode("utf-8", "replace")
    first = next((ln for ln in text.split("\n") if ln and not ln.startswith("#")), None)
    if first is None or first.split("\t") != OUTCOME_HEADER:
        raise SpecError("%s: header must be %s" % (name, "<TAB>".join(OUTCOME_HEADER)))
    places, out, seen = Places(doc), [], set()
    for no, (p, outcome, priority, unit, norm) in tsv_rows(path, 5, OUTCOME_HEADER):
        if p in seen:
            raise SpecError("%s:%d: path %r repeated" % (name, no, p))
        seen.add(p)
        if p and (not p.startswith("/") or places.place(p) is None):
            raise SpecError("%s:%d: path %r is not a place of the schema%s" % (
                name, no, p, " (segment * only at names or items)" if "*" in p.split("/") else ""))
        if not re.fullmatch(r"0|[1-9][0-9]*", priority):
            raise SpecError("%s:%d: priority must be an integer ≥ 0" % (name, no))
        if unit not in UNITS:
            raise SpecError("%s:%d: unit is one of %s" % (name, no, ", ".join(UNITS)))
        if not outcome.strip() or not norm.strip():
            raise SpecError("%s:%d: outcome and norm must be said" % (name, no))
        out.append((p, outcome, int(priority), unit, norm))
    if "" not in seen:
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
    """Выражения вне ECMA-262 `u` ∩ RE2 (ADR-0092 п. 14): синтаксис переносимого подмножества (regex.check), Python `re`
    и — если на стенде есть `v7check` — Go `regexp` (RE2)."""
    from v7 import regex
    bad = []
    for where, p in patterns(doc):
        why = regex.check(p)
        if why:
            bad.append("pattern at %s: %s" % (where or "#", why))
    return bad
