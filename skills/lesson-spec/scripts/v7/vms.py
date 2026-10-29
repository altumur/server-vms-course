"""Семьи VMS в открытых местах семей платформы (решение «Архитектора» по запросу VMS «семьи в открытых местах»,
вариант А, decisions/inbox/2026-10-29-запрос-vms-семьи-расширение.md).

Строка каталога VMS `VMS/common/data/catalog.tsv` — колонки каталога платформы и `place`: `key` и `kind` — экземпляр
ключа и вид ровно одной семьи платформы со схемой (плейсхолдер — как есть или литерал, `<sub>` — подсистема урока
владельца), `place` — JSON Pointer открытого места её схемы (`*` — любое имя или элемент), `schema` — схема урока
владельца V/NN[.K], она судит значение места после того, как строку приняла семья платформы; пути исходов — от значения
места. Векторы — пакет `VMS/common/vectors/family-read/NN.tsv` (NN — урок владельца): заголовок платформы и `place`
после `kind`; строит `build_tables`, судит `check_tables`.

    python -m v7.vms --root ДЕРЕВО --tables        (из skills/lesson-spec/scripts; таблицы пакета заново)
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v7 import regex, spec, stack  # noqa: E402

CATALOG = Path("VMS/common/data/catalog.tsv")
FIELDS = ["key", "kind", "owner", "ops", "readers", "when", "version", "schema", "norm", "place"]
LESSONS = Path("VMS/common/lessons.tsv")
FAMILY_READ = Path("VMS/common/vectors/family-read")
HEADER = ["case", "family", "key", "kind", "place", "mode", "who", "text", "verdict", "paths", "outcome", "note"]
README = """# Векторы семей VMS (family-read)

Таблица `NN.tsv` на урок VMS, владеющий семьями `VMS/common/data/catalog.tsv` (решение «Архитектора» по запросу VMS
«семьи в открытых местах», вариант А). Строка: семья (`family`, `kind`, `place` — строка каталога VMS), конкретный ключ,
режим и роли (`who`), текст строки семьи платформы (`text`, как в `Platform/common/vectors/family-read/`), вердикт и пути
отказа (от корня строки), исход у каждого читателя (`outcome`: роль → пути строк `outcomes.tsv` семьи VMS, пути — от
значения места). Сначала строку судит семья платформы, затем схема VMS — значение в каждом экземпляре места `place`.
Строки, где отказывает сама семья платформы, сюда не входят — это векторы платформы.

Строит `python -m v7.vms --root . --tables` (из `skills/lesson-spec/scripts`), судит `check_spec`.
"""


def read_catalog(root):
    """Строки каталога VMS → [dict] (ops — текст, `line` — номер строки); None — файла нет; заголовок не тот — SpecError."""
    path = Path(root) / CATALOG
    if not path.is_file():
        return None
    rows, header = [], None
    for no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if header is None:
            if cols != FIELDS:
                raise spec.SpecError("%s: header must be %s" % (CATALOG, " ".join(FIELDS)))
            header = cols
            continue
        row = dict(zip(header, cols + [""] * (len(header) - len(cols))))
        row["line"] = no
        rows.append(row)
    return rows


def subsystems(root):
    """{урок NN: подсистема} по `VMS/common/lessons.tsv` (колонка subsystem, «-» — нет)."""
    out = {}
    path = Path(root) / LESSONS
    for line in path.read_text(encoding="utf-8").split("\n") if path.is_file() else []:
        cols = line.split("\t")
        if line and not line.startswith("#") and len(cols) >= 4 and cols[3] != "-":
            out[cols[0]] = cols[3]
    return out


def template_re(key):
    """Ключ каталога платформы → regex экземпляра: плейсхолдер — он сам или литерал (группа на каждый)."""
    parts = re.split(r"(<[^<>]+>)", key)
    return re.compile("".join("(%s|[^/<>]+)" % re.escape(p) if p.startswith("<") else re.escape(p) for p in parts)), \
        [p for p in parts if p.startswith("<")]


def platform_row(vrow, catalog, sub):
    """Строка каталога платформы со схемой, чей ключ покрывает ключ строки VMS (тот же kind): ровно одна; `<sub>` —
    литерал подсистемы урока владельца. → строка или SpecError."""
    hits = []
    for r in catalog:
        if r["kind"] != vrow["kind"] or not spec.is_v7_family(r) or r["schema"].startswith("VMS/"):
            continue
        rx, names = template_re(r["key"])
        m = rx.fullmatch(vrow["key"])
        if m:
            hits.append((r, dict(zip(names, m.groups()))))
    if len(hits) != 1:
        raise spec.SpecError("key %s (%s) is an instance of %s families of the Platform catalog with a schema, not one"
                             % (vrow["key"], vrow["kind"], len(hits) if hits else "no"))
    r, got = hits[0]
    if "<sub>" in got and got["<sub>"] != sub:
        raise spec.SpecError("key %s: <sub> of %s is %s, not %s — the subsystem of the owner lesson %s"
                             % (vrow["key"], r["key"], got["<sub>"], sub or "none", vrow["owner"]))
    return r


def open_place(doc, place):
    """Место `place` схемы платформы есть и открыто: под `x-opaque` или само `x-opaque`, отображение с
    `additionalProperties` не false (слова сверх полей платформы) или место без ограничений. → None или почему нет."""
    if place != "" and not place.startswith("/"):
        return "place %r is not a JSON Pointer" % place
    places = spec.Places(doc)
    chain = places.place(place)
    if chain is None:
        return "place %r is not a place of the Platform schema" % place
    if any(s.get("x-opaque") for s in chain) or chain == [{}]:
        return None
    if any(s.get("additionalProperties") is False or s.get("unevaluatedProperties") is False for s in chain):
        return "place %r of the Platform schema is closed (additionalProperties false)" % place
    if any(isinstance(s.get("additionalProperties"), dict) or s.get("additionalProperties") is True for s in chain):
        return None
    if all(not set(s) - {"description", "$comment"} for s in chain):
        return None
    return "place %r of the Platform schema is not open (no x-opaque, no words beyond its fields)" % place


def instances(value, segs, at=()):
    """Экземпляры места (сегменты, `*` — любое имя или элемент) в разобранном значении → [путь]."""
    if not segs:
        return [list(at)]
    seg, rest, out = segs[0], segs[1:], []
    if isinstance(value, dict):
        for k in (list(value) if seg == "*" else [seg] if seg in value else []):
            out += instances(value[k], rest, at + (k,))
    elif isinstance(value, list):
        if seg == "*":
            keys = range(len(value))
        else:
            keys = [int(seg)] if re.fullmatch(r"0|[1-9][0-9]*", seg) and int(seg) < len(value) else []
        for i in keys:
            out += instances(value[i], rest, at + (i,))
    return out


def seg_of(at, s):
    """Сегмент пути в индекс списка (цифры указателя) или имя."""
    return int(s) if isinstance(at, list) and isinstance(s, str) else s


def get(value, path):
    for s in path:
        value = value[seg_of(value, s)]
    return value


class Judge:
    """Суд строки семьи VMS: семья платформы, затем схема VMS — значение каждого экземпляра места."""

    def __init__(self, root, vrow, catalog, sub):
        self.vrow = vrow
        self.prow = platform_row(vrow, catalog, sub)
        _, _, self.pdoc, _, _ = spec.load_family(root, self.prow)
        _, _, self.vdoc, self.outcomes_path, self.outcomes = spec.load_family(root, vrow)
        self.platform = stack.Family(self.pdoc, self.prow["kind"])
        self.family = stack.Family(self.vdoc, "value")
        self.segs = spec.unpointer(vrow["place"]) if vrow["place"] else []

    def judge(self, text, mode):
        """→ {verdict, paths (от корня строки), rel (пути от значения места), frame (семья платформы приняла)}."""
        p = self.platform.judge(spec.family_value(self.prow["kind"], text), mode)
        if p["verdict"] != "ok":
            return {"verdict": "refused", "paths": p["paths"], "rel": [], "frame": False}
        paths, rel = [], []
        for at in instances(p["value"], self.segs):
            r = self.family.judge(get(p["value"], at), mode)
            for q in r["paths"]:
                paths.append(list(at) + spec.unpointer(q) if q else list(at))
                rel.append(q)
        ps = [stack.pointer(q) for q in stack.canonical(paths)]
        return {"verdict": "refused" if ps else "ok", "paths": ps, "rel": sorted(set(rel)), "frame": True}

    def who(self, mode):
        return spec.who_of(self.vrow, "writer") if mode == "writer" else spec.readers_of(self.outcomes)

    def outcome(self, mode, rel):
        if mode == "writer":
            return []
        return {r: [o.path for o in spec.outcomes_for(self.outcomes, rel, r)] for r in self.who(mode)}


def families(root):
    """(строки каталога VMS, каталог платформы, {урок: подсистема}, [ошибки (где, сообщение)]) — без суда строк."""
    try:
        rows = read_catalog(root)
    except spec.SpecError as exc:
        return [], [], {}, [(CATALOG, str(exc))]
    return rows or [], spec.read_catalog(root), subsystems(root), []


def check_rows(root):
    """Строки каталога VMS против семей платформы: ключ — экземпляр одной семьи со схемой, место открыто, схема VMS,
    слои и исходы годны; (key, kind, place) не повторяется. → (ошибки, {ключ строки: Judge})."""
    rows, catalog, subs, errors = families(root)
    judges, seen = {}, set()
    for r in rows:
        where = (CATALOG, "line %d" % r["line"])
        k = (r["key"], r["kind"], r["place"])
        if k in seen:
            errors.append((CATALOG, "line %d: key, kind and place repeated" % r["line"]))
            continue
        seen.add(k)
        try:
            j = Judge(root, r, catalog, subs.get(r["owner"][2:4]))
        except (spec.SpecError, OSError) as exc:
            errors.append((CATALOG, "%s: %s" % (where[1], exc)))
            continue
        why = open_place(j.pdoc, r["place"])
        if why:
            errors.append((CATALOG, "line %d: %s (%s)" % (r["line"], why, j.prow["key"])))
            continue
        judges[k] = j
    return errors, judges


# ---------------------------------------------------------------- значения по схеме VMS

def merged(places, s):
    """Слова места схемы (цепочка $ref/allOf) в один словарь: первое значение слова — его."""
    out = {}
    for x in places.resolve(s):
        for w, v in x.items():
            out.setdefault(w, v)
    return out


def sample_string(m):
    """Строка по `pattern`/`minLength`/`enum` места или None."""
    pat = m.get("pattern")
    lead = re.match(r"\^\(\?:([^\\\[\](){}*+?|^$.]*)", pat or "")
    for c in ([lead.group(1) + "x", lead.group(1) + "1"] if lead else []) + ["x", "a1", "1x1", "x-1"]:
        if len(c) >= m.get("minLength", 0) and (pat is None or regex.search(pat, c)):
            return c
    return None


def build(places, s):
    """Значение места по схеме VMS (все свойства, какие строятся) или None."""
    return build_m(places, merged(places, s))


def build_m(places, m):
    if "const" in m:
        return copy.deepcopy(m["const"])
    if "enum" in m:
        return copy.deepcopy(m["enum"][0])
    ty = m.get("type")
    ty = ty[0] if isinstance(ty, list) else ty
    if ty == "object" or "properties" in m:
        out = {}
        for k, ps in (m.get("properties") or {}).items():
            v = build(places, ps)
            if v is not None:
                out[k] = v
        return out if all(k in out for k in m.get("required", [])) else None
    if ty == "array":
        n = m.get("minItems", 0)
        item = build(places, m["items"]) if isinstance(m.get("items"), dict) else None
        if n and item is None:
            return None
        return [copy.deepcopy(item) for _ in range(n)] if not m.get("uniqueItems") or n < 2 else None
    if ty == "string":
        return sample_string(m)
    if ty in ("integer", "number"):
        return max(m.get("minimum", 0), 1 if m.get("x-time") else 0)
    if ty == "boolean":
        return True
    return None


def fill(places, s, v):
    """Значение рамки (платформы) дополнено по схеме VMS: свойства, которых нет, — построенные; элементы — по items."""
    m = merged(places, s)
    if isinstance(v, dict):
        for k, ps in (m.get("properties") or {}).items():
            if k in v:
                v[k] = fill(places, ps, v[k])
            else:
                b = build(places, ps)
                if b is not None:
                    v[k] = b
        return v
    if isinstance(v, list) and isinstance(m.get("items"), dict):
        return [fill(places, m["items"], x) for x in v]
    return v


def repair(places, family, v):
    """Значение места, которое схема VMS отвергает (слово рамки вне её enum, нет обязательного), — места отказа заново
    по схеме; до неподвижной точки. → значение или None."""
    for _ in range(8):
        r = family.judge(copy.deepcopy(v), "writer")
        if r["verdict"] == "ok":
            return v
        for q in r["paths"]:
            chain = places.place(q)
            m = {}
            for x in chain or []:
                for w, y in x.items():
                    m.setdefault(w, y)
            b = build_m(places, m) if chain else None
            if b is None:
                return None
            v = setat(v, spec.unpointer(q), b)
    return None


def wrong(m):
    """Значение не того типа."""
    ty = m.get("type")
    ty = ty[0] if isinstance(ty, list) else ty
    return {"string": 1, "integer": "1", "number": "1", "boolean": "true", "array": {}, "object": []}.get(ty, None)


def mutations(places, s, v, path=()):
    """[(путь от значения места, что, новое значение или DEL)] по схеме VMS на построенном значении."""
    m, out = merged(places, s), []
    w = wrong(m)
    if w is not None:
        out.append((path, "type", w))
    if "const" in m:
        out.append((path, "const", "not-const" if m["const"] != "not-const" else 0))
    if "enum" in m:
        out.append((path, "enum", "not_enum" if "not_enum" not in m["enum"] else 0))
    if isinstance(v, str):
        if m.get("pattern"):
            bad = next((c for c in ("", " ", "~~", "x\n") if not regex.search(m["pattern"], c)), None)
            if bad is not None:
                out.append((path, "pattern", bad))
        if m.get("minLength"):
            out.append((path, "minLength", ""))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in m:
            out.append((path, "minimum", m["minimum"] - 1))
        if m.get("x-integer"):
            out.append((path, "x-integer", 1.5))
        if m.get("x-time"):
            out.append((path, "x-time", -1))
    if isinstance(v, list):
        if m.get("minItems"):
            out.append((path, "minItems", []))
        if m.get("uniqueItems") and v:
            out.append((path, "uniqueItems", v + [copy.deepcopy(v[0])]))
        if isinstance(m.get("items"), dict) and v:
            out += mutations(places, m["items"], v[0], path + (0,))
    if isinstance(v, dict):
        for k in m.get("required", []):
            out.append((path + (k,), "required", DEL))
        if m.get("additionalProperties") is False:
            out.append((path + ("zz_extra",), "additionalProperties", 1))
        for k, ps in (m.get("properties") or {}).items():
            if k in v:
                out += mutations(places, ps, v[k], path + (k,))
    return out


DEL = object()


def setat(v, path, x):
    if not path:
        return x
    at = get(v, path[:-1])
    if x is DEL:
        del at[seg_of(at, path[-1])]
    else:
        at[seg_of(at, path[-1])] = x
    return v


# ---------------------------------------------------------------- текст строки семьи платформы

def item_encoding(pdoc, key):
    """x-encoding элемента строки (`row`) схемы платформы."""
    places = spec.Places(pdoc)
    chain = places.child(places.resolve(pdoc), key, None, 0) or []
    return next((s["x-encoding"] for s in chain if s.get("x-encoding")), None)


def decode_text(kind, text):
    """Текст строки семьи платформы → изменяемое значение (у `row` элементы JSON — разобраны)."""
    v = json.loads(text)
    if kind != "row":
        return v, {}
    enc = {}
    for k, t in list(v.items()):
        try:
            x = json.loads(t)
        except ValueError:
            continue
        if isinstance(x, (dict, list)):
            v[k], enc[k] = x, True
    return v, enc


def encode_text(pdoc, kind, v, enc):
    if kind != "row":
        return stack.jcs(v)
    out = {}
    for k, x in v.items():
        if k in enc:
            e = item_encoding(pdoc, k)
            x = stack.jcs(x) if e == "jcs" else json.dumps(x, ensure_ascii=False, separators=(",", ":"))
        out[k] = x
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def frames(root, prow):
    """Строки ok писателя семьи платформы из её таблицы family-read (тексты)."""
    p = Path(root) / spec.FAMILY_READ / ("%s.tsv" % prow["owner"][2:4])
    out = []
    for ln in p.read_text(encoding="utf-8").split("\n")[1:] if p.is_file() else []:
        c = ln.split("\t")
        if len(c) == len(spec.FR_HEADER) and c[1] == prow["key"] and c[3] == prow["kind"] and c[4] == "writer" \
                and c[7] == "ok":
            out.append(c[6])
    return out


def plain_first(text):
    """Рамка, чьи имена верха — обычные (`[a-z0-9_-]*`), — первой; иначе — порядок таблицы платформы."""
    v = json.loads(text)
    return not all(re.fullmatch(r"[a-z0-9_-]*", k) for k in (v if isinstance(v, dict) else {}))


def cases(root, j):
    """Строки таблицы семьи VMS: основа (рамка платформы с значением места по схеме VMS) и мутации места, в режимах
    writer и reader. → [(mode, text, verdict, paths, rel, note)]; SpecError — основы нет."""
    places = spec.Places(j.vdoc)
    base = None
    for t in sorted(frames(root, j.prow), key=plain_first):
        v, enc = decode_text(j.prow["kind"], t)
        ats = sorted(instances(v, j.segs), key=lambda a: not all(re.fullmatch(r"[a-z0-9_-]+|[0-9]+", str(s)) for s in a))
        if not ats:
            continue
        at = ats[0]
        x = repair(places, j.family, fill(places, j.vdoc, copy.deepcopy(get(v, at))))
        if x is None:
            continue
        v = setat(v, at, x)
        text = encode_text(j.pdoc, j.prow["kind"], v, enc)
        if all(j.judge(text, mode)["verdict"] == "ok" for mode in ("writer", "reader")):
            base = (v, enc, at)
            break
    if base is None:
        raise spec.SpecError("%s %s: no ok row of %s in the Platform family-read holds the place, or the value built by "
                             "the VMS schema is refused there" % (j.vrow["key"], j.vrow["place"] or "/", j.prow["key"]))
    v, enc, at = base
    out = []
    for mode in ("writer", "reader"):
        out.append((mode, encode_text(j.pdoc, j.prow["kind"], v, enc), "base"))
    muts = [((), "null", None)] + mutations(places, j.vdoc, get(v, at))
    seen = set()
    for rel, what, x in muts:
        w = setat(copy.deepcopy(v), list(at) + list(rel), x)
        text = encode_text(j.pdoc, j.prow["kind"], w, enc)
        note = "%s %s" % (stack.pointer(rel) or "/", what)
        for mode in ("writer", "reader"):
            if (mode, text) not in seen:
                seen.add((mode, text))
                out.append((mode, text, note))
    rows = []
    for mode, text, note in out:
        r = j.judge(text, mode)
        if r["frame"]:
            rows.append((mode, text, r["verdict"], r["paths"], r["rel"], note))
    return rows


def build_tables(root):
    """Пакет family-read VMS заново: README и `NN.tsv` на урок владельца. → {урок: строк}."""
    errors, judges = check_rows(root)
    if errors:
        sys.exit("VMS catalog:\n  " + "\n  ".join("%s: %s" % e for e in errors))
    templates, why = keys(root, judges)
    if why:
        sys.exit("VMS catalog keys:\n  " + "\n  ".join(why))
    d = Path(root) / FAMILY_READ
    d.mkdir(parents=True, exist_ok=True)
    (d / "README.md").write_text(README, encoding="utf-8")
    tables = {}
    for k, j in judges.items():
        lesson = j.vrow["owner"][2:4]
        for mode, text, verdict, paths, rel, note in cases(root, j):
            t = tables.setdefault(lesson, [])
            t.append(["V%s-%04d" % (lesson, len(t) + 1), k[0], templates[k].example(), k[1], k[2], mode,
                      json.dumps(j.who(mode), ensure_ascii=False), text, verdict, json.dumps(paths, ensure_ascii=False),
                      json.dumps(j.outcome(mode, rel), ensure_ascii=False), note])
    for p in d.glob("[0-9][0-9].tsv"):
        if p.stem not in tables:
            p.unlink()
    for lesson, rows in tables.items():
        (d / ("%s.tsv" % lesson)).write_text("".join("\t".join(r) + "\n" for r in [HEADER] + rows), encoding="utf-8")
    return {k: len(v) for k, v in sorted(tables.items())}


def keys(root, judges):
    """{(key, kind, place): KeyTemplate} ключей VMS по таблице плейсхолдеров каталога платформы, [ошибки]."""
    table, why = spec.placeholder_table(root)
    out = {}
    if table is None:
        return out, why
    for k in judges:
        try:
            out[k] = spec.KeyTemplate(k[0], table)
        except spec.SpecError as exc:
            why.append(str(exc))
    return out, why


def check_tables(root, judges):
    """Пакет family-read VMS: README, таблица на каждого урока-владельца, строка по форме, семья каталога VMS, who и
    исход — по каталогу и стеку В7. → (ошибки [(путь, сообщение)], счёты)."""
    errors, stats = [], {"vms_family_read_rows": 0, "vms_family_read_tables": 0}
    d = Path(root) / FAMILY_READ
    owners = {j.vrow["owner"][2:4] for j in judges.values()}
    if not d.is_dir():
        if owners:
            errors.append((FAMILY_READ, "family-read VMS: no package for the families of %s (rebuild: python -m v7.vms "
                                        "--root . --tables)" % ", ".join("V/" + o for o in sorted(owners))))
        return errors, stats
    if not (d / "README.md").is_file():
        errors.append((FAMILY_READ, "family-read VMS: the package needs README.md"))
    templates, _ = keys(root, judges)
    for p in sorted(d.iterdir()):
        if p.name in ("README.md", ".DS_Store"):
            continue
        m = re.fullmatch(r"([0-9]{2})\.tsv", p.name)
        if not m:
            errors.append((FAMILY_READ / p.name, "family-read VMS: only README.md and NN.tsv (one table per owner lesson)"))
            continue
        stats["vms_family_read_tables"] += 1
        owners.discard(m.group(1))
        lines = [ln for ln in p.read_text(encoding="utf-8").split("\n") if ln]
        where = FAMILY_READ / p.name
        if not lines or lines[0].split("\t") != HEADER:
            errors.append((where, "family-read VMS: header must be %s" % "<TAB>".join(HEADER)))
            continue
        seen, unknown = set(), {}
        for no, ln in enumerate(lines[1:], 2):
            cols = ln.split("\t")
            if len(cols) != len(HEADER):
                errors.append((where, "line %d: expected %d TSV columns" % (no, len(HEADER))))
                continue
            case, fam, key, kind, place, mode, who, text, verdict, paths, outcome, _note = cols
            if case in seen:
                errors.append((where, "line %d: case %r repeated" % (no, case)))
            seen.add(case)
            j = judges.get((fam, kind, place))
            if j is None or j.vrow["owner"][2:4] != m.group(1):
                unknown.setdefault((fam, kind, place), []).append(no)
                continue
            if mode not in ("writer", "reader"):
                errors.append((where, "line %d: mode is writer or reader" % no))
                continue
            stats["vms_family_read_rows"] += 1
            if key != templates[(fam, kind, place)].example():
                errors.append((where, "line %d: key is the example of the template %s" % (no, fam)))
            try:
                got = [json.loads(who), json.loads(paths), json.loads(outcome)]
            except ValueError:
                errors.append((where, "line %d: who, paths and outcome are JSON" % no))
                continue
            r = j.judge(text, mode)
            want = [j.who(mode), r["paths"], j.outcome(mode, r["rel"])]
            if not r["frame"]:
                errors.append((where, "line %d: the Platform family %s refuses the text: a vector of the Platform, not "
                                      "of VMS" % (no, j.prow["key"])))
            elif verdict != r["verdict"] or got != want:
                errors.append((where, "line %d: the V7 stack gives %s %s, who %s, outcome %s" % (
                    no, r["verdict"], json.dumps(r["paths"], ensure_ascii=False),
                    json.dumps(want[0], ensure_ascii=False), json.dumps(want[2], ensure_ascii=False))))
        for (fam, kind, place), nos in unknown.items():
            errors.append((where, "lines %s: %s (%s, place %r) is not a family of the VMS catalog owned by V/%s that "
                                  "judges" % (",".join(map(str, nos[:5])) + (",…" if len(nos) > 5 else ""), fam, kind,
                                              place, m.group(1))))
    for o in sorted(owners):
        errors.append((FAMILY_READ, "family-read VMS: no table %s.tsv for the families of V/%s" % (o, o)))
    return errors, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--tables", action="store_true", help="пакет family-read VMS заново")
    a = ap.parse_args(argv)
    if a.tables:
        print("family-read VMS tables:", build_tables(Path(a.root).resolve()))


if __name__ == "__main__":
    main()
