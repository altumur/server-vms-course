"""GEN01: pure P/03 row constructors from the accepted row-write-bindings form.

This is an overlay of the existing schema-mode families package. It does not
change the family generator, copy its codecs, or implement the SDK's IO loop.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

import gen_families as families
from gen_checks import GenError, go_str, gofmt
import lesson
import machine_source
import tsv_input
import wire

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
L = lesson.CURRENT
FORM = "Platform/03-worker/forms/row-write-bindings.tsv"
GRAMMAR = "Platform/03-worker/forms/row-write-bindings.md"
CATALOG = "Platform/common/data/catalog.tsv"
CODEC = "Platform/common/data/codec.tsv"
KEYS = "Platform/common/data/key-placeholders.tsv"
STORE = "Platform/01-store/spec/01-store.api.openapi.yaml"
MANIFEST = "Platform/02-installer/spec/02.1-installer.schema.json"
RUNTIME = HERE / "rowwritert/go/runtime.go"
COLUMNS = ("write", "key", "field", "source", "value", "guard_key", "guard_version", "norm")
TYPES = ("string", "boolean", "integer", "number", "object", "array", "dyn")
POINTER = r"(?:/(?:[^~/\s]|~[01])*)+"
DECL = re.compile(rf"#(start|input) ({POINTER}) ([a-z]+)\Z")
FIELD = re.compile(r"/(?:[^~/]|~[01])+\Z")
PLACE = re.compile(rf"\{{(start|input):({POINTER})\}}\Z")
VERSION = re.compile(rf"(start|input):({POINTER})\Z")
NAME = re.compile(r"[a-z][a-z0-9-]*\Z")


def enabled(root=ROOT):
    if L.key != "03-worker":
        return False
    if (Path(root) / FORM).is_file():
        return True
    if (Path(root) / GRAMMAR).is_file():
        raise GenError(f"missing required constructor form {FORM}")
    return False  # older exports predate both the form and its grammar


def rows(root, rel, names=None):
    try:
        return tsv_input.read(Path(root) / rel, names=names, root=root)
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None


def parse_template(text, decls):
    # A slash inside a source pointer is not a key-segment separator.
    segments = re.findall(r"\{[^{}]+\}|[^/{}]+", text)
    if "/".join(segments) != text:
        raise GenError(f"invalid whole-segment key template {text!r}")
    result = []
    for segment in segments:
        match = PLACE.fullmatch(segment)
        if match:
            src, pointer = match.groups()
            if decls.get((src, pointer)) != "string":
                raise GenError(f"{text}: key reference must be a declared string: {segment}")
            result.append({"source": src, "pointer": pointer})
        elif re.fullmatch(r"[A-Za-z0-9._-]+", segment):
            result.append({"literal": segment})
        else:
            raise GenError(f"invalid key segment {segment!r}")
    return result


def matches_family(key, segments):
    if len(key) != len(segments):
        return False
    for binding, family in zip(key, segments):
        if "source" in binding:
            if not re.fullmatch(r"<[^<>]+>", family):
                return False
        else:
            parts = re.split(r"(<[^<>]+>)", family)
            pattern = "".join(re.escape(p) if i % 2 == 0 else "[^/]+" for i, p in enumerate(parts))
            if not re.fullmatch(pattern, binding["literal"]):
                return False
    return True


def resolve(doc, node):
    seen = set()
    while "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            raise GenError(f"unsupported or cyclic schema reference {ref!r}")
        seen.add(ref)
        target = doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                raise GenError(f"missing schema reference {ref!r}")
            target = target[part]
        if not isinstance(target, dict):
            raise GenError(f"schema reference is not an object {ref!r}")
        node = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
    return node


def check_schema_words(value):
    if not isinstance(value, dict):
        raise GenError("family schema nodes must be objects")
    for key, child in value.items():
        if key not in families.DOC_WORDS:
            raise GenError(f"unsupported family schema word {key!r}")
        if key in ("properties", "$defs", "patternProperties"):
            if not isinstance(child, dict):
                raise GenError(f"{key} must contain schema nodes")
            for node in child.values():
                check_schema_words(node)
        elif key in ("allOf", "anyOf", "oneOf"):
            for node in child:
                check_schema_words(node)
        elif key in ("items", "additionalProperties", "if", "then", "else", "not", "propertyNames") and isinstance(child, dict):
            check_schema_words(child)


def load(root=ROOT):
    root = Path(root)
    table = rows(root, FORM, COLUMNS)
    decls = {}
    for line in table.text.split("\n"):
        if not re.match(r"#(?:start|input)(?:\s|$)", line):
            continue
        m = DECL.fullmatch(line)
        if not m or m[3] not in TYPES or (m[1], m[2]) in decls:
            raise GenError(f"{FORM}: invalid or duplicate source declaration {line!r}")
        decls[m[1], m[2]] = m[3]
    grammar = {r["placeholder"]: r["pattern"] for _, r in rows(root, KEYS).rows}
    catalog = [r for _, r in rows(root, CATALOG, families.CATALOG_COLUMNS).rows]
    anchors = set()
    norms = sorted((root / "Platform/03-worker/spec").glob("*.norms.md"))
    for path in norms:
        anchors.update(re.findall(r"<!-- req: (P/03\.[0-9]+-R[0-9]+) -->", path.read_text()))
    groups, seen, paths = {}, set(), [root / FORM, root / GRAMMAR, root / CATALOG, root / CODEC, root / KEYS,
                                   root / STORE, root / MANIFEST]
    for line, row in table.rows:
        where = f"{FORM}:{line}"
        if not NAME.fullmatch(row["write"]) or not FIELD.fullmatch(row["field"]):
            raise GenError(f"{where}: invalid constructor or direct property pointer")
        identity = row["write"], row["field"]
        if identity in seen:
            raise GenError(f"{where}: duplicate write/property {identity}")
        seen.add(identity)
        ns = row["norm"].split(",")
        if not ns or len(set(ns)) != len(ns) or any(n not in anchors for n in ns):
            raise GenError(f"{where}: norms must name existing distinct lesson anchors")
        source = row["source"]
        if source == "const":
            try:
                value = wire.strict_json(row["value"], where)
                json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (wire.WireError, ValueError, UnicodeError):
                raise GenError(f"{where}: const must be one scalar-UTF8 JSON value") from None
        elif source not in ("start", "input") or (source, row["value"]) not in decls:
            raise GenError(f"{where}: value must be a declared source pointer")
        groups.setdefault(row["write"], []).append(row)
    if set(groups) != {"state"}:
        raise GenError(f"{FORM}: this published overlay requires exactly constructor state")
    writes = []
    for name, group in groups.items():
        first = group[0]
        for column in ("key", "guard_key", "guard_version"):
            if any(r[column] != first[column] for r in group):
                raise GenError(f"{name}: {column} differs inside a constructor")
        key = parse_template(first["key"], decls)
        candidates = []
        for family in catalog:
            segs = family["key"].split("/")
            if matches_family(key, segs):
                candidates.append(family)
        if len(candidates) != 1 or candidates[0]["kind"] != "row":
            raise GenError(f"{name}: key must select exactly one row family")
        family = candidates[0]
        schema_path = root / "Platform" / family["schema"]
        if not schema_path.is_file() or not schema_path.name.endswith(".schema.json"):
            raise GenError(f"{name}: target family must have a schema")
        doc = json.loads(schema_path.read_bytes())
        check_schema_words(doc)
        properties = resolve(doc, doc).get("properties", {})
        bound = []
        for row in group:
            field = row["field"][1:].replace("~1", "/").replace("~0", "~")
            if field not in properties:
                raise GenError(f"{name}: foreign property {field!r}")
            node = resolve(doc, properties[field])
            codec = "jcs" if node.get("x-encoding") == "jcs" else node.get("x-codec")
            if isinstance(codec, list) and len(codec) == 1:
                codec = codec[0]
            if codec not in ("string", "integer", "jcs"):
                raise GenError(f"{name}.{field}: unsupported writer codec {codec!r}")
            ty = node.get("type")
            ty = [ty] if isinstance(ty, str) else ty
            if row["source"] != "const":
                declared = decls[row["source"], row["value"]]
                if ty and declared != "dyn" and declared not in ty and not (declared == "integer" and "number" in ty):
                    raise GenError(f"{name}.{field}: source type does not match schema")
            elif ty:
                value = wire.strict_json(row["value"], name)
                typ = {str: "string", bool: "boolean", int: "integer", float: "number", dict: "object", list: "array",
                       type(None): "null"}[type(value)]
                if typ not in ty and not (typ == "integer" and "number" in ty):
                    raise GenError(f"{name}.{field}: const type does not match schema")
            bound.append({"field": field, "source": row["source"], "pointer": row["value"], "codec": codec})
        if set(resolve(doc, doc).get("required", [])) - {r["field"] for r in bound}:
            raise GenError(f"{name}: missing required properties")
        gkey, gver = first["guard_key"], first["guard_version"]
        if (gkey == "-") != (gver == "-"):
            raise GenError(f"{name}: guard key and version must both be set or both absent")
        guard = [] if gkey == "-" else parse_template(gkey, decls)
        version = None
        if gver != "-":
            m = VERSION.fullmatch(gver)
            if not m or decls.get((m[1], m[2])) != "string":
                raise GenError(f"{name}: guard version must reference a declared string")
            version = {"source": m[1], "pointer": m[2]}
        template = families.template(family["key"], grammar)
        names = [i for i, part in enumerate(family["key"].split("/")) if part == "<name>"]
        if len(names) != 1:
            raise GenError(f"{name}: unsupported state-name position in family")
        writes.append({"name": name, "family": family["key"], "key": key, "guard": guard,
                       "version": version, "fields": bound, "state_name": key[names[0]],
                       "pattern": "^" + "".join(re.escape(lit) if lit else "(?:" + g.removeprefix("^").removesuffix("$") + ")"
                                               for lit, _, g in template) + "$"})
        paths += [schema_path, schema_path.with_name(schema_path.name.replace(".schema.json", ".layers.tsv"))]
    # The state-name grammar and version grammar are source data, not new limits.
    manifest = json.loads((root / MANIFEST).read_bytes())
    import yamlsub
    store = yamlsub.load((root / STORE).read_text())
    return {"declarations": [{"source": s, "pointer": p, "type": ty} for (s, p), ty in decls.items()],
            "writes": writes, "name_pattern": manifest["$defs"]["name"]["pattern"],
            "version_pattern": store["components"]["schemas"]["VersionOrAbsent"]["pattern"],
            "schema_words": sorted(families.DOC_WORDS), "sources": list(dict.fromkeys(paths + norms))}


def render(root=ROOT):
    model = load(root)
    data = {k: v for k, v in model.items() if k != "sources"}
    head = "// Code generated by tools/normgen/gen_row_writes.py; DO NOT EDIT.\n"
    for path in model["sources"]:
        head += f"// {path.relative_to(root)} sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}\n"
    generated = head + "\npackage families\n\nconst rowWriteBindings = " + go_str(json.dumps(data, separators=(",", ":"))) + "\n"
    runtime = "// Code generated by tools/normgen/gen_row_writes.py: copy of tools/normgen/rowwritert/go/runtime.go; DO NOT EDIT.\n" + RUNTIME.read_text()
    return machine_source.go_files({"row_writes.go": gofmt(generated), "row_write_runtime.go": gofmt(runtime)}, generator=__file__, sources=(*model["sources"], RUNTIME), root=root)


def generate(root=ROOT, out=None):
    target = Path(out or lesson.output_root() / "p03") / "go/families"
    target.mkdir(parents=True, exist_ok=True)
    for name, text in render(root).items():
        (target / name).write_text(text)
    return target


def kit_files(out=None):
    if not enabled():
        return []
    target = Path(out or L.out) / "go/families"
    result = []
    for name, text in render().items():
        kept = target / name
        if not kept.is_file() or kept.read_text() != text:
            raise GenError(f"{kept} is stale: run gen_row_writes.py --lesson 03-worker")
        origin = "handwritten" if name == "row_write_runtime.go" else "generated"
        source = RUNTIME if origin == "handwritten" else kept
        result.append(("families", name, kept.read_bytes(), origin, L.output_source(kept, out or L.out) if source == kept else source.relative_to(ROOT).as_posix()))
    return result


def provenance():
    def entry(p):
        return {"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    paths = [p for src in load()["sources"] for p in
             (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])]
    return {"form": [entry(p) for p in dict.fromkeys(paths)],
            "generators": [entry(p) for p in (Path(__file__), Path(families.__file__), Path(tsv_input.__file__),
                                             Path(wire.__file__), HERE / "gen_checks.py", HERE / "yamlsub.py", Path(machine_source.__file__))],
            "handwritten": [entry(RUNTIME)], "judge": entry(HERE / "test_gen_row_writes.py")}


KIT_MD = """
### P/03 state row constructor (GEN01; part `families`)

`CaptureStateStart` captures the accepted start and its `StateSpec` together. `BuildState` returns only
key/items/guard; it does not read, reread, write, decide may_write, or run CAS/retry. Keep the snapshot for that
accepted start. The function cannot prove that the caller captured the right start. The ordinary SDK must still
pass `s5-state-start-born` through its real state-write procedure.

```go
spec := families.StateSpec{Schemas: stateSchemas, Defs: schemaDefs} // accepted manifest, not a later read
snapshot, err := families.CaptureStateStart(startJSON, spec)        // sub, unit, born, revision, epoch, epoch_index
write, err := families.BuildState(snapshot, inputJSON)              // name, value; no new schema argument
```

Check every error before IO. A missing pointer is an error; an explicit empty `born` is a string, while a permitted
JSON null value is stored as the required JCS item `"null"`. `RowWrite.Items` is newly owned by the caller and its
guard `Index` is a whole string, including versions beyond binary64 and int64. The SDK still reads the state CAS
version and applies may_write, CAS, guard refusal and retry itself. This helper is not an SDK or stage verdict.
"""


if __name__ == "__main__":
    try:
        if L.key != "03-worker":
            raise GenError("gen_row_writes is published only for 03-worker")
        if enabled():
            print(generate())
    except GenError as exc:
        print(f"gen_row_writes: {exc}", file=sys.stderr)
        raise SystemExit(1)
