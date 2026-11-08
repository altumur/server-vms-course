"""Generate data-family readers from schemas, without a model (ADR-0125 generator 5, narrowed to validators by addendum (1), item 4).

Read row families owned by the lesson from common/data/catalog.tsv; their JSON Schema 2020-12 and layer-3 x-* keywords; matching layers.tsv locations/keywords/values; and only path, reader, priority and unit from outcomes.tsv. Outcome prose is normative text, not generator input. Key grammar comes from key-placeholders.tsv, with the old README table only for historical exports. outcome-units.tsv closes the unit vocabulary; common/ru is not an input.

Emit standard-library Go 1.22 families.go with *Family, typed rows, Read<Family>, Items and keys, plus famrt/go/runtime.go implementing V7 item codecs, layer3, JSON Schema, refusal paths and reader outcomes. Unknown schema keywords, non-row families and unsupported * in keys/outcomes raise GenError rather than silently dropping constraints. family_judge.py executes family-read/NN.tsv; check_spec compares vectors with V7.

  python tools/normgen/gen_families.py [lesson [output-directory]]
Default lesson: 01."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import GenError, go_str, gofmt  # noqa: E402
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
import tsv_input  # noqa: E402
import machine_source  # noqa: E402
L = lesson.CURRENT

CATALOG = ROOT / "Platform/common/data/catalog.tsv"
KEYS_README = ROOT / "Platform/common/data/README.md"
PLACEHOLDER_LABELS = ROOT / "Platform/common/placeholders.tsv"
KEY_GRAMMARS = ROOT / "Platform/common/data/key-placeholders.tsv"
OUTCOME_UNITS = ROOT / "Platform/common/data/outcome-units.tsv"
PLATFORM = ROOT / "Platform"
RUNTIME_FLAT = HERE / "famrt/go/runtime.go"
RUNTIME_DOC = HERE / "famrt2/go/runtime.go"     # Data-schema mode for lessons after P/01 (ADR-0125 addendum (5)).
DOC_MODE = L.key != lesson.DEFAULT                # P/01 keeps its flat mode byte for byte.
RUNTIME = RUNTIME_DOC if DOC_MODE else RUNTIME_FLAT
JUDGE = HERE / "family_judge.py"
DEFAULT_OUT = L.out
DEFAULT_LESSON = L.nn
KIT_DIRS = ("families",)
CATALOG_COLUMNS = ["key", "kind", "owner", "ops", "readers", "when", "version", "schema", "norm"]
OUTCOME_COLUMNS = ["path", "reader", "outcome", "priority", "unit", "norm"]
UNITS = ("row", "field", "element")
LEGACY_UNITS = ('\u0441\u0442\u0440\u043e\u043a\u0430', '\u043f\u043e\u043b\u0435', '\u044d\u043b\u0435\u043c\u0435\u043d\u0442')
ROOT_WORDS = {"$schema", "type", "properties", "additionalProperties", "required", "$defs", "description"}
PLACE_WORDS = {"$ref", "description", "type", "x-codec", "x-whole", "x-time", "x-integer", "minimum", "maximum",
               "x-max-bytes", "enum"}
CODECS = {"integer", "time", "string", "boolean", "number"}
DOC_WORDS = {"$schema", "$defs", "$ref", "description", "type", "enum", "const", "pattern", "minLength", "maxLength",
             "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "uniqueItems", "items",
             "minProperties", "maxProperties", "properties", "patternProperties", "additionalProperties", "propertyNames",
             "required", "anyOf", "allOf", "oneOf", "not", "if", "then", "else", "x-codec", "x-encoding", "x-whole", "x-time",
             "x-integer", "x-max-bytes", "x-max-names", "x-opaque"}     # Keywords executed by famrt2.
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
    try:
        return [row for _, row in tsv_input.read(path, names=columns, root=ROOT).rows]
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None


def grammar_sources():
    if KEY_GRAMMARS.is_file():
        return [KEY_GRAMMARS]
    return [KEYS_README] + ([PLACEHOLDER_LABELS] if PLACEHOLDER_LABELS.is_file() else [])


def unit_words():
    """Semantic units from this source's registry; legacy exports keep their raw words."""
    if OUTCOME_UNITS.is_file():
        words = [r["unit"] for r in tsv(OUTCOME_UNITS, ["unit", "meaning"])]
        if len(words) != len(UNITS) or set(words) != set(UNITS):
            raise GenError(f"{rel(OUTCOME_UNITS)}: closed units must be {UNITS}")
        return dict(zip(UNITS, UNITS))
    if KEY_GRAMMARS.is_file():
        raise GenError(f"{rel(OUTCOME_UNITS)}: missing canonical unit registry")
    return dict(zip(UNITS, LEGACY_UNITS))


def placeholders():
    """Typed registry (legacy: README): placeholder → portable grammar ^(?:…)$."""
    if KEY_GRAMMARS.is_file():
        out = {}
        for row in tsv(KEY_GRAMMARS, ["placeholder", "pattern", "example", "norm"]):
            label, grammar = row["placeholder"], row["pattern"]
            if label in out and out[label] != grammar:
                raise GenError(f"{rel(KEY_GRAMMARS)}: conflicting grammars for {label}")
            if not label or not grammar:
                raise GenError(f"{rel(KEY_GRAMMARS)}: empty placeholder or grammar")
            out[label] = grammar
        if not out:
            raise GenError(f"{rel(KEY_GRAMMARS)}: no placeholder grammar")
        return out
    out, inside = {}, False
    for x in KEYS_README.read_text(encoding="utf-8").split("\n"):
        if x.startswith("| Placeholder | Grammar |"):
            inside = True
            continue
        if inside:
            if not x.startswith("|"):
                break
            m = re.match(r"\| `(<[^`]+>|\*)` \| `(.+?)` \| ", x)
            if m:
                label, grammar = m.group(1), m.group(2).replace("\\|", "|")
                if label in out and out[label] != grammar:
                    raise GenError(f"{rel(KEYS_README)}: conflicting grammars for {label}")
                out[label] = grammar
    if not out:
        raise GenError(f"{rel(KEYS_README)}: no placeholder table")
    # The catalogue keeps its typed key templates. Only the spelling used to look
    # up their grammar changes between the ru/en labels of ADR-0121 (3).
    if PLACEHOLDER_LABELS.is_file():
        explicit = dict(out)
        seen = set()
        for row in tsv(PLACEHOLDER_LABELS, ["ru", "en"]):
            if not row["ru"] or not row["en"] or row["ru"] in seen:
                raise GenError(f"{rel(PLACEHOLDER_LABELS)}: empty or duplicate ru label {row['ru']!r}")
            seen.add(row["ru"])
            ru, en = f"<{row['ru']}>", f"<{row['en']}>"
            # README is typed data: distinguish legacy server/key spellings from their canonical typed names.
            # can denote different types. Prose labels never override those.
            if ru in explicit and en in explicit:
                continue
            source, alias = (en, ru) if en in explicit else (ru, en)
            if source in explicit:
                if alias in out and out[alias] != explicit[source]:
                    raise GenError(f"{rel(PLACEHOLDER_LABELS)}: conflicting grammars for alias {alias}")
                out[alias] = explicit[source]
    return out


def template(key, grammar):
    """Parse a catalog key template into [(literal, placeholder, grammar)]."""
    if "*" in key and not DOC_MODE:         # In data-schema mode, '*' is a README placeholder (spec.PLACEHOLDER).
        raise GenError(f"{key}: «*» in a key template is outside the generator")
    segs = []
    for part in re.split(r"(<[^<>]+>|\*)", key):
        if not part:
            continue
        if part.startswith("<") or part == "*":
            if part not in grammar:
                raise GenError(f"{key}: placeholder {part} has no grammar in {rel(grammar_sources()[0])}")
            segs.append(("", part, grammar[part]))
        else:
            segs.append((part, "", ""))
    return segs


def go_name(words):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[/_\-.]+", words) if w)


def family_name(key, full=False):
    """Derive a Go family name from non-placeholder key words; '*' becomes All. full includes placeholders to disambiguate duplicate short names: <a:b> -> b, <a> -> a, no ASCII letters -> Part."""
    k = re.sub(r"(^|/)\*(?=/|$)", r"\1all", key)
    if full:
        def word(m):
            w = re.sub(r"[^A-Za-z0-9]+", "-", m[1].split(":")[-1]).strip("-")
            return w or "part"
        k = re.sub(r"<([^<>]+)>", word, k)
    k = re.sub(r"<[^<>]+>", "", k)
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

    def root(self):
        """Resolve the schema root through local refs; a root {$ref: '#/$defs/...'} denotes its target node."""
        node, seen = self.doc, set()
        while isinstance(node, dict) and isinstance(node.get("$ref"), str) and node["$ref"].startswith("#/"):
            ref = node["$ref"]
            if ref in seen:
                raise GenError(f"{rel(self.path)}: $ref cycle {ref!r}")
            seen.add(ref)
            node = self.at(ref[1:])
            if node is None:
                raise GenError(f"{rel(self.path)}: $ref {ref!r} does not resolve")
        return node

    def chain(self, node, where):
        """Return ref-chain nodes with the original location first, so its keywords take precedence."""
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
    """Validate layers.tsv as a copy of schema x-* keywords: every location and value must match."""
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
    units = tuple(unit_words().values())
    for r in tsv(outcomes_path, OUTCOME_COLUMNS):
        p = r["path"]
        if p and (not p.startswith("/") or "*" in unpointer(p) or schema.at("/properties" + p) is None):
            raise GenError(f"{rel(outcomes_path)}: path {p!r} — \"\" or a field of the row (no «*»)")
        if not re.fullmatch(r"0|[1-9][0-9]*", r["priority"]) or r["unit"] not in units:
            raise GenError(f"{rel(outcomes_path)}: priority — an integer ≥ 0, unit — one of {units}")
        outcomes.append({"path": p, "reader": r["reader"], "priority": int(r["priority"]), "unit": r["unit"]})
    if not any(o["path"] == "" for o in outcomes):
        raise GenError(f"{rel(outcomes_path)}: no row of the empty path (the readers)")
    return {"key": key, "kind": kind, "schema": row["schema"], "norm": row["norm"], "name": family_name(key),
            "template": template(key, grammar), "props": props, "required": required,
            "closed": root.get("additionalProperties") is False, "outcomes": outcomes,
            "sources": [schema_path, layers if layers.is_file() else None, outcomes_path], "layers": n_layers}


def place(doc, pointer):
    """Resolve an outcome location per V7 DIALECT section 9. Return {* segment index: declared property names} or None if absent. Follow the location, refs, allOf and conditional then branches. '*' denotes author-defined additional properties excluding declared ones, or array items; x-opaque allows any name."""
    def resolve(x, seen=()):
        out = []
        if not isinstance(x, dict):
            return out
        out.append(x)
        r = x.get("$ref")
        if isinstance(r, str) and r.startswith("#/") and r not in seen:
            at = doc
            for seg in unpointer(r[1:]):
                at = at.get(seg, {}) if isinstance(at, dict) else {}
            out += resolve(at, seen + (r,))
        for e in x.get("allOf", []):
            if isinstance(e, dict):
                out += resolve(e.get("then", {}) if "if" in e else e, seen)
        return out

    def child(chain, seg, i):
        if any(x.get("x-opaque") for x in chain):
            return [{}]
        if seg == "*":
            for x in chain:
                ap = x.get("additionalProperties")
                if isinstance(ap, dict) or ap is True:
                    wild[i] = sorted(x.get("properties") or ())
                    return resolve(ap if isinstance(ap, dict) else {})
            for x in chain:
                if isinstance(x.get("items"), dict):
                    wild[i] = []
                    return resolve(x["items"])
            return None
        for x in chain:
            if seg in (x.get("properties") or {}):
                return resolve(x["properties"][seg])
        if re.fullmatch(r"0|[1-9][0-9]*", seg):
            for x in chain:
                if isinstance(x.get("items"), dict):
                    return resolve(x["items"])
        for x in chain:
            for pat, ps in (x.get("patternProperties") or {}).items():
                if re.search(pat, seg):
                    return resolve(ps)
            ap = x.get("additionalProperties")
            if isinstance(ap, dict) or ap is True:
                return resolve(ap if isinstance(ap, dict) else {})
        return None

    wild, chain = {}, resolve(doc)
    for i, seg in enumerate(unpointer(pointer) if pointer else []):
        chain = child(chain, seg, i)
        if not chain:
            return None
    return wild


def load_family_doc(row, grammar):
    """Data-schema mode: famrt2 executes row schemas unchanged using its closed JSON Schema/V7 vocabulary. The generator checks an object root, copied layers.tsv keywords and row-field outcome paths."""
    key, kind = row["key"], row["kind"]
    if kind not in ("row", "object", "file"):
        raise GenError(f"{key}: kind {kind!r} — the schema mode reads row, object and file families")
    file_cell, _, word_ = row["schema"].partition("#")   # #<word> only identifies the outcomes filename (spec.load_family).
    schema_path = PLATFORM / file_cell
    if not schema_path.name.endswith(".schema.json") or not schema_path.is_file():
        raise GenError(f"{key}: schema {row['schema']!r} is not a file")
    base = schema_path.name[:-len(".schema.json")]
    out_base = base[:-len(kind) - 1] if kind != "file" and base.endswith("." + kind) else base
    out_base += f".{word_}" if word_ else ""
    schema = Schema(schema_path)
    root = schema.root()
    if kind == "row" and (not isinstance(root, dict) or root.get("type") != "object"):
        raise GenError(f"{rel(schema_path)}: the root of a row family is an object")
    defs = schema.doc.get("$defs", {}) if isinstance(schema.doc, dict) else {}
    profiles = ("person_writer", "role_writer")
    declared = isinstance(defs, dict) and any(name in defs for name in profiles)
    if key == "domain/deleting/<name>" or declared:
        if key != "domain/deleting/<name>" or kind != "row":
            raise GenError(f"{key}: contextual writer profiles require their catalog row identity")
        if not isinstance(defs, dict) or any(not isinstance(defs.get(name), dict) or
                                           defs[name].get("type") != "object" for name in profiles):
            raise GenError(f"{rel(schema_path)}: both ordinary local person_writer and role_writer are required")
        person_name = schema.at("/$defs/common.person_name")
        common_time = schema.at("/$defs/common.time")
        if (not isinstance(defs.get("writer"), dict) or not isinstance(person_name, dict) or
                person_name.get("type") != "string" or not isinstance(person_name.get("pattern"), str) or
                not isinstance(common_time, dict) or common_time.get("x-time") is not True):
            raise GenError(f"{rel(schema_path)}: contextual writer needs common writer and original name/time targets")
    words = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("properties", "$defs", "patternProperties"):
                    for vv in v.values():
                        walk(vv)
                else:
                    words.add(k)
                    walk(v)
        elif isinstance(x, list):
            for e in x:
                walk(e)
    walk(schema.doc)
    if "x-file" in words:                          # LAYERS.md layer3: family instances are files when kind=file carries that meaning.
        if kind != "file" or schema.doc.get("x-file") is not True or json.dumps(schema.doc).count('"x-file"') != 1:
            raise GenError(f"{rel(schema_path)}: x-file — only true, only at the root, only of a family of kind file")
        words.discard("x-file")
    extra = words - DOC_WORDS
    if extra:
        raise GenError(f"{rel(schema_path)}: words {sorted(extra)} are outside famrt2 (supported: {sorted(DOC_WORDS)})")
    layers = schema_path.with_name(base + ".layers.tsv")
    n_layers = check_layers(schema, layers) if layers.is_file() else 0
    outcomes_path = schema_path.with_name(out_base + ".outcomes.tsv")
    outcomes = []
    units = tuple(unit_words().values())
    for r in tsv(outcomes_path, OUTCOME_COLUMNS):
        p = r["path"]
        wild = place(schema.doc, p) if p.startswith("/") else None
        if p and (not p.startswith("/") or (kind == "row" and wild is None)):
            raise GenError(f'{rel(outcomes_path)}: path {p!r} -- empty path or a row-schema location (V7: * is a name '
                           f"or an item); object, file — a JSON Pointer")
        if not re.fullmatch(r"0|[1-9][0-9]*", r["priority"]) or r["unit"] not in units:
            raise GenError(f"{rel(outcomes_path)}: priority — an integer ≥ 0, unit — one of {units}")
        outcomes.append({"path": p, "reader": r["reader"], "priority": int(r["priority"]), "unit": r["unit"],
                         "wild": wild or {}})
    if not any(o["path"] == "" for o in outcomes):
        raise GenError(f"{rel(outcomes_path)}: no row of the empty path (the readers)")
    return {"key": key, "kind": kind, "schema": row["schema"], "norm": row["norm"], "name": family_name(key),
            "template": template(key, grammar), "doc": schema_path.read_text(encoding="utf-8"), "outcomes": outcomes,
            "sources": [schema_path, layers if layers.is_file() else None, outcomes_path], "layers": n_layers}


def go_family_doc(f):
    n = f["name"]
    segs = ", ".join(f"{{Lit: {go_str(a)}, Placeholder: {go_str(b)}, Grammar: {go_str(c)}}}" for a, b, c in f["template"])
    def wild(o):
        if not o.get("wild"):
            return ""
        return ", Wild: map[int][]string{" + ", ".join(
            f"{i}: {{{', '.join(go_str(x) for x in names)}}}" for i, names in sorted(o["wild"].items())) + "}"
    outs = ", ".join(f"{{Path: {go_str(o['path'])}, Reader: {go_str(o['reader'])}, Priority: {o['priority']}, "
                     f"Unit: {go_str(o['unit'])}{wild(o)}}}" for o in f["outcomes"])
    readers = []
    for o in f["outcomes"]:
        if o["path"] == "" and o["reader"] not in readers:
            readers.append(o["reader"])
    return (f"// {n} — the family {f['key']} ({f['kind']}; {f['schema']}; {f['norm']}).\n"
            f"// Readers (the rows of the empty path of the outcomes): {', '.join(readers)}.\n"
            f"var {n} = &Family{{Key: {go_str(f['key'])}, Kind: {go_str(f['kind'])}, Schema: {go_str(f['schema'])}, "
            f"Norm: {go_str(f['norm'])},\nTemplate: []Seg{{{segs}}},\nOutcomes: []Outcome{{{outs}}},\n"
            f"Doc: {go_str(f['doc'])}}}")


def families(lesson=DEFAULT_LESSON):
    grammar = placeholders()
    rows = [r for r in tsv(CATALOG, CATALOG_COLUMNS)
            if r["owner"].startswith(f"P/{lesson}") and re.search(r"\.schema\.json(#[a-z][a-z0-9-]*)?$", r["schema"])]
    if not rows:
        raise GenError(f"{rel(CATALOG)}: no family of P/{lesson} with a schema")
    out = [(load_family_doc if DOC_MODE else load_family)(r, grammar) for r in rows]
    short = [f["name"] for f in out]
    for f in out:
        if short.count(f["name"]) > 1:
            f["name"] = family_name(f["key"], full=True)
    names = [f["name"] for f in out]
    if len(set(names)) != len(out):
        raise GenError("two families with one Go name: " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
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
    # Typed row.
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
    uses_bool = not DOC_MODE and any(p["codec"][0] == "boolean" for f in fams for p in f["props"])
    inputs = [CATALOG] + [p for f in fams for p in f["sources"] if p is not None]
    inputs += grammar_sources() + ([OUTCOME_UNITS] if OUTCOME_UNITS.is_file() else [])
    header = machine_source.identity_header("tools/normgen/gen_families.py",
                                             [(rel(p), sha(p)) for p in dict.fromkeys(inputs)])
    head = "package families\n" + ('\nimport "strconv"\n' if uses_bool else "")
    units = unit_words()
    parts = [head, f"const unitRow = {go_str(units['row'])}\nconst unitField = {go_str(units['field'])}"] \
        + [(go_family_doc if DOC_MODE else go_family)(f) for f in fams]
    parts.append("// All — the families in the order of the catalog.\nvar All = []*Family{" +
                 ", ".join(f["name"] for f in fams) + "}")
    parts.append("// ByKey — the family of a catalog key template; nil — none.\nfunc ByKey(key string) *Family {\n"
                 "for _, f := range All {\nif f.Key == key {\nreturn f\n}\n}\nreturn nil\n}")
    return machine_source.go_source("\n\n".join(parts) + "\n", header=header)


def render(lesson=DEFAULT_LESSON):
    fams = families(lesson)
    header = machine_source.identity_header("tools/normgen/gen_families.py", [(rel(RUNTIME), sha(RUNTIME))])
    runtime = machine_source.go_source(RUNTIME.read_text(encoding="utf-8"), header=header)
    return {"families.go": gofmt(go_module(fams, lesson)), "runtime.go": gofmt(runtime)}


def generate(lesson=DEFAULT_LESSON, out=DEFAULT_OUT):
    gdir = Path(out) / "go/families"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in render(lesson).items():
        (gdir / name).write_text(text, encoding="utf-8")
    return gdir


def kit_files(out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source)]; stale output raises GenError."""
    files = []
    for name, text in sorted(render().items()):
        kept = Path(out) / "go/families" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_families.py")
        origin, source = ("handwritten", rel(RUNTIME)) if name == "runtime.go" else ("generated", L.output_source(kept, out))
        files.append(("families", name, kept.read_bytes(), origin, source))
    return files


def sources(lesson=DEFAULT_LESSON):
    out = [CATALOG] + grammar_sources() + ([OUTCOME_UNITS] if OUTCOME_UNITS.is_file() else [])
    for f in families(lesson):
        out += [s for s in f["sources"] if s is not None]
    return list(dict.fromkeys(p for src in out for p in
                              (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])))


def provenance():
    """Part provenance (ADR-0125 addendum (1), item 6(a)): forms, generator, handwritten runtime and judge with paths/SHA256."""
    def entry(path):
        return {"path": rel(path), "sha256": sha(path)}
    return {"form": [entry(p) for p in sources()], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__)),
                           entry(Path(machine_source.__file__))],
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

KIT_MD_DOC = """
## Part `families`: reading the data families (generated; the schemas are data)

| Package | Import path | Origin |
|---|---|---|
| `families` | `{module}/internal/families` | `families.go` — one `*Family` per row family of the lesson with a schema, the schema text as data (`Platform/common/data/catalog.tsv`, `data/<family>.schema.json`, `outcomes.tsv`); `runtime.go` — the hand-written executor of the schemas; closed |

```go
f := families.ByKey("platform/manifest/<sub>")            // the family of a catalog key template; families.All
r := f.Judge(key, families.ItemsOf(items), families.Reader) // r.Verdict "ok" | "refused", r.Paths — JSON Pointers
outcome := f.OutcomesFor(r.Paths, "admin")                   // the rows of <family>.outcomes.tsv that act at this reader
w := f.Judge(key, families.ItemsOf(items), families.Writer)   // before a write: retain the concrete key
// Keyless JudgeItems cannot prove person/role context; a contextual writer requires Judge.
```

The reading is that of the V7 stack of the course: the codec of the items (`x-encoding` json|jcs, `x-codec`), layer 3
(`x-time`, `x-integer`, `x-whole`, `x-max-bytes`, `x-max-names`, `$defs.writer`), then JSON Schema 2020-12 with the
refusal places of the dialect. There is no typed row here: read the values yourself from a readable row. What an
outcome does is the prose of the norm (the column outcome of `<family>.outcomes.tsv`).
"""


def kit_md():
    """Use KIT_MD_DOC for data-schema lessons; KIT_MD for P/01."""
    return KIT_MD_DOC if DOC_MODE else KIT_MD



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
