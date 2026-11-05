"""Генератор № 5 ADR-0125: чтение семей данных P/01 по их схемам — без модели (сужен доп. (1) п. 4 до валидаторов).

Читает каталог `Platform/common/data/catalog.tsv` (семьи урока-владельца со схемой), схему семьи
`Platform/<NN-процесс>/data/<семья>.schema.json` (JSON Schema 2020-12 со словами слоя 3 `x-*`), сверяет с ней
`<семья>.layers.tsv` (место, слово, значение — то же в схеме), берёт из `<семья>.outcomes.tsv` только путь, читателя,
приоритет и единицу (исход словами — проза нормы, генератор его не читает), грамматику плейсхолдеров ключа — из первой
таблицы `Platform/common/data/README.md`. Строит пакет Go 1.22 только на стандартной библиотеке `<out>/go/families`:
`families.go` (по *Family на семью, типизированная строка, Read<Семья>, Items, ключ) и ручную среду
`famrt/go/runtime.go` (проход стека В7: кодек items, слой 3, JSON Schema, пути отказа, исходы по читателю).

Слова схемы вне поддержанного набора, семья не `row`, `*` в ключе или в пути исхода — отказ генератора (GenError):
закрытый набор, а не молчаливый пропуск. Судья — `family_judge.py` (векторы `Platform/common/vectors/family-read/NN.tsv`)
и `check_spec` (векторы против стека В7).

Запуск: python tools/normgen/gen_families.py [урок [каталог_выхода]] (урок по умолчанию 01).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import GenError, go_str, gofmt  # noqa: E402

CATALOG = ROOT / "Platform/common/data/catalog.tsv"
KEYS_README = ROOT / "Platform/common/data/README.md"
PLATFORM = ROOT / "Platform"
RUNTIME = HERE / "famrt/go/runtime.go"
JUDGE = HERE / "family_judge.py"
DEFAULT_OUT = HERE / "out/p01-1"
DEFAULT_LESSON = "01"
KIT_DIRS = ("families",)
CATALOG_COLUMNS = ["key", "kind", "owner", "ops", "readers", "when", "version", "schema", "norm"]
OUTCOME_COLUMNS = ["path", "reader", "outcome", "priority", "unit", "norm"]
UNITS = ("строка", "поле", "элемент")
ROOT_WORDS = {"$schema", "type", "properties", "additionalProperties", "required", "$defs", "description"}
PLACE_WORDS = {"$ref", "description", "type", "x-codec", "x-whole", "x-time", "x-integer", "minimum", "maximum",
               "x-max-bytes", "enum"}
CODECS = {"integer", "time", "string", "boolean", "number"}
GO_TYPE = {"integer": "int64", "time": "float64", "string": "string", "boolean": "bool", "number": "float64"}
INT64 = (-(2 ** 63), 2 ** 63 - 1)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def tsv(path, columns):
    lines = [x for x in Path(path).read_text(encoding="utf-8").split("\n") if x and not x.startswith("#")]
    if not lines or lines[0].split("\t") != columns:
        raise GenError(f"{rel(path)}: header must be {'<TAB>'.join(columns)}")
    out = []
    for no, x in enumerate(lines[1:], 2):
        cols = x.split("\t")
        if len(cols) != len(columns):
            raise GenError(f"{rel(path)}: row {no}: {len(cols)} columns, expected {len(columns)}")
        out.append(dict(zip(columns, cols)))
    return out


def placeholders():
    """Первая таблица README ключей: плейсхолдер → грамматика (переносимое выражение ^(?:…)$)."""
    out, inside = {}, False
    for x in KEYS_README.read_text(encoding="utf-8").split("\n"):
        if x.startswith("| Placeholder | Grammar |"):
            inside = True
            continue
        if inside:
            if not x.startswith("|"):
                break
            m = re.match(r"\| `(<[^`]+>)` \| `(.+?)` \| ", x)
            if m:
                out[m.group(1)] = m.group(2).replace("\\|", "|")
    if not out:
        raise GenError(f"{rel(KEYS_README)}: no placeholder table")
    return out


def template(key, grammar):
    """Шаблон ключа каталога → [(литерал, плейсхолдер, грамматика)]."""
    if "*" in key:
        raise GenError(f"{key}: «*» in a key template is outside the generator")
    segs = []
    for part in re.split(r"(<[^<>]+>)", key):
        if not part:
            continue
        if part.startswith("<"):
            if part not in grammar:
                raise GenError(f"{key}: placeholder {part} has no grammar in {rel(KEYS_README)}")
            segs.append(("", part, grammar[part]))
        else:
            segs.append((part, "", ""))
    return segs


def go_name(words):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[/_\-.]+", words) if w)


def family_name(key):
    k = re.sub(r"<[^<>]+>", "", key)
    k = k[len("platform/"):] if k.startswith("platform/") else k
    name = go_name(k)
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
        raise GenError(f"{key}: no Go name")
    return name


def unpointer(p):
    return [s.replace("~1", "/").replace("~0", "~") for s in p.split("/")[1:]]


class Schema:
    def __init__(self, path):
        self.path = Path(path)
        self.doc = json.loads(self.path.read_text(encoding="utf-8"))

    def at(self, pointer):
        n = self.doc
        for s in unpointer(pointer):
            if not isinstance(n, dict) or s not in n:
                return None
            n = n[s]
        return n

    def chain(self, node, where):
        """[узлы] по цепочке $ref (место первым: его слова важнее)."""
        out, seen = [], set()
        while True:
            if not isinstance(node, dict):
                raise GenError(f"{rel(self.path)}: {where} is not a schema object")
            extra = set(node) - PLACE_WORDS
            if extra:
                raise GenError(f"{rel(self.path)}: {where}: words {sorted(extra)} are outside the generator "
                               f"(supported: {sorted(PLACE_WORDS)})")
            out.append(node)
            ref = node.get("$ref")
            if ref is None:
                return out
            if not ref.startswith("#/") or ref in seen:
                raise GenError(f"{rel(self.path)}: {where}: $ref {ref!r} is not a local #/… reference")
            seen.add(ref)
            node = self.at(ref[1:])
            where = ref
            if node is None:
                raise GenError(f"{rel(self.path)}: $ref {ref!r} does not resolve")


def word(chain, k, default=None):
    for s in chain:
        if k in s:
            return s[k]
    return default


def check_layers(schema, path):
    """layers.tsv — копия слов x-* схемы: каждое место есть в схеме, слово в нём — то же значение."""
    rows = tsv(path, ["place", "layer", "word", "value"])
    for r in rows:
        n = schema.at(r["place"])
        if not isinstance(n, dict):
            raise GenError(f"{rel(path)}: place {r['place']!r} is not in {rel(schema.path)}")
        if r["word"] not in n or n[r["word"]] != json.loads(r["value"]):
            raise GenError(f"{rel(path)}: {r['place']} {r['word']} = {r['value']}, the schema has "
                           f"{json.dumps(n.get(r['word']))}")
    return len(rows)


def prop_of(schema, name, node):
    where = f"/properties/{name}"
    ch = schema.chain(node, where)
    codec = word(ch, "x-codec")
    if not isinstance(codec, list) or not codec or set(codec) - CODECS:
        raise GenError(f"{rel(schema.path)}: {where}: x-codec {codec!r} — a non-empty list of {sorted(CODECS)}")
    types = word(ch, "type", [])
    types = [types] if isinstance(types, str) else list(types)
    bounds = {}
    for b in ("minimum", "maximum"):
        v = word(ch, b)
        if v is not None:
            if not isinstance(v, int) or isinstance(v, bool):
                raise GenError(f"{rel(schema.path)}: {where}: {b} {v!r} is not an integer")
            bounds[b] = v
    enum = word(ch, "enum")
    if enum is not None and not all(isinstance(e, str) for e in enum):
        raise GenError(f"{rel(schema.path)}: {where}: enum of non-strings is outside the generator")
    mb = word(ch, "x-max-bytes", -1)
    gotype = GO_TYPE[codec[0]]
    if len(codec) > 1 and len({GO_TYPE[c] for c in codec}) > 1:
        raise GenError(f"{rel(schema.path)}: {where}: x-codec {codec} has no single Go type")
    if gotype == "int64" and not (INT64[0] <= bounds.get("minimum", INT64[0] - 1)
                                  and bounds.get("maximum", INT64[1] + 1) <= INT64[1]):
        raise GenError(f"{rel(schema.path)}: {where}: an integer without bounds inside int64")
    return {"name": name, "go": go_name(name), "codec": codec, "whole": bool(word(ch, "x-whole")),
            "time": bool(word(ch, "x-time")), "integer": bool(word(ch, "x-integer")), "types": types,
            "min": bounds.get("minimum"), "max": bounds.get("maximum"), "max_bytes": mb, "enum": enum,
            "gotype": gotype}


def load_family(row, grammar):
    key, kind = row["key"], row["kind"]
    if kind != "row":
        raise GenError(f"{key}: kind {kind!r} — the generator reads only row families")
    schema_path = PLATFORM / row["schema"]
    if not schema_path.name.endswith(".schema.json") or not schema_path.is_file():
        raise GenError(f"{key}: schema {row['schema']!r} is not a file")
    base = schema_path.name[:-len(".schema.json")]
    schema = Schema(schema_path)
    root = schema.doc
    extra = set(root) - ROOT_WORDS
    if extra or root.get("type") != "object":
        raise GenError(f"{rel(schema_path)}: the root — an object with {sorted(ROOT_WORDS)}; extra {sorted(extra)}")
    if root.get("additionalProperties", True) not in (False, True):
        raise GenError(f"{rel(schema_path)}: additionalProperties — false or absent")
    props = [prop_of(schema, n, v) for n, v in root.get("properties", {}).items()]
    names = [p["name"] for p in props]
    required = root.get("required", [])
    if set(required) - set(names):
        raise GenError(f"{rel(schema_path)}: required {sorted(set(required) - set(names))} without properties")
    layers = schema_path.with_name(base + ".layers.tsv")
    n_layers = check_layers(schema, layers) if layers.is_file() else 0
    outcomes_path = schema_path.with_name(base + ".outcomes.tsv")
    outcomes = []
    for r in tsv(outcomes_path, OUTCOME_COLUMNS):
        p = r["path"]
        if p and (not p.startswith("/") or "*" in unpointer(p) or schema.at("/properties" + p) is None):
            raise GenError(f"{rel(outcomes_path)}: path {p!r} — \"\" or a field of the row (no «*»)")
        if not re.fullmatch(r"0|[1-9][0-9]*", r["priority"]) or r["unit"] not in UNITS:
            raise GenError(f"{rel(outcomes_path)}: priority — an integer ≥ 0, unit — one of {UNITS}")
        outcomes.append({"path": p, "reader": r["reader"], "priority": int(r["priority"]), "unit": r["unit"]})
    if not any(o["path"] == "" for o in outcomes):
        raise GenError(f"{rel(outcomes_path)}: no row of the empty path (the readers)")
    return {"key": key, "kind": kind, "schema": row["schema"], "norm": row["norm"], "name": family_name(key),
            "template": template(key, grammar), "props": props, "required": required,
            "closed": root.get("additionalProperties") is False, "outcomes": outcomes,
            "sources": [schema_path, layers if layers.is_file() else None, outcomes_path], "layers": n_layers}


def families(lesson=DEFAULT_LESSON):
    grammar = placeholders()
    rows = [r for r in tsv(CATALOG, CATALOG_COLUMNS)
            if r["owner"].startswith(f"P/{lesson}") and r["schema"].endswith(".schema.json")]
    if not rows:
        raise GenError(f"{rel(CATALOG)}: no family of P/{lesson} with a schema")
    out = [load_family(r, grammar) for r in rows]
    if len({f["name"] for f in out}) != len(out):
        raise GenError("two families with one Go name")
    return out


# ---------------------------------------------------------------- Go

def go_list(xs):
    return "[]string{" + ", ".join(go_str(x) for x in xs) + "}"


def go_family(f):
    n = f["name"]
    segs = ", ".join(f"{{Lit: {go_str(a)}, Placeholder: {go_str(b)}, Grammar: {go_str(c)}}}" for a, b, c in f["template"])
    props = []
    for p in f["props"]:
        props.append(
            f"{{Name: {go_str(p['name'])}, Codec: {go_list(p['codec'])}, Whole: {str(p['whole']).lower()}, "
            f"Time: {str(p['time']).lower()}, Integer: {str(p['integer']).lower()}, Types: {go_list(p['types'])}, "
            f"Min: {go_str('' if p['min'] is None else str(p['min']))}, "
            f"Max: {go_str('' if p['max'] is None else str(p['max']))}, MaxBytes: {p['max_bytes']}, "
            f"Enum: {'nil' if p['enum'] is None else go_list(p['enum'])}}}")
    outs = ", ".join(f"{{Path: {go_str(o['path'])}, Reader: {go_str(o['reader'])}, Priority: {o['priority']}, "
                     f"Unit: {go_str(o['unit'])}}}" for o in f["outcomes"])
    readers = []
    for o in f["outcomes"]:
        if o["path"] == "" and o["reader"] not in readers:
            readers.append(o["reader"])
    src = [f"// {n} — the family {f['key']} ({f['kind']}; {f['schema']}; {f['norm']}).\n"
           f"// Readers (the rows of the empty path of the outcomes): {', '.join(readers)}.\n"
           f"var {n} = &Family{{Key: {go_str(f['key'])}, Kind: {go_str(f['kind'])}, Schema: {go_str(f['schema'])}, "
           f"Norm: {go_str(f['norm'])},\nTemplate: []Seg{{{segs}}},\nProps: []Prop{{\n" + ",\n".join(props) + ",\n},\n"
           f"Required: {go_list(f['required'])}, Closed: {str(f['closed']).lower()},\n"
           f"Outcomes: []Outcome{{{outs}}}}}"]
    # типизированная строка
    fields = []
    for p in f["props"]:
        opt = p["name"] not in f["required"]
        fields.append(f"\t// {p['go']} — /{p['name']} ({', '.join(p['codec'])}{', optional' if opt else ''}).\n"
                      f"\t{p['go']} {'*' if opt else ''}{p['gotype']}")
    src.append(f"// {n}Row — the values of a readable row of {f['key']}.\ntype {n}Row struct {{\n" + "\n".join(fields) + "\n}")
    reads, writes = [], []
    for p in f["props"]:
        opt = p["name"] not in f["required"]
        get = {"int64": "intOf(v)", "float64": "floatOf(v)", "string": "v.s", "bool": "v.b"}[p["gotype"]]
        enc = {"integer": "textInt({x})", "time": "textTime({x})", "string": "{x}", "boolean": "strconv.FormatBool({x})",
               "number": "plainDecimal({x})"}[p["codec"][0]]
        if opt:
            reads.append(f"if v, ok := vals[{go_str(p['name'])}]; ok {{\nx := {get}\nrow.{p['go']} = &x\n}}")
            writes.append(f"if r.{p['go']} != nil {{\nm[{go_str(p['name'])}] = {enc.format(x='*r.' + p['go'])}\n}}")
        else:
            reads.append(f"if v, ok := vals[{go_str(p['name'])}]; ok {{\nrow.{p['go']} = {get}\n}}")
            writes.append(f"m[{go_str(p['name'])}] = {enc.format(x='r.' + p['go'])}")
    src.append(f"// Read{n} — a row of {f['key']} by its items (as stored): the values, or the refusal (Result.Paths;\n"
               f"// the outcome at a reader — {n}.OutcomesFor(r.Paths, role)). The key is not judged: {n}.Matches(key).\n"
               f"func Read{n}(items map[string]string, mode Mode) ({n}Row, Result) {{\n"
               f"r, vals := {n}.judge(ItemsOf(items), mode)\nvar row {n}Row\nif !r.OK() {{\nreturn row, r\n}}\n"
               + "\n".join(reads) + "\nreturn row, r\n}")
    src.append(f"// Items — the items of the row in the writer's notation (codec.tsv; time — to the millisecond), judged by\n"
               f"// the writer: a refused Result — not to be written.\n"
               f"func (r {n}Row) Items() (map[string]string, Result) {{\nm := map[string]string{{}}\n"
               + "\n".join(writes) + f"\nreturn m, {n}.JudgeItems(ItemsOf(m), Writer)\n}}")
    params = [(b, f"p{i}" if not re.fullmatch(r"<[a-z][a-z0-9]*>", b) else b[1:-1]) for i, (a, b, c) in enumerate(f["template"]) if b]
    if params:
        body = " + ".join(go_str(a) if not b else dict(params)[b] for a, b, c in f["template"])
        src.append(f"// {n}Key — the key of the row: {f['key']} (the placeholders by their grammar; {n}.Matches checks).\n"
                   f"func {n}Key({', '.join(v for _, v in params)} string) string {{\nreturn {body}\n}}")
    else:
        src.append(f"// {n}Key — the key of the row.\nconst {n}Key = {go_str(f['key'])}")
    return "\n\n".join(src)


def go_module(fams, lesson):
    uses_bool = any(p["codec"][0] == "boolean" for f in fams for p in f["props"])
    head = (f"// Code generated by tools/normgen/gen_families.py from {rel(CATALOG)} and the schemas of P/{lesson}; "
            f"DO NOT EDIT.\n")
    for f in fams:
        for s in f["sources"]:
            if s is not None:
                head += f"// {rel(s)} sha256 {sha(s)}\n"
    head += (f"// {rel(KEYS_README)} sha256 {sha(KEYS_README)}\n\n"
             f"// Package families — the reading of the data families of P/{lesson} (ADR-0125 № 5): by family a *Family\n"
             "// (Judge, Matches, OutcomesFor, Readers), the typed row Read<Family> and Items, the key. What an outcome does is\n"
             "// the prose of the norm (the column outcome of <family>.outcomes.tsv) — not here.\n"
             "package families\n" + ('\nimport "strconv"\n' if uses_bool else ""))
    parts = [head] + [go_family(f) for f in fams]
    parts.append("// All — the families in the order of the catalog.\nvar All = []*Family{" +
                 ", ".join(f["name"] for f in fams) + "}")
    parts.append("// ByKey — the family of a catalog key template; nil — none.\nfunc ByKey(key string) *Family {\n"
                 "for _, f := range All {\nif f.Key == key {\nreturn f\n}\n}\nreturn nil\n}")
    return "\n\n".join(parts) + "\n"


def render(lesson=DEFAULT_LESSON):
    fams = families(lesson)
    return {"families.go": gofmt(go_module(fams, lesson)), "runtime.go": RUNTIME.read_text(encoding="utf-8")}


def generate(lesson=DEFAULT_LESSON, out=DEFAULT_OUT):
    gdir = Path(out) / "go/families"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in render(lesson).items():
        (gdir / name).write_text(text, encoding="utf-8")
    return gdir


def kit_files(out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник)]; GenError — out устарел."""
    files = []
    for name, text in sorted(render().items()):
        kept = Path(out) / "go/families" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_families.py")
        origin, source = ("handwritten", rel(RUNTIME)) if name == "runtime.go" else ("generated", rel(kept))
        files.append(("families", name, kept.read_bytes(), origin, source))
    return files


def sources(lesson=DEFAULT_LESSON):
    out = [CATALOG, KEYS_README]
    for f in families(lesson):
        out += [s for s in f["sources"] if s is not None]
    return out


def provenance():
    """Паспорт части (ADR-0125 доп. (1) п. 6 (а)): формы, генератор, ручная среда, судья — пути и sha256."""
    def entry(path):
        return {"path": rel(path), "sha256": sha(path)}
    return {"form": [entry(p) for p in sources()], "generator": entry(Path(__file__).resolve()),
            "handwritten": [entry(RUNTIME)], "judge": entry(JUDGE)}


KIT_MD = """
## Part `families`: reading the data families (generated from `data/*.schema.json`)

| Package | Import path | Origin |
|---|---|---|
| `families` | `{module}/internal/families` | `families.go` generated from `Platform/common/data/catalog.tsv` and `Platform/01-store/data/<family>.schema.json` (with `layers.tsv`, the paths of `outcomes.tsv`); `runtime.go` — the hand-written environment of the generator |

Closed (regenerated with the kit). One `*families.Family` per family of P/01 with a schema: `families.EpochFloor`
(`platform/epoch_floor`), `families.ConfigstoreDoors` (`platform/configstore-doors/<id>`); `families.All`, `families.ByKey`.

```go
type Row struct{ Floor int64; GenerationAt float64 }       // families.EpochFloorRow (ConfigstoreDoorsRow{SeenAt float64})
func ReadEpochFloor(items map[string]string, mode families.Mode) (EpochFloorRow, families.Result)
func (r EpochFloorRow) Items() (map[string]string, families.Result)   // the writer's notation, judged by the writer
func ConfigstoreDoorsKey(id string) string                            // platform/configstore-doors/<id>; EpochFloorKey — a const
func (f *Family) Matches(key string) bool                             // the key by the catalog template
func (f *Family) Judge(key string, items Items, mode Mode) Result     // Result{Verdict "ok"|"refused", Paths []string}
func (f *Family) OutcomesFor(paths []string, reader string) []string // the paths of the outcomes.tsv rows that act
func (f *Family) Readers() []string
```

- `families.Writer` before a write (the strict notation), `families.Reader` when a row is read (the tolerant one):
  codec `Platform/common/data/codec.tsv`, the words `x-*` of the schema, JSON Schema. A refusal is a set of JSON Pointer
  paths (`/floor`; `""` — the row as a whole).
- An unreadable row at a reader: `f.OutcomesFor(r.Paths, role)` names the rows of `<family>.outcomes.tsv` that act
  (`"/floor"`, `""`); **what** each outcome does — its column `outcome` and the norm it names — is yours (the prose,
  not generated): e.g. an unreadable door row does not count as a visible door; a refused floor refuses the issue.
- The package reads and judges a row; when to read or write it, and the store operations, are yours.
"""


def main(argv):
    lesson = argv[1] if len(argv) > 1 else DEFAULT_LESSON
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        print(generate(lesson, out))
    except GenError as exc:
        print(f"gen_families: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
